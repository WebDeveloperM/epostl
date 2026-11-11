"""Video yozish dvigateli: ovoz (edge-tts), brauzer kadrlari (CDP screencast), sichqoncha effekti va montaj."""
import asyncio
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "pylib"))

import edge_tts  # noqa: E402
import imageio_ffmpeg  # noqa: E402

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
BASE = "http://127.0.0.1:8765"
VOICE = "uz-UZ-MadinaNeural"
RATE = "+10%"
VW, VH, DSF = 1280, 720, 1.5
BUILD = ROOT / "build"
TTS_DIR = BUILD / "tts"
DRY = False  # True: ovozsiz/kadrsiz tez sinov (selektorlarni tekshirish)


# ----------------------------------------------------------------- ovoz ---
def _duration(path: Path) -> float:
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr)
    h, mi, s = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(s)


async def tts(text: str) -> dict:
    TTS_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{VOICE}|{RATE}|{text}".encode()).hexdigest()[:16]
    mp3, meta = TTS_DIR / f"{key}.mp3", TTS_DIR / f"{key}.json"
    if meta.exists():
        return json.loads(meta.read_text(encoding="utf-8"))
    for attempt in range(4):
        try:
            com = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary")
            audio, words = bytearray(), []
            async for ch in com.stream():
                if ch["type"] == "audio":
                    audio += ch["data"]
                elif ch["type"] == "WordBoundary":
                    words.append({"t": ch["offset"] / 1e7, "d": ch["duration"] / 1e7, "w": ch["text"]})
            break
        except Exception:  # tarmoq uzilsa — qayta urinish
            if attempt == 3:
                raise
            await asyncio.sleep(2 + attempt * 2)
    mp3.write_bytes(bytes(audio))
    info = {"text": text, "path": str(mp3), "dur": _duration(mp3), "words": words}
    meta.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


# ------------------------------------------------------- sahifa effektlari ---
CURSOR_JS = r"""
(() => {
  if (window.__vc) return; window.__vc = 1;
  const css = `
  #__cur{position:fixed;left:-50px;top:-50px;width:30px;height:30px;z-index:2147483647;pointer-events:none;margin:-3px 0 0 -4px}
  #__cur svg{filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
  .__ripple{position:fixed;width:46px;height:46px;margin:-23px 0 0 -23px;border-radius:50%;border:3px solid rgba(65,84,241,.95);
    background:rgba(65,84,241,.18);z-index:2147483646;pointer-events:none;animation:__rp .55s ease-out forwards}
  @keyframes __rp{from{transform:scale(.25);opacity:1}to{transform:scale(1.35);opacity:0}}
  .__hl{position:fixed;z-index:2147483645;pointer-events:none;border:3px solid #f59e0b;border-radius:14px;
    animation:__pulse 1.3s ease-in-out infinite, __in .25s ease-out}
  @keyframes __pulse{0%,100%{box-shadow:0 0 0 4px rgba(245,158,11,.28)}50%{box-shadow:0 0 0 11px rgba(245,158,11,.10)}}
  @keyframes __in{from{opacity:0;transform:scale(1.04)}to{opacity:1;transform:scale(1)}}
  #__fade{position:fixed;inset:0;background:#0f172a;z-index:2147483647;pointer-events:none;transition:opacity .45s ease}
  html{scroll-behavior:auto !important}
  `;
  function mount(){
    if (document.getElementById('__cur')) return;
    const st=document.createElement('style'); st.textContent=css; document.head.appendChild(st);
    const c=document.createElement('div'); c.id='__cur';
    c.innerHTML='<svg width="30" height="30" viewBox="0 0 30 30"><path d="M5 3 L5 24 L10.6 18.6 L14.4 27 L18.2 25.3 L14.5 17 L22.5 17 Z" fill="#fff" stroke="#111827" stroke-width="1.7" stroke-linejoin="round"/></svg>';
    document.body.appendChild(c);
    let p=null; try{p=JSON.parse(sessionStorage.getItem('__cur')||'null')}catch(e){}
    if(p){c.style.left=p[0]+'px';c.style.top=p[1]+'px'}
  }
  document.addEventListener('mousemove',e=>{const c=document.getElementById('__cur');
    if(c){c.style.left=e.clientX+'px';c.style.top=e.clientY+'px'}
    try{sessionStorage.setItem('__cur',JSON.stringify([e.clientX,e.clientY]))}catch(_){}},true);
  document.addEventListener('mousedown',e=>{const r=document.createElement('div');r.className='__ripple';
    r.style.left=e.clientX+'px';r.style.top=e.clientY+'px';document.body.appendChild(r);setTimeout(()=>r.remove(),650)},true);
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',mount); else mount();
})();
"""


