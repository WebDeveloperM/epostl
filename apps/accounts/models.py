from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.files import random_upload_name


class Role(models.Model):
    """Foydalanuvchi rollari (roles jadvali)."""

    class Code(models.TextChoices):
        ADMIN = "admin", _("Administrator")
        MENTOR = "mentor", _("Ustoz")
        STUDENT = "student", _("Talaba")

    code = models.CharField(_("Kod"), max_length=20, choices=Code.choices, unique=True)
    name = models.CharField(_("Nomi"), max_length=100)
    description = models.TextField(_("Tavsif"), blank=True)

    class Meta:
        db_table = "roles"
        ordering = ["id"]
        verbose_name = _("Rol")
        verbose_name_plural = _("Rollar")

    def __str__(self):
        return str(self.label)

    @property
    def label(self):
        """Rol nomi — joriy tilda (bazadagi `name` o‘rniga tarjima qilinadigan kod nomi)."""
        try:
            return self.Code(self.code).label
        except ValueError:
            return self.name


class UserManager(DjangoUserManager):
    def students(self):
        return self.filter(role__code=Role.Code.STUDENT)

    def mentors(self):
        return self.filter(role__code=Role.Code.MENTOR)

    def admins(self):
        return self.filter(Q(role__code=Role.Code.ADMIN) | Q(is_superuser=True))


def avatar_upload_to(instance, filename):
    return random_upload_name("avatars", filename)


phone_validator = RegexValidator(
    r"^\+?[0-9\s\-()]{7,20}$", _("Telefon raqami noto‘g‘ri. Masalan: +998 90 123 45 67")
)


class User(AbstractUser):
    """Platforma foydalanuvchisi (Custom User Model)."""

    middle_name = models.CharField(_("Otasining ismi"), max_length=150, blank=True)
    email = models.EmailField(_("Elektron pochta"), blank=True)
    phone = models.CharField(_("Telefon raqami"), max_length=20, blank=True, validators=[phone_validator])
    avatar = models.ImageField(
        _("Profil rasmi"), upload_to=avatar_upload_to, blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png"])],
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True,
                             related_name="users", verbose_name=_("Rol"))
    group = models.ForeignKey("organization.StudyGroup", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="students", verbose_name=_("Guruh"))
    department = models.ForeignKey("organization.Department", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="staff", verbose_name=_("Kafedra"))
    external_id = models.CharField(_("Talaba / xodim ID"), max_length=50, blank=True)
    must_change_password = models.BooleanField(_("Parolni o‘zgartirish talab etiladi"), default=False)
    language = models.CharField(_("Til"), max_length=5, choices=settings.LANGUAGES,
                                default=settings.LANGUAGE_CODE)

    objects = UserManager()

    class Meta:
        db_table = "users"
        ordering = ["last_name", "first_name"]
        verbose_name = _("Foydalanuvchi")
        verbose_name_plural = _("Foydalanuvchilar")
        constraints = [
            models.UniqueConstraint(fields=["email"], condition=~Q(email=""), name="uniq_user_email"),
            models.UniqueConstraint(fields=["external_id"], condition=~Q(external_id=""),
                                    name="uniq_user_external_id"),
        ]

    def __str__(self):
        return self.full_name or self.username

    # --- F.I.Sh. ---
    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.last_name, self.first_name, self.middle_name) if p).strip()

    @property
    def short_name(self) -> str:
        if self.last_name and self.first_name:
            return f"{self.last_name} {self.first_name[0]}."
        return self.full_name or self.username

    def get_full_name(self):
        return self.full_name

    # --- Rol ---
    @property
    def role_code(self) -> str:
        if self.role_id:
            return self.role.code
        return Role.Code.ADMIN if self.is_superuser else ""

    @property
    def role_label(self) -> str:
        if self.role_id:
            return str(self.role.label)
        return str(Role.Code.ADMIN.label) if self.is_superuser else "—"

    @property
    def is_student(self) -> bool:
        return self.role_code == Role.Code.STUDENT

    @property
    def is_mentor(self) -> bool:
        return self.role_code == Role.Code.MENTOR

    @property
    def is_platform_admin(self) -> bool:
        return self.role_code == Role.Code.ADMIN

    # --- Tashkiliy tuzilma (normallashtirilgan: guruh -> yo‘nalish -> fakultet) ---
    @property
    def direction(self):
        return self.group.direction if self.group_id else None

    @property
    def faculty(self):
        if self.group_id:
            return self.group.direction.faculty
        if self.department_id:
            return self.department.faculty
        return None


class MentorAssignment(models.Model):
    """Ustozni talabaga yoki butun guruhga biriktirish (mentor_assignments)."""

    mentor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="mentee_links", verbose_name=_("Ustoz"))
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="mentor_links", verbose_name=_("Talaba"))
    group = models.ForeignKey("organization.StudyGroup", on_delete=models.CASCADE, null=True, blank=True,
                              related_name="mentor_links", verbose_name=_("Guruh"))
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="+", verbose_name=_("Biriktirgan"))
    start_date = models.DateField(_("Boshlanish sanasi"), default=timezone.localdate)
    end_date = models.DateField(_("Tugash sanasi"), null=True, blank=True)
    is_active = models.BooleanField(_("Faol"), default=True)
    note = models.CharField(_("Izoh"), max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mentor_assignments"
        ordering = ["-is_active", "-created_at"]
        verbose_name = _("Ustoz biriktiruvi")
        verbose_name_plural = _("Ustoz biriktiruvlari")
        constraints = [
            models.CheckConstraint(
                condition=(Q(student__isnull=False, group__isnull=True)
                           | Q(student__isnull=True, group__isnull=False)),
                name="mentor_assignment_single_target",
            ),
            models.UniqueConstraint(fields=["mentor", "student"],
                                    condition=Q(is_active=True, student__isnull=False),
                                    name="uniq_active_mentor_student"),
            models.UniqueConstraint(fields=["mentor", "group"],
                                    condition=Q(is_active=True, group__isnull=False),
                                    name="uniq_active_mentor_group"),
        ]

    def __str__(self):
        return f"{self.mentor} → {self.target}"

    @property
    def target(self):
        return self.student or self.group
