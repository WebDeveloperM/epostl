from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.files import random_upload_name


class Assignment(models.Model):
    """Ustoz tomonidan beriladigan topshiriq."""

    title = models.CharField(_("Topshiriq nomi"), max_length=255)
    description = models.TextField(_("Batafsil tavsif"))
    subject = models.ForeignKey("subjects.Subject", on_delete=models.PROTECT, null=True, blank=True,
                                related_name="assignments", verbose_name=_("Fan"))
    competency = models.ForeignKey("competencies.Competency", on_delete=models.PROTECT, null=True,
                                   blank=True, related_name="assignments",
                                   verbose_name=_("Rivojlantiriladigan kompetensiya"))
    instructions = models.TextField(_("Bajarish bo‘yicha yo‘riqnoma"), blank=True)
    criteria = models.ManyToManyField("competencies.AssessmentCriterion", blank=True, related_name="assignments",
                                      verbose_name=_("Baholash mezonlari"))
    criteria_notes = models.TextField(_("Baholash mezonlari bo‘yicha izoh"), blank=True)
    start_date = models.DateTimeField(_("Boshlanish muddati"), default=timezone.now)
    due_date = models.DateTimeField(_("Yakuniy muddat"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="created_assignments", verbose_name=_("Ustoz"))
    groups = models.ManyToManyField("organization.StudyGroup", blank=True, related_name="assignments",
                                    verbose_name=_("Biriktirilgan guruhlar"))
    is_active = models.BooleanField(_("Faol"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assignments"
        ordering = ["-created_at"]
        verbose_name = _("Topshiriq")
        verbose_name_plural = _("Topshiriqlar")
        constraints = [
            models.CheckConstraint(condition=models.Q(due_date__gt=models.F("start_date")),
                                   name="assignment_due_after_start"),
        ]

    def __str__(self):
        return self.title

    @property
    def is_past_due(self):
        return timezone.now() > self.due_date

    def effective_criteria(self):
        from apps.competencies.models import AssessmentCriterion

        selected = self.criteria.filter(is_active=True)
        if selected.exists():
            return selected.select_related("competency")
        return AssessmentCriterion.objects.filter(is_active=True).select_related("competency")


def attachment_upload_to(instance, filename):
    return random_upload_name(f"assignments/{instance.assignment_id}", filename)


class AssignmentAttachment(models.Model):
    """Topshiriqqa biriktirilgan qo‘shimcha fayllar."""

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(_("Fayl"), upload_to=attachment_upload_to, max_length=255)
    original_name = models.CharField(_("Fayl nomi"), max_length=255)
    file_size = models.PositiveBigIntegerField(_("Hajmi"), default=0)
    mime_type = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=20, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assignment_attachments"
        ordering = ["uploaded_at"]
        verbose_name = _("Topshiriq fayli")
        verbose_name_plural = _("Topshiriq fayllari")

    def __str__(self):
        return self.original_name


class AssignmentTarget(models.Model):
    """Topshiriq biriktirilgan talaba (to‘g‘ridan-to‘g‘ri yoki guruh orqali) va uning holati."""

    class Status(models.TextChoices):
        NEW = "new", _("Yangi")
        ACCEPTED = "accepted", _("Qabul qilingan")
        IN_PROGRESS = "in_progress", _("Bajarilmoqda")
        SUBMITTED = "submitted", _("Tekshirishda")
        REVISION = "revision", _("Qayta ishlash talab etiladi")
        APPROVED = "approved", _("Tasdiqlangan")
        OVERDUE = "overdue", _("Muddati o‘tgan")

    OPEN_STATUSES = (Status.NEW, Status.ACCEPTED, Status.IN_PROGRESS, Status.REVISION, Status.OVERDUE)

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="targets",
                                   verbose_name=_("Topshiriq"))
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="assignment_targets", verbose_name=_("Talaba"))
    source_group = models.ForeignKey("organization.StudyGroup", on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="+", verbose_name=_("Guruh orqali"))
    status = models.CharField(_("Holati"), max_length=20, choices=Status.choices, default=Status.NEW,
                              db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    deadline_reminder_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assignment_targets"
        ordering = ["assignment__due_date"]
        verbose_name = _("Topshiriq ijrochisi")
        verbose_name_plural = _("Topshiriq ijrochilari")
        constraints = [
            models.UniqueConstraint(fields=["assignment", "student"], name="uniq_assignment_student"),
        ]

    def __str__(self):
        return f"{self.assignment} — {self.student}"

    @property
    def is_overdue(self):
        return self.status in self.OPEN_STATUSES and timezone.now() > self.assignment.due_date

    @property
    def display_status(self):
        return self.Status.OVERDUE if self.is_overdue else self.status

    @property
    def display_status_label(self):
        return self.Status(self.display_status).label
