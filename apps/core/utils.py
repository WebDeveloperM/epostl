import re
from urllib.parse import urlsplit

from django.conf import settings
from django.utils.html import format_html


def client_ip(request) -> str | None:
    if request is None:
        return None
    if settings.USE_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()[:45] or None
    return request.META.get("REMOTE_ADDR") or None


def percent(value, total, digits=1):
    if not total:
        return None
    return round(float(value) * 100 / float(total), digits)


def tr(value):
    """Bazadagi standart (seed) nomlarni — kompetensiya, mezon, savol — joriy tilga o‘giradi.

    Tarjima kataloglarida bo‘lmagan (administrator o‘zi yozgan) matn o‘zgarishsiz qaytadi.
    """
    from django.utils.translation import gettext

    return gettext(value) if value else value


def safe_next(request, default: str) -> str:
    """POST/GET dagi `next` manzilini faqat shu sayt ichida bo‘lsa qaytaradi (open redirect himoyasi)."""
    from django.utils.http import url_has_allowed_host_and_scheme

    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                  require_https=request.is_secure()):
        return target
    return default


TELEGRAM_HOSTS = {"t.me", "telegram.me", "telegram.dog"}


def telegram_url(value) -> str:
    """`.env` dagi qiymatni Telegram havolasiga aylantiradi; yaroqsiz bo‘lsa — bo‘sh satr.

    Qabul qilinadi: `https://t.me/username`, `t.me/username`, `@username`, `username`.
    Faqat http(s) va Telegram domenlari: `javascript:` yoki begona sayt havolasi hech qachon chiqmaydi.
    """
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("@"):
        value = "https://t.me/" + value[1:]
    elif re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", value):
        value = "https://t.me/" + value
    elif re.match(r"(?i)(t\.me|telegram\.me|telegram\.dog)/", value):
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or (parts.hostname or "").lower() not in TELEGRAM_HOSTS:
        return ""
    return value


def admin_link():
    """«Administratorga» so‘zi: Telegram havolasi sozlangan bo‘lsa — havola (yangi oynada), aks holda oddiy matn."""
    from django.utils.translation import gettext

    text = gettext("Administratorga")
    url = telegram_url(getattr(settings, "ADMIN_TELEGRAM_URL", ""))
    if not url:
        return text
    return format_html('<a class="admin-link" href="{}" target="_blank" rel="noopener noreferrer">'
                       '<i class="bi bi-telegram" aria-hidden="true"></i> {}</a>', url, text)
