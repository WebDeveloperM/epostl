from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, UpdateView

from apps.audit.services import log_action

from .forms import SystemSettingsForm
from .landing import landing_content
from .middleware import available_languages
from .models import SystemSettings
from .permissions import AdminRequiredMixin
from .utils import safe_next


class LandingView(TemplateView):
    """Bosh sahifa (hamma uchun ochiq): platforma haqida ma’lumot va kirish tugmasi."""

    template_name = "landing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            system = SystemSettings.get_solo()
        except Exception:  # migratsiyalar qo‘llanmagan bo‘lsa ham sahifa ochilsin
            system = None
        ctx.update(landing_content(system))
        return ctx


class SystemSettingsView(AdminRequiredMixin, UpdateView):
    form_class = SystemSettingsForm
    template_name = "admin/system_settings.html"

    def get_object(self, queryset=None):
        return SystemSettings.get_solo()

    def form_valid(self, form):
        form.save()
        log_action(self.request, "update", form.instance, changed=form.changed_data)
        messages.success(self.request, _("Tizim sozlamalari saqlandi."))
        return redirect("core:settings")


@require_POST
def set_language(request):
    """Interfeys tilini almashtiradi: cookie + (tizimga kirgan bo‘lsa) foydalanuvchi profili."""
    language = request.POST.get("language", "")
    response = redirect(safe_next(request, "/"))
    if language in available_languages():
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME, language, max_age=settings.LANGUAGE_COOKIE_AGE,
            samesite="Lax", secure=settings.SESSION_COOKIE_SECURE,
        )
        user = request.user
        if user.is_authenticated and user.language != language:
            get_user_model().objects.filter(pk=user.pk).update(language=language)
    return response


def error_403(request, exception=None):
    return render(request, "base/error.html", {"code": 403, "title": _("Ruxsat yo‘q"),
                  "message": _("Bu sahifani ko‘rish uchun sizda ruxsat mavjud emas.")}, status=403)


def error_404(request, exception=None):
    return render(request, "base/error.html", {"code": 404, "title": _("Sahifa topilmadi"),
                  "message": _("So‘ralgan sahifa mavjud emas yoki sizga ochiq emas.")}, status=404)


def error_500(request):
    return render(request, "base/error.html", {"code": 500, "title": _("Server xatosi"),
                  "message": _("Kutilmagan xatolik yuz berdi. Iltimos, keyinroq urinib ko‘ring.")}, status=500)