class Screencast:
    def __init__(self, page, folder: Path):
        self.page, self.dir, self.frames = page, folder, []
        self.cdp = None

    async def start(self):
        if DRY:
            return
        if self.dir.exists():
            shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True)
        self.cdp = await self.page.context.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", self._on_frame)
        await self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": int(VW * DSF),
                                                     "maxHeight": int(VH * DSF), "everyNthFrame": 1})

    def _on_frame(self, params):
        t = time.time()
        name = f"{len(self.frames):06d}.jpg"
        (self.dir / name).write_bytes(base64.b64decode(params["data"]))
        self.frames.append((t, name))
        asyncio.ensure_future(self.cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]}))

    async def stop(self):
        if DRY or not self.cdp:
            return
        await self.cdp.send("Page.stopScreencast")
        await asyncio.sleep(0.1)
        await self.cdp.detach()


class Beat:
    def __init__(self, scene, text, gap):
        self.scene, self.text, self.gap = scene, text, gap

    async def __aenter__(self):
        self.info = await tts(self.text)
        self.t0 = time.time()
        self.cursor = 0
        self.scene.audio.append({"path": self.info["path"], "t": self.t0, "words": self.info["words"],
                                 "text": self.text})
        self.scene.current = self
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None and not DRY:
            await sleep_until(self.t0 + self.info["dur"] + self.gap)
        self.scene.current = None
        return False

    async def at(self, word: str, extra: float = 0.0):
        """Diktor shu so'zni aytadigan paytgacha kutadi."""
        words = self.info["words"]
        low = word.strip("«»“”\"'.,!?:;").lower()
        for i in range(self.cursor, len(words)):
            if low in words[i]["w"].lower():
                self.cursor = i + 1
                if not DRY:
                    await sleep_until(self.t0 + words[i]["t"] + extra)
                return
        raise ValueError(f"so'z topilmadi: {word!r} — {self.text}")


async def sleep_until(t):
    d = t - time.time()
    if d > 0:
        await asyncio.sleep(d)


