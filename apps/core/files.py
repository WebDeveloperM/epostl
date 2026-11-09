"""
Fayllar bilan xavfsiz ishlash:

* yuklangan faylning kengaytmasi, haqiqiy MIME turi (fayl imzosi) va hajmini
  tekshirish;
* fayllarni ochiq URL orqali emas, ruxsat tekshirilgandan keyin uzatish
  (video uchun HTTP Range qo‘llab-quvvatlanadi; production'da nginx
  X-Accel-Redirect ishlatiladi).
"""
from __future__ import annotations

import mimetypes
import os
import re
import uuid
from dataclasses import dataclass
from urllib.parse import quote

import filetype
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

# --- Fayl toifalari -------------------------------------------------------
DOCUMENT = "document"
PRESENTATION = "presentation"
VIDEO = "video"
AUDIO = "audio"
IMAGE = "image"

CATEGORY_LABELS = {
    DOCUMENT: gettext_lazy("Hujjat"),
    PRESENTATION: gettext_lazy("Taqdimot"),
    VIDEO: gettext_lazy("Video"),
    AUDIO: gettext_lazy("Audio"),
    IMAGE: gettext_lazy("Rasm"),
}
CATEGORY_ICONS = {
    DOCUMENT: "bi-file-earmark-text",
    PRESENTATION: "bi-file-earmark-slides",
    VIDEO: "bi-camera-video",
    AUDIO: "bi-music-note-beamed",
    IMAGE: "bi-image",
}

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP = "application/zip"
OLE_MIMES = {"application/msword", "application/vnd.ms-excel", "application/vnd.ms-powerpoint"}
TEXT = None  # imzosiz (matnli) fayllar

