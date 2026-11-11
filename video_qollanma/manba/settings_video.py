"""Video qo'llanma yozish uchun alohida sozlamalar: asosiy baza va media papkasiga tegmaydi."""
import os
from pathlib import Path

os.environ.setdefault("LOG_DIR", str(Path(__file__).resolve().parent / "data" / "logs"))

from config.settings import *  # noqa: E402,F401,F403

DATA = Path(__file__).resolve().parent / "data"
DATA.mkdir(exist_ok=True)

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(DATA / "video.sqlite3")}}
MEDIA_ROOT = str(DATA / "media")
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
NOTIFICATIONS_EMAIL_ENABLED = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # faqat demo: tez kirish
