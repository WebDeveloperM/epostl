from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.utils import tr


class Competency(models.Model):
    """Pedagogik kompetensiya."""

    code = models.SlugField(_("Kod"), max_length=50, unique=True)
    name = models.CharField(_("Nomi"), max_length=255)
    description = models.TextField(_("Tavsif"), blank=True)
    order = models.PositiveSmallIntegerField(_("Tartib"), default=0)
    is_active = models.BooleanField(_("Faol"), default=True)

    class Meta:
        db_table = "competencies"
        ordering = ["order", "name"]
        verbose_name = _("Kompetensiya")
        verbose_name_plural = _("Kompetensiyalar")

    def __str__(self):
        return tr(self.name)


class AssessmentCriterion(models.Model):
    """Baholash mezoni (administrator o‘zgartirishi va yangisini qo‘shishi mumkin)."""

    competency = models.ForeignKey(Competency, on_delete=models.PROTECT, null=True, blank=True,
                                   related_name="criteria", verbose_name=_("Kompetensiya"))
    name = models.CharField(_("Mezon nomi"), max_length=255)
    description = models.TextField(_("Tavsif"), blank=True)
    max_score = models.PositiveSmallIntegerField(
        _("Maksimal ball"), default=20, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    order = models.PositiveSmallIntegerField(_("Tartib"), default=0)
    is_active = models.BooleanField(_("Faol"), default=True)

    class Meta:
        db_table = "assessment_criteria"
        ordering = ["order", "name"]
        verbose_name = _("Baholash mezoni")
        verbose_name_plural = _("Baholash mezonlari")

    def __str__(self):
        return f"{tr(self.name)} ({self.max_score})"
