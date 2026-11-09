from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .services import log_action


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    log_action(request, "login", user, user=user)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        log_action(request, "logout", user, user=user)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get("username", "")
    user = get_user_model().objects.filter(username=username).first()
    log_action(request, "login_failed", user, message=f"login: {username[:150]}", user=user)
