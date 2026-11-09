"""Tarjima kataloglari bilan ishlash — GNU gettext o‘rnatilmagan bo‘lsa ham (masalan, Windows'da).

    python tools/catalog.py check            # kodda ishlatilgan, lekin katalogda yo‘q matnlar
    python tools/catalog.py add yangi.json   # {"o‘zbekcha matn": "English text", ...} ni en va uz ga qo‘shadi
    python tools/catalog.py compile          # django.po -> django.mo (en va uz)

`msgid`lar o‘zbekcha; `locale/en` ularni oddiy inglizchaga o‘giradi, `locale/uz` esa matnni o‘zi bilan
qaytaradi (u bo‘lmasa, Django o‘zbekcha sahifada ham inglizcha katalogga tushib ketadi).
"""
import ast
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ("en", "uz")
GETTEXT_NAMES = {"_", "gettext", "gettext_lazy", "gettext_noop", "_lazy"}
BS, NL = chr(92), chr(10)


# ---------- .po o‘qish / yozish ----------
def unquote(s: str) -> str:
    s = s.strip()[1:-1]
    out, i = [], 0
    while i < len(s):
        if s[i] == BS and i + 1 < len(s):
            out.append({"n": NL, "t": chr(9), '"': '"', BS: BS}.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def quote(s: str) -> str:
    return '"' + s.replace(BS, BS + BS).replace('"', BS + '"').replace(NL, BS + "n").replace(chr(9), BS + "t") + '"'


def parse_po(path: Path) -> dict:
    """{msgid: msgstr}. Sarlavha ('') ham kiradi. 'fuzzy' yozuvlar o‘tkazib yuboriladi."""
    entries, msgid, msgstr, field, fuzzy = {}, None, None, None, False

    def flush():
        nonlocal msgid, msgstr, field, fuzzy
        if msgid is not None and msgstr is not None and not fuzzy:
            entries[msgid] = msgstr
        msgid = msgstr = field = None
        fuzzy = False

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#,") and "fuzzy" in line:
            fuzzy = True
        elif line.startswith("msgid "):
            if msgid is not None:  # oldingi yozuvdan keyin bo‘sh qator bo‘lmagan
                flush()
            msgid, field = unquote(line[6:]), "id"
        elif line.startswith("msgstr "):
            msgstr, field = unquote(line[7:]), "str"
        elif line.startswith('"') and field:
            if field == "id":
                msgid += unquote(line)
            else:
                msgstr += unquote(line)
        elif not line.strip():
            flush()
    flush()
    return entries


def write_mo(entries: dict, path: Path):
    keys = sorted(entries)  # msgid bo‘yicha, baytlar tartibida
    ids = strs = b""
    offsets = []
    for k in keys:
        kb, vb = k.encode("utf-8"), entries[k].encode("utf-8")
        offsets.append((len(ids), len(kb), len(strs), len(vb)))
        ids += kb + b"\0"
        strs += vb + b"\0"
    n = len(keys)
    keystart = 7 * 4 + 16 * n
    valuestart = keystart + len(ids)
    koffsets, voffsets = [], []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]
    data = struct.pack("<Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
    data += struct.pack(f"<{len(koffsets)}i", *koffsets) + struct.pack(f"<{len(voffsets)}i", *voffsets)
    path.write_bytes(data + ids + strs)


def po_path(lang):
    return ROOT / "locale" / lang / "LC_MESSAGES" / "django.po"


# ---------- kodda ishlatilgan matnlar ----------
def python_msgids(path: Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:  # jimgina o‘tkazib yubormaymiz: fayldagi matnlar ko‘rinmay qolardi
        print(f"SINTAKSIS XATOSI  {path.relative_to(ROOT).as_posix()}:{exc.lineno}: {exc.msg}", file=sys.stderr)
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args:
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
            first = node.args[0]
            if name in GETTEXT_NAMES and isinstance(first, ast.Constant) and isinstance(first.value, str):
                yield first.value


TR_TAG = re.compile(r"""{%\s*(?:translate|trans)\s+(["'])(.*?)(?<!\\)\1""", re.S)
BLOCK = re.compile(r"{%\s*(?:blocktranslate|blocktrans)\b([^%]*)%}(.*?){%\s*end(?:blocktranslate|blocktrans)\s*%}", re.S)
UNDERSCORE = re.compile(r"""\b_\(\s*(["'])(.*?)(?<!\\)\1\s*\)""", re.S)
VAR = re.compile(r"{{\s*([\w.]+)\s*}}")


def _lit(s: str) -> str:
    return s.replace(BS + '"', '"').replace(BS + "'", "'")


def template_msgids(path: Path):
    src = path.read_text(encoding="utf-8")
    for m in TR_TAG.finditer(src):
        yield _lit(m.group(2)).replace("%", "%%")
    for m in BLOCK.finditer(src):
        body = m.group(2)
        if "{% plural %}" in body:
            continue
        if "trimmed" in m.group(1):
            body = " ".join(body.split())
        yield _block_msgid(body)
    for m in UNDERSCORE.finditer(src):
        yield _lit(m.group(2)).replace("%", "%%")


def _block_msgid(body: str) -> str:
    parts = re.split(r"({{\s*[\w.]+\s*}})", body)
    out = []
    for part in parts:
        v = VAR.fullmatch(part)
        out.append("%(" + v.group(1).split(".")[-1] + ")s" if v else part.replace("%", "%%"))
    return "".join(out)


def used_msgids():
    found = {}
    for base in ("apps", "config", "templates"):
        for path in (ROOT / base).rglob("*"):
            if "migrations" in path.parts or "__pycache__" in path.parts:
                continue
            gen = python_msgids(path) if path.suffix == ".py" else template_msgids(path) if path.suffix == ".html" else ()
            for msgid in gen:
                found.setdefault(msgid, path.relative_to(ROOT).as_posix())
    return found


# ---------- buyruqlar ----------
def cmd_check():
    en, uz = parse_po(po_path("en")), parse_po(po_path("uz"))
    used = used_msgids()
    missing = {m: f for m, f in used.items() if m.strip() and m not in en}
    for m, f in sorted(missing.items(), key=lambda x: x[1]):
        print(f"YO‘Q  {f}: {m[:90]}")
    only_one = (set(en) ^ set(uz)) - {""}
    for m in sorted(only_one):
        print(f"en/uz farq: {m[:90]}")
    unused = sorted(m for m in en if m and m not in used)
    print(f"\nKodda {len(used)} ta matn, katalogda {len(en) - 1} ta. Yetishmaydi: {len(missing)}. "
          f"Ishlatilmaydigan (ma’lumot uchun): {len(unused)}.")
    return 1 if missing or only_one else 0


def cmd_add(json_file):
    new = json.loads(Path(json_file).read_text(encoding="utf-8"))
    for lang in LOCALES:
        existing = parse_po(po_path(lang))
        chunks = []
        for msgid, english in new.items():
            if msgid in existing:
                continue
            flag = "#, python-format" + NL if re.search(r"%\([a-z_]+\)[sd]|%[sd]", msgid) else ""
            chunks.append(f"{flag}msgid {quote(msgid)}{NL}msgstr {quote(english if lang == 'en' else msgid)}{NL}")
        if chunks:
            with po_path(lang).open("a", encoding="utf-8", newline=NL) as f:
                f.write(NL + (NL).join(chunks))
        print(f"{lang}: {len(chunks)} ta qo‘shildi")
    cmd_compile()


def cmd_compile():
    for lang in LOCALES:
        entries = parse_po(po_path(lang))
        write_mo(entries, po_path(lang).with_suffix(".mo"))
        print(f"{lang}: django.mo yozildi ({len(entries) - 1} ta matn)")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["check"]
    if cmd == "check":
        sys.exit(cmd_check())
    elif cmd == "add" and args:
        cmd_add(args[0])
    elif cmd == "compile":
        cmd_compile()
    else:
        sys.exit(__doc__)
