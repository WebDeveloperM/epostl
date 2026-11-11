"""
Refleksiv portfolio platformasi — Django sozlamalari.

Barcha maxfiy va muhitga bog‘liq qiymatlar `.env` faylidan o‘qiladi
(namuna: `.env.example`).
"""
from pathlib import Path

import environ
from django.contrib.messages import constants as message_constants

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

# --- Asosiy ---------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
# Administratorning Telegram havolasi (landing va kirish sahifasidagi «Administratorga» havolasi), masalan https://t.me/username
ADMIN_TELEGRAM_URL = env("ADMIN_TELEGRAM_URL", default="")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Loyiha ilovalari
    "apps.core",
    "apps.organization",
    "apps.accounts",
    "apps.subjects",
    "apps.competencies",
    "apps.goals",
    "apps.assignments",
    "apps.portfolios",
    "apps.reflections",
    "apps.assessments",
    "apps.analytics",
    "apps.notifications",
    "apps.audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.LanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.platform",
                "apps.notifications.context_processors.notifications",
            ],
        },
    },
]

# --- Ma'lumotlar bazasi (PostgreSQL) --------------------------------------
# DATABASES = {
#      'default': {
#          'ENGINE': 'django.db.backends.postg',
#          'NAME': 'refleksi_db',
#          'USER': 'refleksi_admin',
#          'PASSWORD': 'nilufarDSC1515',
#          'HOST': 'localhost',
#          'PORT': '3306'
#      }
#  }
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["ATOMIC_REQUESTS"] = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Autentifikatsiya -----------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Kirish urinishlarini cheklash (brute-force himoyasi)
LOGIN_MAX_ATTEMPTS = env.int("LOGIN_MAX_ATTEMPTS", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=15 * 60)

SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=8 * 60 * 60)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# --- Xalqarolashtirish ----------------------------------------------------
# Asosiy til — ingliz tili. Tilni almashtirish: yuqori paneldagi «globus» tugmasi.
# Til nomlari tarjima qilinmaydi: har bir til o‘z nomi bilan ko‘rsatiladi.
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("uz", "O‘zbekcha"),
]
LANGUAGE_COOKIE_NAME = "portfolio_language"
LANGUAGE_COOKIE_AGE = 365 * 24 * 60 * 60
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

# --- Statik va media fayllar ----------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Har bir statik havolaga fayl hash'i qo‘shiladi (nginx 30 kun keshlaydi, yangilanish ko‘rinib turishi uchun)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "apps.core.storage.VersionedStaticFilesStorage"},
}

# Media fayllar ochiq URL orqali TARQATILMAYDI. Ular faqat ruxsatni
# tekshiradigan view'lar orqali beriladi (apps.core.files).
# Media files (uploaded course images, certificates, etc.)
MEDIA_URL = 'media/'
# MEDIA_ROOT = os.environ.get('MEDIA_ROOT', BASE_DIR / 'media')
MEDIA_ROOT = '/home/refleksi/public_html/backmanager/media'

# Production'da nginx X-Accel-Redirect orqali uzatish (deploy/nginx.conf)
PROTECTED_MEDIA_USE_X_ACCEL = env.bool("PROTECTED_MEDIA_USE_X_ACCEL", default=False)
PROTECTED_MEDIA_INTERNAL_URL = "/protected-media/"

# Katta fayllar xotirada emas, vaqtinchalik faylda saqlanadi
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 50
# nginx boshqa foydalanuvchi bo‘lsa (masalan, Docker) — 644; aks holda 640
FILE_UPLOAD_PERMISSIONS = int(env("FILE_UPLOAD_PERMISSIONS", default="640").removeprefix("0o"), 8)
FILE_UPLOAD_TEMP_DIR = env("FILE_UPLOAD_TEMP_DIR", default=None)

# --- Xavfsizlik -----------------------------------------------------------
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
USE_X_FORWARDED_FOR = env.bool("USE_X_FORWARDED_FOR", default=False)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    # Faqat HTTPS orqali ishlashda True bo‘lishi shart (lokal Docker/HTTP sinovi uchun False qilinadi)
    SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
    CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)

# --- Kesh -----------------------------------------------------------------
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}

# --- Elektron pochta va bildirishnomalar ----------------------------------
EMAIL_CONFIG = env.email("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@portfolio.local")
NOTIFICATIONS_EMAIL_ENABLED = env.bool("NOTIFICATIONS_EMAIL_ENABLED", default=False)
SITE_URL = env("SITE_URL", default="http://localhost:8000")

# --- Xabarlar (Bootstrap klasslari) ---------------------------------------
MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

# --- Loglar ---------------------------------------------------------------
LOG_DIR = Path(env("LOG_DIR", default=str(BASE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{asctime} [{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "app.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "errors.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
            "level": "ERROR",
            "encoding": "utf-8",
        },
    },
    "root": {"handlers": ["console", "error_file"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console", "error_file"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console", "app_file", "error_file"], "level": "INFO", "propagate": False},
    },
}
