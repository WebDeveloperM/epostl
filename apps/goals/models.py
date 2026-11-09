from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Goal(models.Model):
    """Talabaning pedagogik rivojlanish maqsadi — rivojlanish siklining markazi."""

    class Status(models.TextChoices):
        NEW = "new", _("Yangi")
        IN_PROGRESS = "in_progress", _("Jarayonda")
        COMPLETED = "completed", _("Bajarildi")
        CANCELLED = "cancelled", _("Bekor qilindi")

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goals",
                                verbose_name=_("Talaba"))
    title = models.CharField(_("Maqsad nomi"), max_length=255)
    description = models.TextField(_("Maqsad tavsifi"), blank=True)
    competency = models.ForeignKey("competencies.Competency", on_delete=models.PROTECT, null=True,
                                   related_name="goals", verbose_name=_("Rivojlantiriladigan kompetensiya"))
    start_date = models.DateField(_("Boshlanish sanasi"), default=timezone.localdate)
    target_date = models.DateField(_("Rejalashtirilgan tugash sanasi"))
    expected_outcome = models.TextField(_("Kutilayotgan natija"))
    status = models.CharField(_("Holati"), max_length=20, choices=Status.choices, default=Status.NEW,
                              db_index=True)
    completed_at = models.DateTimeField(_("Bajarilgan vaqt"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "goals"
        ordering = ["-created_at"]
        verbose_name = _("Rivojlanish maqsadi")
        verbose_name_plural = _("Rivojlanish maqsadlari")
        constraints = [
            models.CheckConstraint(condition=models.Q(target_date__gte=models.F("start_date")),
                                   name="goal_dates_order"),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if self.start_date and self.target_date and self.target_date < self.start_date:
            raise ValidationError({"target_date": _("Tugash sanasi boshlanish sanasidan oldin bo‘lishi mumkin emas.")})

    @property
    def is_open(self):
        return self.status in (self.Status.NEW, self.Status.IN_PROGRESS)

    @property
    def is_overdue(self):
        return self.is_open and self.target_date < timezone.localdate()
