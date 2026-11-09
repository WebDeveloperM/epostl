from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.utils import tr


class Assessment(models.Model):
    """Baholash natijasi.

    * `BASELINE` — boshlang‘ich baholash (rivojlanish siklining 1-bosqichi),
      ishga bog‘lanmaydi;
    * `WORK` — talabaning ish versiyasi va refleksiyasi bo‘yicha baholash.
    Dastlabki va keyingi natijalar alohida yozuvlar sifatida saqlanadi.
    """

    class Kind(models.TextChoices):
        BASELINE = "baseline", _("Boshlang‘ich baholash")
        WORK = "work", _("Ish bo‘yicha baholash")

    class Decision(models.TextChoices):
        APPROVED = "approved", _("Tasdiqlash")
        REVISION = "revision", _("Qayta ishlashga qaytarish")

    kind = models.CharField(_("Baholash turi"), max_length=20, choices=Kind.choices, default=Kind.WORK)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assessments",
                                verbose_name=_("Talaba"))
    mentor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                               related_name="given_assessments", verbose_name=_("Ustoz"))
    portfolio_version = models.OneToOneField("portfolios.PortfolioVersion", on_delete=models.PROTECT, null=True,
                                             blank=True, related_name="assessment", verbose_name=_("Ish versiyasi"))
    goal = models.ForeignKey("goals.Goal", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="assessments", verbose_name=_("Rivojlanish maqsadi"))
    decision = models.CharField(_("Qaror"), max_length=20, choices=Decision.choices, blank=True)
    total_score = models.PositiveSmallIntegerField(_("Jami ball"), default=0)
    max_score = models.PositiveSmallIntegerField(_("Maksimal ball"), default=0)
    overall_comment = models.TextField(_("Umumiy xulosa"), blank=True)
    created_at = models.DateTimeField(_("Baholangan vaqt"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assessments"
        ordering = ["-created_at"]
        verbose_name = _("Baholash")
        verbose_name_plural = _("Baholash natijalari")
        constraints = [
            models.CheckConstraint(
                condition=(Q(kind="work", portfolio_version__isnull=False)
                           | Q(kind="baseline", portfolio_version__isnull=True)),
                name="assessment_kind_matches_version",
            ),
        ]

    def __str__(self):
        return f"{self.student} — {self.get_kind_display()} ({self.total_score}/{self.max_score})"

    @property
    def percent(self):
        return round(self.total_score * 100 / self.max_score, 1) if self.max_score else None


class AssessmentDetail(models.Model):
    """Har bir mezon bo‘yicha ball, izoh, kamchiliklar va tavsiya."""

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="details")
    criterion = models.ForeignKey("competencies.AssessmentCriterion", on_delete=models.PROTECT,
                                  related_name="details", verbose_name=_("Mezon"))
    score = models.PositiveSmallIntegerField(_("Ball"))
    max_score = models.PositiveSmallIntegerField(_("Maksimal ball (nusxa)"))
    comment = models.TextField(_("Izoh"), blank=True)
    weaknesses = models.TextField(_("Kamchiliklar"), blank=True)
    recommendations = models.TextField(_("Takomillashtirish bo‘yicha tavsiya"), blank=True)

    class Meta:
        db_table = "assessment_details"
        ordering = ["criterion__order", "criterion_id"]
        verbose_name = _("Mezon bo‘yicha baho")
        verbose_name_plural = _("Mezonlar bo‘yicha baholar")
        constraints = [
            models.UniqueConstraint(fields=["assessment", "criterion"], name="uniq_assessment_criterion"),
            models.CheckConstraint(condition=Q(score__lte=models.F("max_score")), name="detail_score_lte_max"),
        ]

    def __str__(self):
        return f"{tr(self.criterion.name)}: {self.score}/{self.max_score}"

    def clean(self):
        if self.score is not None and self.max_score is not None and self.score > self.max_score:
            raise ValidationError({"score": _("Ball maksimal balldan oshmasligi kerak.")})

    @property
    def percent(self):
        return round(self.score * 100 / self.max_score, 1) if self.max_score else None


class MentorFeedback(models.Model):
    """Ustozning ish bo‘yicha izohi va tavsiyalari."""

    class Kind(models.TextChoices):
        COMMENT = "comment", _("Izoh")
        RECOMMENDATION = "recommendation", _("Tavsiya")

    portfolio = models.ForeignKey("portfolios.Portfolio", on_delete=models.CASCADE, related_name="feedback",
                                  verbose_name=_("Ish"))
    version = models.ForeignKey("portfolios.PortfolioVersion", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="feedback", verbose_name=_("Versiya"))
    mentor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="given_feedback",
                               verbose_name=_("Ustoz"))
    kind = models.CharField(_("Turi"), max_length=20, choices=Kind.choices, default=Kind.COMMENT)
    text = models.TextField(_("Matn"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mentor_feedback"
        ordering = ["-created_at"]
        verbose_name = _("Ustoz fikri")
        verbose_name_plural = _("Ustoz fikrlari")

    def __str__(self):
        return f"{self.mentor}: {self.text[:50]}"
