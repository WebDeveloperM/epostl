from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Role, User


@receiver(post_save, sender=User)
def superuser_gets_admin_role(sender, instance, created, **kwargs):
    """`createsuperuser` bilan yaratilgan foydalanuvchiga administrator rolini beradi."""
    if created and instance.is_superuser and not instance.role_id:
        role = Role.objects.filter(code=Role.Code.ADMIN).first()
        if role:
            User.objects.filter(pk=instance.pk).update(role=role)
            instance.role = role


@receiver(user_logged_in)
def remember_language_on_login(sender, request, user, **kwargs):
    """Kirish sahifasida tanlangan til foydalanuvchi profiliga ham yoziladi
    (bildirishnomalar va xatlar shu tilda yuboriladi)."""
    chosen = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME) if request is not None else None
    valid = {code for code, _name in settings.LANGUAGES}
    if chosen in valid and user.language != chosen:
        User.objects.filter(pk=user.pk).update(language=chosen)
        user.language = chosen
