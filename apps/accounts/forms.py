from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.forms import BootstrapFormMixin, DateInput
from apps.core.utils import client_ip
from apps.organization.models import Department, Faculty, StudyGroup

from .models import MentorAssignment, Role, User

AVATAR_MAX_BYTES = 5 * 1024 * 1024


def _clean_avatar(form):
    avatar = form.cleaned_data.get("avatar")
    if avatar and hasattr(avatar, "size") and avatar.size > AVATAR_MAX_BYTES:
        raise ValidationError(_("Profil rasmi 5 MB dan oshmasligi kerak."))
    return avatar


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    """Kirish formasi: urinishlar soni cheklangan (brute-force himoyasi)."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": _("Login yoki parol noto‘g‘ri."),
        "inactive": _("Hisobingiz bloklangan. Administrator bilan bog‘laning."),
        "locked": _("Juda ko‘p muvaffaqiyatsiz urinish. %(minutes)s daqiqadan so‘ng qayta urinib ko‘ring."),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Login")
        self.fields["username"].widget.attrs.update({"placeholder": _("Login"), "autofocus": True})
        self.fields["password"].widget.attrs.update({"placeholder": _("Parol")})

    def _throttle_key(self):
        username = (self.data.get("username") or "").strip().lower()[:150]
        return f"login-fail:{client_ip(self.request)}:{username}"

    def clean(self):
        key = self._throttle_key()
        if cache.get(key, 0) >= settings.LOGIN_MAX_ATTEMPTS:
            raise ValidationError(
                self.error_messages["locked"], code="locked",
                params={"minutes": max(1, settings.LOGIN_LOCKOUT_SECONDS // 60)},
            )
        try:
            cleaned = super().clean()
        except ValidationError:
            cache.add(key, 0, settings.LOGIN_LOCKOUT_SECONDS)
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, settings.LOGIN_LOCKOUT_SECONDS)
            raise
        cache.delete(key)
        return cleaned


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["email", "phone", "avatar"]
        widgets = {"avatar": forms.ClearableFileInput(attrs={"accept": ".jpg,.jpeg,.png"})}

    def clean_avatar(self):
        return _clean_avatar(self)

    def clean_email(self):
        email = self.cleaned_data.get("email", "")
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_("Bu email boshqa foydalanuvchiga tegishli."))
        return email


class UserAdminForm(BootstrapFormMixin, forms.ModelForm):
    """Administrator uchun foydalanuvchi yaratish/tahrirlash formasi."""

    password1 = forms.CharField(label=_("Parol"), required=False, strip=False,
                                widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label=_("Parolni tasdiqlang"), required=False, strip=False,
                                widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}))

    class Meta:
        model = User
        fields = [
            "last_name", "first_name", "middle_name", "username", "email", "phone", "avatar",
            "role", "group", "department", "external_id", "is_active", "must_change_password",
        ]
        widgets = {"avatar": forms.ClearableFileInput(attrs={"accept": ".jpg,.jpeg,.png"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("last_name", "first_name", "role"):
            self.fields[name].required = True
        self.fields["username"].label = _("Login")
        self.fields["group"].queryset = StudyGroup.objects.filter(is_active=True).select_related("direction")
        self.fields["department"].queryset = Department.objects.filter(is_active=True).select_related("faculty")
        self.fields["group"].help_text = _("Talabalar uchun majburiy")
        self.fields["department"].help_text = _("Ustoz va xodimlar uchun")
        if self.instance.pk:
            self.fields["password1"].label = _("Yangi parol")
            self.fields["password1"].help_text = _("O‘zgartirmaslik uchun bo‘sh qoldiring")
        else:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
            self.fields["must_change_password"].initial = True

    def clean_avatar(self):
        return _clean_avatar(self)

    def clean_email(self):
        email = self.cleaned_data.get("email", "")
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_("Bu email boshqa foydalanuvchiga tegishli."))
        return email

    def clean_external_id(self):
        value = self.cleaned_data.get("external_id", "").strip()
        if value and User.objects.filter(external_id__iexact=value).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_("Bu ID raqam boshqa foydalanuvchiga tegishli."))
        return value

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        if role and role.code == Role.Code.STUDENT and not cleaned.get("group"):
            self.add_error("group", _("Talaba uchun guruhni tanlang."))
        if role and role.code != Role.Code.STUDENT:
            cleaned["group"] = None
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", _("Parollar mos kelmadi."))
            else:
                probe = self.instance if self.instance.pk else User(
                    username=cleaned.get("username", ""), first_name=cleaned.get("first_name", ""),
                    last_name=cleaned.get("last_name", ""), email=cleaned.get("email", ""))
                try:
                    validate_password(p1, probe)
                except ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password1"):
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(label=_("Qidiruv"), required=False,
                        widget=forms.TextInput(attrs={"placeholder": _("F.I.Sh., login, email, ID...")}))
    role = forms.ModelChoiceField(label=_("Rol"), queryset=Role.objects.all(), required=False,
                                  empty_label=_("Barcha rollar"))
    faculty = forms.ModelChoiceField(label=_("Fakultet"), queryset=Faculty.objects.all(), required=False,
                                     empty_label=_("Barcha fakultetlar"))
    group = forms.ModelChoiceField(label=_("Guruh"), queryset=StudyGroup.objects.all(), required=False,
                                   empty_label=_("Barcha guruhlar"))
    status = forms.ChoiceField(label=_("Holat"), required=False,
                               choices=[("", _("Barchasi")), ("active", _("Faol")), ("blocked", _("Bloklangan"))])


class UserImportForm(BootstrapFormMixin, forms.Form):
    file = forms.FileField(label=_("Excel fayl (.xlsx)"),
                           widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}))
    skip_invalid = forms.BooleanField(
        label=_("Xatoli qatorlarni o‘tkazib yuborib, qolganlarini import qilish"), required=False)

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".xlsx"):
            raise ValidationError(_("Faqat .xlsx formatidagi fayl qabul qilinadi."))
        if f.size > 10 * 1024 * 1024:
            raise ValidationError(_("Fayl hajmi 10 MB dan oshmasligi kerak."))
        f.seek(0)
        if f.read(4) != b"PK\x03\x04":
            raise ValidationError(_("Fayl Excel (.xlsx) formatida emas."))
        f.seek(0)
        return f


class MentorAssignmentForm(BootstrapFormMixin, forms.ModelForm):
    TARGET_CHOICES = [("student", _("Talabaga")), ("group", _("Guruhga"))]
    target_type = forms.ChoiceField(label=_("Biriktirish turi"), choices=TARGET_CHOICES,
                                    widget=forms.RadioSelect, initial="student")

    class Meta:
        model = MentorAssignment
        fields = ["mentor", "target_type", "student", "group", "start_date", "end_date", "note"]
        widgets = {"start_date": DateInput(), "end_date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mentor"].queryset = User.objects.mentors().filter(is_active=True)
        self.fields["student"].queryset = User.objects.students().filter(is_active=True).select_related("group")
        self.fields["group"].queryset = StudyGroup.objects.filter(is_active=True)
        self.fields["student"].label_from_instance = lambda u: f"{u.full_name} ({u.group or '—'})"

    def clean(self):
        cleaned = super().clean()
        target_type = cleaned.get("target_type")
        if target_type == "student":
            cleaned["group"] = None
            if not cleaned.get("student"):
                self.add_error("student", _("Talabani tanlang."))
        else:
            cleaned["student"] = None
            if not cleaned.get("group"):
                self.add_error("group", _("Guruhni tanlang."))
        mentor = cleaned.get("mentor")
        if mentor and not self.errors:
            exists = MentorAssignment.objects.filter(
                mentor=mentor, is_active=True,
                student=cleaned.get("student"), group=cleaned.get("group"),
            ).exists()
            if exists:
                raise ValidationError(_("Bu biriktiruv allaqachon mavjud va faol."))
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", _("Tugash sanasi boshlanish sanasidan oldin bo‘lishi mumkin emas."))
        return cleaned

    def _post_clean(self):
        # target_type bo‘yicha tozalangan qiymatlarni instance'ga o‘tkazamiz
        self.instance.student = self.cleaned_data.get("student")
        self.instance.group = self.cleaned_data.get("group")
        super()._post_clean()