class Scene:
    """Bitta uzluksiz yozuv (bir sahifa, bir screencast)."""

    def __init__(self, name, page):
        self.name, self.page = name, page
        self.audio, self.current = [], None
        self.mouse = [VW * 0.62, VH * 0.55]
        self.cast = Screencast(page, BUILD / "frames" / name)

    # --- yozuvni boshlash/tugatish ---
    async def start(self, fade=True):
        if fade:
            await self.page.evaluate("""() => {let f=document.getElementById('__fade');
              if(!f){f=document.createElement('div');f.id='__fade';f.style.cssText='position:fixed;inset:0;background:#0f172a;z-index:2147483647;pointer-events:none;transition:opacity .45s ease';document.body.appendChild(f)}
              f.style.opacity='1';}""")
        await self.page.mouse.move(*self.mouse)
        await self.cast.start()
        self.t_start = time.time()
        await asyncio.sleep(0.15 if not DRY else 0)
        if fade:
            await self.page.evaluate("() => {const f=document.getElementById('__fade'); f.style.opacity='0';}")
            await asyncio.sleep(0.5 if not DRY else 0)

    async def end(self, fade=True, hold=0.3):
        await self.clear()
        if not DRY:
            await asyncio.sleep(hold)
        if fade:
            await self.page.evaluate("""() => {let f=document.getElementById('__fade');
              if(!f){f=document.createElement('div');f.id='__fade';f.style.cssText='position:fixed;inset:0;background:#0f172a;z-index:2147483647;pointer-events:none;transition:opacity .45s ease;opacity:0';document.body.appendChild(f); f.getBoundingClientRect();}
              f.style.opacity='1';}""")
            if not DRY:
                await asyncio.sleep(0.6)
        self.t_end = time.time()
        await self.cast.stop()
        return {"name": self.name, "t_start": getattr(self, "t_start", self.t_end), "t_end": self.t_end,
                "frames": self.cast.frames, "audio": self.audio}

    def beat(self, text, gap=0.3):
        return Beat(self, text, gap)

    async def at(self, word, extra=0.0):
        await self.current.at(word, extra)

    async def pause(self, s):
        if not DRY:
            await asyncio.sleep(s)

    # --- sichqoncha ---
    async def move(self, x, y, dur=0.55):
        x0, y0 = self.mouse
        n = max(6, int(dur * 50)) if not DRY else 1
        for i in range(1, n + 1):
            k = i / n
            e = k * k * (3 - 2 * k)
            await self.page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
            if not DRY:
                await asyncio.sleep(dur / n)
        self.mouse = [x, y]

    async def _center(self, loc, scroll=True, dx=0.5, dy=0.5):
        loc = loc.first
        if scroll:
            await self.ensure_visible(loc)
        box = await loc.bounding_box()
        return box["x"] + box["width"] * dx, box["y"] + box["height"] * dy

    async def hover(self, loc, dur=0.55, **kw):
        x, y = await self._center(loc, **kw)
        await self.move(x, y, dur)

    async def click(self, loc, dur=0.55, nav=False, **kw):
        await self.hover(loc, dur, **kw)
        await self.pause(0.18)
        if nav:
            async with self.page.expect_navigation(wait_until="load"):
                await self.page.mouse.down()
                await self.page.mouse.up()
            await self.after_nav()
        else:
            await self.page.mouse.down()
            await self.pause(0.05)
            await self.page.mouse.up()

    async def after_nav(self):
        try:
            await self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        await self.pause(0.35)

    async def type(self, loc, text, cps=24, click=True):
        if click:
            await self.click(loc)
        else:
            await loc.first.focus()
        await self.page.keyboard.type(text, delay=0 if DRY else 1000 / cps)

    async def fill(self, loc, text, dur=0.45):
        await self.hover(loc, dur)
        await loc.first.fill(text)

    async def select(self, loc, dur=0.5, **option):
        await self.hover(loc, dur)
        await self.pause(0.15)
        await loc.first.select_option(**option)

    # --- aylantirish ---
    async def scroll_to(self, y, dur=0.9):
        await self.page.evaluate("""([y,d]) => new Promise(r => {
            const s = window.scrollY, max = document.documentElement.scrollHeight - innerHeight;
            const to = Math.max(0, Math.min(y, max)); if (Math.abs(to-s) < 2 || d <= 0) { window.scrollTo(0,to); return r(); }
            const t0 = performance.now();
            function f(t){ const k=Math.min(1,(t-t0)/d); const e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2;
              window.scrollTo(0, s+(to-s)*e); if(k<1) requestAnimationFrame(f); else r(); }
            requestAnimationFrame(f); })""", [y, 0 if DRY else dur * 1000])

    async def scroll_by(self, dy, dur=0.9):
        y = await self.page.evaluate("window.scrollY")
        await self.scroll_to(y + dy, dur)

    async def scroll_into(self, loc, where=0.3, dur=0.9):
        """Elementni ekranning `where` qismiga (0 — tepa) olib keladi."""
        box = await loc.first.bounding_box()
        y = await self.page.evaluate("window.scrollY")
        await self.scroll_to(y + box["y"] - VH * where, dur)

    async def ensure_visible(self, loc):
        loc = loc.first
        box = await loc.bounding_box()
        if box is None:
            await loc.scroll_into_view_if_needed()
            return
        fixed = await loc.evaluate("""el => { for (let n = el; n; n = n.parentElement) {
            const p = getComputedStyle(n).position; if (p === 'fixed' || p === 'sticky') return true; } return false; }""")
        if fixed:
            await loc.scroll_into_view_if_needed()
            return
        if box["y"] < 70 or box["y"] + box["height"] > VH - 20:
            await self.scroll_into(loc, 0.35, 0.7)

    # --- ajratib ko'rsatish ---
    async def highlight(self, *locs, pad=6, radius=14):
        boxes = [await loc.first.bounding_box() for loc in locs]
        x1 = min(b["x"] for b in boxes) - pad
        y1 = min(b["y"] for b in boxes) - pad
        x2 = max(b["x"] + b["width"] for b in boxes) + pad
        y2 = max(b["y"] + b["height"] for b in boxes) + pad
        await self.page.evaluate("""([x,y,w,h,r]) => { const d=document.createElement('div'); d.className='__hl';
            Object.assign(d.style,{left:x+'px',top:y+'px',width:w+'px',height:h+'px',borderRadius:r+'px'});
            document.body.appendChild(d); }""", [x1, y1, x2 - x1, y2 - y1, radius])

    async def clear(self):
        await self.page.evaluate("document.querySelectorAll('.__hl').forEach(e=>e.remove())")

    def side(self, text):
        return self.page.locator(".app-sidebar a.nav-link", has_text=text)