# kengaytma -> (toifa, ruxsat etilgan aniqlangan MIME'lar, saqlanadigan MIME)
EXTENSIONS: dict[str, tuple[str, set, str]] = {
    "pdf": (DOCUMENT, {"application/pdf"}, "application/pdf"),
    "doc": (DOCUMENT, OLE_MIMES, "application/msword"),
    "docx": (
        DOCUMENT,
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", ZIP},
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "odt": (DOCUMENT, {"application/vnd.oasis.opendocument.text"}, "application/vnd.oasis.opendocument.text"),
    "rtf": (DOCUMENT, {"application/rtf"}, "application/rtf"),
    "txt": (DOCUMENT, {TEXT}, "text/plain"),
    "xls": (DOCUMENT, OLE_MIMES, "application/vnd.ms-excel"),
    "xlsx": (
        DOCUMENT,
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ZIP},
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    "ppt": (PRESENTATION, OLE_MIMES, "application/vnd.ms-powerpoint"),
    "pptx": (
        PRESENTATION,
        {"application/vnd.openxmlformats-officedocument.presentationml.presentation", ZIP},
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    "odp": (
        PRESENTATION,
        {"application/vnd.oasis.opendocument.presentation"},
        "application/vnd.oasis.opendocument.presentation",
    ),
    "mp4": (VIDEO, {"video/mp4", "video/x-m4v", "video/quicktime"}, "video/mp4"),
    "m4v": (VIDEO, {"video/x-m4v", "video/mp4"}, "video/mp4"),
    "webm": (VIDEO, {"video/webm", "video/x-matroska"}, "video/webm"),
    "mkv": (VIDEO, {"video/x-matroska", "video/webm"}, "video/x-matroska"),
    "mov": (VIDEO, {"video/quicktime", "video/mp4"}, "video/quicktime"),
    "avi": (VIDEO, {"video/x-msvideo"}, "video/x-msvideo"),
    "mp3": (AUDIO, {"audio/mpeg"}, "audio/mpeg"),
    "wav": (AUDIO, {"audio/x-wav", "audio/wav"}, "audio/wav"),
    "m4a": (AUDIO, {"audio/mp4", "video/mp4"}, "audio/mp4"),
    "ogg": (AUDIO, {"audio/ogg"}, "audio/ogg"),
    "jpg": (IMAGE, {"image/jpeg"}, "image/jpeg"),
    "jpeg": (IMAGE, {"image/jpeg"}, "image/jpeg"),
    "png": (IMAGE, {"image/png"}, "image/png"),
}

ALL_CATEGORIES = (DOCUMENT, PRESENTATION, VIDEO, AUDIO, IMAGE)
# Brauzerda to‘g‘ridan-to‘g‘ri ochish xavfsiz bo‘lgan turlar
INLINE_MIME_PREFIXES = ("video/", "audio/", "image/jpeg", "image/png", "application/pdf")


@dataclass
class ValidatedFile:
    original_name: str
    extension: str
    category: str
    mime_type: str
    size: int


def file_extension(name: str) -> str:
    base = os.path.basename(name or "")
    return base.rsplit(".", 1)[-1].lower() if "." in base else ""


def allowed_extensions(categories=ALL_CATEGORIES) -> list[str]:
    from apps.core.models import SystemSettings

    video_ext = SystemSettings.get_solo().video_extensions
    result = []
    for ext, (category, _m, _s) in EXTENSIONS.items():
        if category not in categories:
            continue
        if category == VIDEO and ext not in video_ext:
            continue
        result.append(ext)
    return result


def accept_attribute(categories=ALL_CATEGORIES) -> str:
    return ",".join(f".{ext}" for ext in allowed_extensions(categories))


def _looks_like_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError:
        # Ko‘p baytli belgining o‘rtasida kesilgan bo‘lishi mumkin
        try:
            head[:-4].decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False


def validate_uploaded_file(uploaded, categories=ALL_CATEGORIES) -> ValidatedFile:
    """Kengaytma, haqiqiy MIME turi va hajmni tekshiradi."""
    from apps.core.models import SystemSettings

    conf = SystemSettings.get_solo()
    original_name = os.path.basename(uploaded.name or "")[:255]
    ext = file_extension(original_name)

    if ext not in EXTENSIONS:
        raise ValidationError(
            _("«%(name)s»: bu turdagi faylni yuklashga ruxsat berilmagan.") % {"name": original_name}
        )
    category, allowed_mimes, stored_mime = EXTENSIONS[ext]
    if category not in categories:
        raise ValidationError(
            _("«%(name)s»: bu bo‘limga %(cat)s turidagi fayl yuklab bo‘lmaydi.")
            % {"name": original_name, "cat": CATEGORY_LABELS[category]}
        )
    if category == VIDEO and ext not in conf.video_extensions:
        raise ValidationError(
            _("«%(name)s»: .%(ext)s video formati ruxsat etilmagan. Ruxsat etilganlar: %(allowed)s")
            % {"name": original_name, "ext": ext, "allowed": ", ".join(sorted(conf.video_extensions))}
        )

    limit_mb = conf.max_video_size_mb if category == VIDEO else conf.max_upload_size_mb
    if uploaded.size > limit_mb * 1024 * 1024:
        raise ValidationError(
            _("«%(name)s»: fayl hajmi %(limit)s MB dan oshmasligi kerak.")
            % {"name": original_name, "limit": limit_mb}
        )
    if uploaded.size == 0:
        raise ValidationError(_("«%(name)s»: fayl bo‘sh.") % {"name": original_name})

    uploaded.seek(0)
    head = uploaded.read(8192)
    uploaded.seek(0)
    kind = filetype.guess(head)
    detected = kind.mime if kind else None

    ok = detected in allowed_mimes
    if not ok and allowed_mimes is OLE_MIMES:
        ok = head.startswith(OLE_MAGIC)
    if not ok and TEXT in allowed_mimes:
        ok = detected is None and _looks_like_text(head)
    if not ok:
        raise ValidationError(
            _("«%(name)s»: fayl mazmuni uning kengaytmasiga mos kelmaydi.") % {"name": original_name}
        )

    return ValidatedFile(
        original_name=original_name,
        extension=ext,
        category=category,
        mime_type=stored_mime,
        size=uploaded.size,
    )


def random_upload_name(prefix: str, filename: str) -> str:
    """Taxmin qilib bo‘lmaydigan fayl nomi (path traversal va enumeration'dan himoya)."""
    ext = file_extension(filename)
    suffix = f".{ext}" if ext else ""
    return f"{prefix.strip('/')}/{uuid.uuid4().hex}{suffix}"


# --- Himoyalangan uzatish -------------------------------------------------
RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
CHUNK_SIZE = 64 * 1024


def _range_iterator(path: str, start: int, length: int):
    with open(path, "rb") as fh:
        fh.seek(start)
        remaining = length
        while remaining > 0:
            data = fh.read(min(CHUNK_SIZE, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def protected_file_response(request, field_file, *, filename: str, content_type: str = "",
                            force_download: bool = False):
    """Ruxsat tekshirilgandan keyin chaqiriladi: faylni xavfsiz uzatadi."""
    if not field_file or not field_file.name:
        raise Http404
    content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    as_attachment = force_download or not content_type.startswith(INLINE_MIME_PREFIXES)

    if settings.PROTECTED_MEDIA_USE_X_ACCEL:
        response = HttpResponse(content_type=content_type)
        response["X-Accel-Redirect"] = settings.PROTECTED_MEDIA_INTERNAL_URL + quote(field_file.name)
    else:
        try:
            path = field_file.path
            size = os.path.getsize(path)
        except (FileNotFoundError, NotImplementedError, ValueError):
            raise Http404
        match = RANGE_RE.match(request.META.get("HTTP_RANGE", "").strip())
        if match and (match.group(1) or match.group(2)):
            first, last = match.groups()
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            else:  # oxirgi N bayt
                start = max(size - int(last), 0)
                end = size - 1
            if start >= size or start > end:
                response = HttpResponse(status=416)
                response["Content-Range"] = f"bytes */{size}"
                return response
            length = end - start + 1
            response = StreamingHttpResponse(
                _range_iterator(path, start, length), status=206, content_type=content_type
            )
            response["Content-Range"] = f"bytes {start}-{end}/{size}"
            response["Content-Length"] = str(length)
        else:
            response = FileResponse(open(path, "rb"), content_type=content_type)
        response["Accept-Ranges"] = "bytes"

    response["Content-Disposition"] = content_disposition_header(as_attachment, filename)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response


def human_size(num: int | None) -> str:
    if not num:
        return "0 B"
    size = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
