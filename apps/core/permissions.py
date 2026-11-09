"""
Role-Based Access Control (RBAC).

Rollar: administrator, ustoz (mentor), talaba. View'lar uchun mixin'lar va
funksional view'lar uchun dekorator.  Obyekt darajasidagi ruxsatlar har bir
ilovaning `services.py` faylidagi `visible_*` / `can_*` funksiyalarida
tekshiriladi.
"""
from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

ADMIN = "admin"
MENTOR = "mentor"
STUDENT = "student"


def role_of(user) -> str:
    if not user or not user.is_authenticated:
        return ""
    return user.role_code


def has_role(user, *roles: str) -> bool:
    return role_of(user) in roles


class RoleRequiredMixin(LoginRequiredMixin):
    """Faqat ko‘rsatilgan rollarga ruxsat beradi."""

    allowed_roles: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.allowed_roles and role_of(request.user) not in self.allowed_roles:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (ADMIN,)


class MentorRequiredMixin(RoleRequiredMixin):
    allowed_roles = (MENTOR,)


class StudentRequiredMixin(RoleRequiredMixin):
    allowed_roles = (STUDENT,)


class StaffRequiredMixin(RoleRequiredMixin):
    """Administrator yoki ustoz."""

    allowed_roles = (ADMIN, MENTOR)


def role_required(*roles: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if roles and role_of(request.user) not in roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