# --------------------------------------------------------------- montaj ---
def build_video(scenes, out: Path, subs=True, fps=30):
    """Sahnalarni ketma-ket ulaydi: kadrlar (o'zgaruvchan davomiylik) + ovoz + subtitr."""
    work = BUILD / "assemble"
    work.mkdir(parents=True, exist_ok=True)
    lines, audio, cues = ["ffconcat version 1.0"], [], []
    offset = 0.0
    last_file = None
    for sc in scenes:
        frames = sc["frames"]
        t0, t1 = sc["t_start"], sc["t_end"]
        fdir = BUILD / "frames" / sc["name"]
        for i, (t, name) in enumerate(frames):
            nxt = frames[i + 1][0] if i + 1 < len(frames) else t1
            start = max(t, t0)
            dur = max(0.0, nxt - start)
            if dur <= 0:
                continue
            last_file = (fdir / name).as_posix()
            lines += [f"file '{last_file}'", f"duration {dur:.4f}"]
        for a in sc["audio"]:
            at = offset + (a["t"] - t0)
            audio.append((a["path"], at))
            cues += make_cues(a["words"], at, text=a.get("text"))
        offset += t1 - t0
    lines.append(f"file '{last_file}'")
    (work / "frames.txt").write_text("\n".join(lines), encoding="utf-8")
    total = offset

    # ovoz: har bir jumla o'z vaqtiga qo'yiladi
    inputs, parts = [], []
    for i, (path, at) in enumerate(audio):
        inputs += ["-i", path]
        ms = max(0, int(at * 1000))
        parts.append(f"[{i}:a]aresample=48000,adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(audio)))
    parts.append(f"{mix}amix=inputs={len(audio)}:normalize=0:dropout_transition=0,apad,atrim=0:{total:.3f},"
                 f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]")
    (work / "audio_filter.txt").write_text(";\n".join(parts), encoding="utf-8")
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *inputs,
                    "-/filter_complex", str(work / "audio_filter.txt"), "-map", "[aout]",
                    "-ac", "2", "-c:a", "pcm_s16le", str(work / "audio.wav")], check=True)

    write_ass(cues, work / "subs.ass")
    write_srt(cues, out.with_suffix(".srt"))
    fonts = work / "fonts"
    fonts.mkdir(exist_ok=True)
    for f in ("segoeui.ttf", "segoeuib.ttf"):
        if not (fonts / f).exists():
            shutil.copy(f"C:/Windows/Fonts/{f}", fonts / f)
    vf = (f"fps={fps},scale={int(VW * DSF)}:{int(VH * DSF)}:flags=lanczos:out_color_matrix=bt709:out_range=tv,"
          f"format=yuv420p")
    variants = [(out, True), (out.with_name(out.stem + "_subtitrsiz.mp4"), False)] if subs else [(out, False)]
    # Kompyuterda bo'sh xotira kam bo'lishi mumkin: avval yengil sozlama, xato bo'lsa — yanada yengilroq
    attempts = [("fast", "3", "12"), ("veryfast", "2", "8"), ("veryfast", "1", "4"), ("veryfast", "1", "4")]
    for path, burn in variants:
        filt = vf + (",subtitles=subs.ass:fontsdir=fonts" if burn else "")
        for n, (preset, threads, look) in enumerate(attempts):
            r = subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                                "-i", "frames.txt", "-i", "audio.wav", "-vf", filt, "-filter_threads", "1",
                                "-c:v", "libx264", "-preset", preset, "-threads", threads,
                                "-x264-params", f"rc-lookahead={look}", "-crf", "20", "-colorspace", "bt709",
                                "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
                                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                                "-t", f"{total:.3f}", str(path.resolve())], cwd=work, capture_output=True, text=True)
            if r.returncode == 0:
                break
            print(f"  kodlash xatosi ({preset}/{threads}): {r.stderr.strip().splitlines()[:1]} — qayta urinish",
                  file=sys.stderr)
            time.sleep(5)
        else:
            raise RuntimeError(f"video kodlanmadi: {path.name}")
    return total, len(cues)


