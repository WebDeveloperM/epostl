from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.templatetags.static import static
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.audit.services import log_action
from apps.core.files import protected_file_response
from apps.core.permissions import AdminRequiredMixin
from apps.core.utils import safe_next

from . import services
from .forms import (LoginForm, MentorAssignmentForm, ProfileForm, StyledPasswordChangeForm,
                    UserAdminForm, UserFilterForm, UserImportForm)
from .models import MentorAssignment, Role, User


# --- Autentifikatsiya -----------------------------------------------------
class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    pass


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.user
        if user.must_change_password:
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
        update_session_auth_hash(self.request, user)
        log_action(self.request, "password", user)
        messages.success(self.request, _("Parolingiz muvaffaqiyatli o‘zgartirildi."))
        return response


class ProfileView(LoginRequiredMixin, UpdateView):
    template_name = "accounts/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_student:
            ctx["mentors"] = services.student_mentors(user)
        elif user.is_mentor:
            ctx["students_count"] = services.mentor_students(user).count()
            ctx["groups"] = services.mentor_groups(user)
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request, "update", self.object, changed=form.changed_data)
        messages.success(self.request, _("Profil ma’lumotlari saqlandi."))
        return response


class AvatarView(LoginRequiredMixin, View):
    def get(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        if not target.avatar or not services.can_view_profile(request.user, target):
            return redirect(static("images/avatar.svg"))
        return protected_file_response(request, target.avatar, filename=f"avatar-{target.pk}.png",
                                       content_type="image/jpeg" if target.avatar.name.lower().endswith(("jpg", "jpeg")) else "image/png")


# --- Foydalanuvchilarni boshqarish (administrator) ------------------------
class UserListView(AdminRequiredMixin, ListView):
    template_name = "admin/users/list.html"
    paginate_by = 25
    context_object_name = "users"

    def get_queryset(self):
        qs = User.objects.select_related("role", "group", "department", "group__direction__faculty")
        self.filter_form = UserFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if q := data.get("q"):
                qs = qs.filter(
                    Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
                    | Q(middle_name__icontains=q) | Q(email__icontains=q) | Q(external_id__icontains=q)
                    | Q(phone__icontains=q)
                )
            if data.get("role"):
                qs = qs.filter(role=data["role"])
            if data.get("faculty"):
                f = data["faculty"]
                qs = qs.filter(Q(group__direction__faculty=f) | Q(department__faculty=f))
            if data.get("group"):
                qs = qs.filter(group=data["group"])
            if data.get("status") == "active":
                qs = qs.filter(is_active=True)
            elif data.get("status") == "blocked":
                qs = qs.filter(is_active=False)
        return qs.order_by("last_name", "first_name", "username")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = self.filter_form
        ctx["total"] = User.objects.count()
        counts = User.objects.values("role__code").annotate(n=Count("id")).order_by("role__code")
        ctx["role_counts"] = [
            {"label": Role.Code(c["role__code"]).label if c["role__code"] else _("Rolsiz"), "n": c["n"]}
            for c in counts
        ]
        return ctx


class UserCreateView(AdminRequiredMixin, CreateView):
    template_name = "admin/users/form.html"
    form_class = UserAdminForm

    def form_valid(self, form):
        self.object = form.save()
        log_action(self.request, "create", self.object, role=self.object.role_code)
        messages.success(self.request, _("Foydalanuvchi «%(u)s» yaratildi.") % {"u": self.object})
        return redirect("accounts:user_update", pk=self.object.pk)


class UserUpdateView(AdminRequiredMixin, UpdateView):
    template_name = "admin/users/form.html"
    form_class = UserAdminForm
    model = User
    context_object_name = "target_user"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.object
        if user.is_student:
            ctx["mentor_links"] = MentorAssignment.objects.filter(
                Q(student=user) | Q(group_id=user.group_id, group__isnull=False)
            ).select_related("mentor", "group")
        elif user.is_mentor:
            ctx["mentee_links"] = user.mentee_links.select_related("student", "group")
        return ctx

    def form_valid(self, form):
        old_role = User.objects.get(pk=self.object.pk).role_code
        self.object = form.save()
        extra = {"changed": form.changed_data}
        if old_role != self.object.role_code:
            extra["role"] = f"{old_role} -> {self.object.role_code}"
        log_action(self.request, "update", self.object, **extra)
        messages.success(self.request, _("O‘zgarishlar saqlandi."))
        return redirect("accounts:user_update", pk=self.object.pk)


class UserToggleActiveView(AdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            messages.error(request, _("O‘z hisobingizni bloklay olmaysiz."))
        else:
            services.set_active(request, user, not user.is_active)
            messages.success(request, _("«%(u)s» faollashtirildi.") % {"u": user} if user.is_active
                             else _("«%(u)s» bloklandi.") % {"u": user})
        return redirect(safe_next(request, reverse("accounts:user_list")))


class UserImportView(AdminRequiredMixin, View):
    template_name = "admin/users/import.html"

    def get(self, request):
        return render(request, self.template_name, {"form": UserImportForm(), "columns": services.IMPORT_COLUMNS})

    def post(self, request):
        form = UserImportForm(request.POST, request.FILES)
        ctx = {"form": form, "columns": services.IMPORT_COLUMNS}
        if form.is_valid():
            try:
                result = services.import_users_from_excel(
                    request, form.cleaned_data["file"], skip_invalid=form.cleaned_data["skip_invalid"])
            except ValidationError as exc:
                form.add_error("file", exc)
            else:
                ctx["result"] = result
                if result.applied:
                    messages.success(request, _("%(n)s ta foydalanuvchi import qilindi.") % {"n": len(result.created)})
                else:
                    messages.error(request, _("Faylda xatolar topildi. Hech bir foydalanuvchi qo‘shilmadi."))
        return render(request, self.template_name, ctx)


class UserImportTemplateView(AdminRequiredMixin, View):
    def get(self, request):
        response = HttpResponse(
            services.build_import_template(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="foydalanuvchilar_import_namuna.xlsx"'
        return response


# --- Ustoz biriktiruvlari -------------------------------------------------
class MentorAssignmentListView(AdminRequiredMixin, ListView):
    template_name = "admin/mentor_assignments/list.html"
    paginate_by = 30
    context_object_name = "links"

    def get_queryset(self):
        qs = MentorAssignment.objects.select_related("mentor", "student", "student__group", "group", "assigned_by")
        if mentor_id := self.request.GET.get("mentor"):
            if mentor_id.isdigit():
                qs = qs.filter(mentor_id=mentor_id)
        if q := self.request.GET.get("q", "").strip():
            qs = qs.filter(
                Q(mentor__last_name__icontains=q) | Q(mentor__first_name__icontains=q)
                | Q(student__last_name__icontains=q) | Q(student__first_name__icontains=q)
                | Q(group__name__icontains=q)
            )
        status = self.request.GET.get("status", "active")
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "inactive":
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["mentors"] = User.objects.mentors().filter(is_active=True)
        ctx["status"] = self.request.GET.get("status", "active")
        return ctx


class MentorAssignmentCreateView(AdminRequiredMixin, CreateView):
    template_name = "admin/mentor_assignments/form.html"
    form_class = MentorAssignmentForm

    def get_initial(self):
        initial = super().get_initial()
        for key in ("mentor", "student", "group"):
            if value := self.request.GET.get(key):
                initial[key] = value
        if self.request.GET.get("group"):
            initial["target_type"] = "group"
        return initial

    def form_valid(self, form):
        form.instance.assigned_by = self.request.user
        self.object = form.save()
        log_action(self.request, "assign", self.object)
        messages.success(self.request, _("Ustoz biriktirildi: %(a)s") % {"a": self.object})
        return redirect("accounts:mentor_assignment_list")


class MentorAssignmentToggleView(AdminRequiredMixin, View):
    def post(self, request, pk):
        link = get_object_or_404(MentorAssignment, pk=pk)
        if not link.is_active:
            duplicate = MentorAssignment.objects.filter(
                mentor=link.mentor, student=link.student, group=link.group, is_active=True).exists()
            if duplicate:
                messages.error(request, _("Bunday faol biriktiruv allaqachon mavjud."))
                return redirect("accounts:mentor_assignment_list")
        link.is_active = not link.is_active
        link.save(update_fields=["is_active"])
        log_action(request, "update", link, is_active=link.is_active)
        messages.success(request, _("Biriktiruv holati o‘zgartirildi."))
        return redirect(safe_next(request, reverse("accounts:mentor_assignment_list")))
