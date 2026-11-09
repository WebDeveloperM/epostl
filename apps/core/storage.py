"""Statik fayllar uchun kesh buzish (cache busting).

Nginx `/static/` ni 30 kunga keshlaydi. Fayl nomi o‘zgarmasa, CSS/JS yangilanganda foydalanuvchining brauzeri
eski nusxani ishlatib yuboradi (masalan, yangi qo‘shilgan uslublar ko‘rinmaydi). Shu sababli har bir
`{% static %}` havolasiga fayl mazmunining qisqa hash'i qo‘shiladi: `/static/css/app.css?v=3fa9c1d2e0`.
Fayl o‘zgarsa — hash o‘zgaradi, brauzer yangisini oladi; o‘zgarmasa — eski kesh ishlayveradi.
"""
import hashlib
import os

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import StaticFilesStorage
from django.core.exceptions import SuspiciousFileOperation


class VersionedStaticFilesStorage(StaticFilesStorage):
    _versions: dict = {}  # fayl yo‘li -> ((mtime, hajm), hash): mazmun faqat fayl o‘zgarganda qayta o‘qiladi

    def _file_path(self, name):
        try:
            path = self.path(name)
        except SuspiciousFileOperation:
            return None
        if os.path.isfile(path):
            return path
        found = finders.find(name)  # collectstatic qilinmagan bo‘lsa (dev, testlar) — manba papkadan
        return found if isinstance(found, str) else None

    def version(self, name) -> str:
        path = self._file_path(name) if name else None
        if not path:
            return ""
        stat = os.stat(path)
        stamp = (stat.st_mtime_ns, stat.st_size)
        cached = self._versions.get(path)
        if cached and cached[0] == stamp:
            return cached[1]
        with open(path, "rb") as fh:
            digest = hashlib.md5(fh.read(), usedforsecurity=False).hexdigest()[:10]
        self._versions[path] = (stamp, digest)
        return digest

    def url(self, name):
        url = super().url(name)
        version = self.version(name)
        return f"{url}?v={version}" if version else url