def with_punct(words, text):
    """edge-tts so'zlarini asl matndagi tinish belgilari bilan tiklaydi («Kirish», bosing. va h.k.)."""
    starts, pos = [], 0
    for w in words:
        i = text.find(w["w"], pos)
        i = pos if i < 0 else i
        pos = i + len(w["w"])
        while i > 0 and text[i - 1] in "«“(\"‘'":
            i -= 1
        starts.append(i)
    out = []
    for k, w in enumerate(words):
        end = starts[k + 1] if k + 1 < len(words) else len(text)
        out.append({**w, "w": text[starts[k]:end].strip() or w["w"]})
    return out


def make_cues(words, at, max_chars=64, text=None):
    if text:
        words = with_punct(words, text)
    cues, cur = [], []

    def flush():
        if cur:
            start = at + cur[0]["t"]
            end = at + cur[-1]["t"] + cur[-1]["d"] + 0.25
            cues.append([start, end, " ".join(w["w"] for w in cur)])
            cur.clear()

    for w in words:
        if cur and len(" ".join(x["w"] for x in cur + [w])) > max_chars:
            flush()
        cur.append(w)
        if re.search(r"[.!?]$", w["w"]):
            flush()
    flush()
    # matndagi tinish belgilarini so'zlarga qaytarish shart emas: edge-tts so'zni tinish belgisiz qaytaradi
    for i in range(len(cues) - 1):
        cues[i][1] = min(cues[i][1], cues[i + 1][0] - 0.02)
    return cues


def _ts(t, sep=","):
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s % 1) * 1000)):03d}"


def write_srt(cues, path):
    out = []
    for i, (a, b, text) in enumerate(cues, 1):
        out += [str(i), f"{_ts(a)} --> {_ts(b)}", text, ""]
    path.write_text("\n".join(out), encoding="utf-8")


def write_ass(cues, path):
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Segoe UI,40,&H00FFFFFF,&H00FFFFFF,&H40000000,&H00000000,0,0,0,0,100,100,0,0,3,12,0,2,200,200,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    for a, b, text in cues:
        cs = lambda t: _ts(t, ".")[:-1]  # noqa: E731  (ASS: santisekund)
        rows.append(f"Dialogue: 0,{cs(a)[1:]},{cs(b)[1:]},Default,,0,0,0,,{text}")
    path.write_text(head + "\n".join(rows) + "\n", encoding="utf-8-sig")
