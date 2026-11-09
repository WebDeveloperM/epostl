import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import QuerySet
from django.utils import translation

from .models import Notification

logger = logging.getLogger("apps.notifications")


def _text(value, user) -> str:
    """Matn funksiya bo‘lsa, qabul qiluvchining tilida hisoblanadi (har kim o‘z tilida o‘qiydi)."""
    if callable(value):
        language = user.language if user.language in dict(settings.LANGUAGES) else settings.LANGUAGE_CODE
        with translation.override(language):
            return str(value())
    return str(value)


def notify(recipients, *, type, title, message="", url="", actor=None):
    """Bir yoki bir nechta foydalanuvchiga bildirishnoma yuboradi.

    `title` va `message` — oddiy matn yoki argumentsiz funksiya (masalan,
    `lambda: _("...") % {...}`). Funksiya har bir qabul qiluvchining tilida chaqiriladi.

    Elektron pochta orqali yuborish `NOTIFICATIONS_EMAIL_ENABLED=True` bo‘lganda
    yoqiladi (kelajakdagi kengaytma uchun tayyor).
    """
    if recipients is None:
        return []
    if not isinstance(recipients, (list, tuple, set, QuerySet)):
        recipients = [recipients]
    objs = [
        Notification(recipient=r, actor=actor, type=type, title=_text(title, r)[:255],
                     message=_text(message, r), url=url)
        for r in recipients
        if r is not None and (actor is None or r.pk != actor.pk)
    ]
    created = Notification.objects.bulk_create(objs)
    if settings.NOTIFICATIONS_EMAIL_ENABLED:
        _send_emails(created)
    return created


def _send_emails(notifications):
    for n in notifications:
        email = n.recipient.email
        if not email:
            continue
        link = f"{settings.SITE_URL.rstrip('/')}{n.url}" if n.url else settings.SITE_URL
        try:
            send_mail(n.title, f"{n.message}\n\n{link}", settings.DEFAULT_FROM_EMAIL, [email])
            Notification.objects.filter(pk=n.pk).update(emailed=True)
        except Exception:  # pragma: no cover
            logger.exception("Bildirishnoma emailini yuborib bo‘lmadi (id=%s)", n.pk)


def unread_count(user) -> int:
    return Notification.objects.filter(recipient=user, is_read=False).count()
