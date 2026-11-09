from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Administrator yaratgan/import qilgan foydalanuvchini birinchi kirishda
    parolni almashtirishga majbur qiladi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.must_change_password:
            allowed = {reverse("accounts:password_change"), reverse("accounts:logout"), reverse("set_language")}
            path = request.path
            if path not in allowed and not path.startswith(settings.STATIC_URL):
                return redirect("accounts:password_change")
        return self.get_response(request)
