from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Faculty(models.Model):
    name = models.CharField(_("Nomi"), max_length=255, unique=True)
    short_name = models.CharField(_("Qisqa nomi"), max_length=50, blank=True)
    is_active = models.BooleanField(_("Faol"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "faculties"
        ordering = ["name"]
        verbose_name = _("Fakultet")
        verbose_name_plural = _("Fakultetlar")

    def __str__(self):
        return self.short_name or self.name


class Department(models.Model):
    """Kafedra."""

    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name="departments",
                                verbose_name=_("Fakultet"))
    name = models.CharField(_("Nomi"), max_length=255)
    is_active = models.BooleanField(_("Faol"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "departments"
        ordering = ["faculty__name", "name"]
        verbose_name = _("Kafedra")
        verbose_name_plural = _("Kafedralar")
        constraints = [
            models.UniqueConstraint(fields=["faculty", "name"], name="uniq_department_per_faculty"),
        ]

    def __str__(self):
        return self.name


class Direction(models.Model):
    """Ta’lim yo‘nalishi."""

    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name="directions",
                                verbose_name=_("Fakultet"))
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="directions", verbose_name=_("Kafedra"))
    code = models.CharField(_("Shifr"), max_length=30, unique=True)
    name = models.CharField(_("Nomi"), max_length=255)
    is_active = models.BooleanField(_("Faol"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "directions"
        ordering = ["code"]
        verbose_name = _("Ta’lim yo‘nalishi")
        verbose_name_plural = _("Ta’lim yo‘nalishlari")

    def __str__(self):
        return f"{self.code} — {self.name}"


class StudyGroup(models.Model):
    """Talabalar guruhi."""

    direction = models.ForeignKey(Direction, on_delete=models.PROTECT, related_name="groups",
                                  verbose_name=_("Yo‘nalish"))
    name = models.CharField(_("Guruh nomi"), max_length=50, unique=True)
    course = models.PositiveSmallIntegerField(
        _("Kurs"), default=1, validators=[MinValueValidator(1), MaxValueValidator(6)]
    )
    academic_year = models.CharField(_("O‘quv yili"), max_length=9, blank=True, help_text="2025-2026")
    is_active = models.BooleanField(_("Faol"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "groups"
        ordering = ["name"]
        verbose_name = _("Guruh")
        verbose_name_plural = _("Guruhlar")

    def __str__(self):
        return self.name

    @property
    def faculty(self):
        return self.direction.faculty
