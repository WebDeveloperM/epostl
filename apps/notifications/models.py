from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """Platforma ichidagi bildirishnoma."""

    class Type(models.TextChoices):
        ASSIGNMENT_NEW = "assignment_new", _("Yangi topshiriq")
        DEADLINE_SOON = "deadline_soon", _("Muddat yaqinlashmoqda")
        WORK_SUBMITTED = "work_submitted", _("Talaba ish yukladi")
        FEEDBACK = "feedback", _("Ustoz izohi")
        REVISION = "revision", _("Qayta ishlashga qaytarildi")
        APPROVED = "approved", _("Ish tasdiqlandi")
        SYSTEM = "system", _("Tizim xabari")

    ICONS = {
        Type.ASSIGNMENT_NEW: ("bi-journal-plus", "primary"),
        Type.DEADLINE_SOON: ("bi-alarm", "warning"),
        Type.WORK_SUBMITTED: ("bi-cloud-arrow-up", "info"),
        Type.FEEDBACK: ("bi-chat-left-text", "primary"),
        Type.REVISION: ("bi-arrow-repeat", "danger"),
        Type.APPROVED: ("bi-patch-check", "success"),
        Type.SYSTEM: ("bi-info-circle", "secondary"),
    }

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="notifications", verbose_name=_("Qabul qiluvchi"))
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="+", verbose_name=_("Yuboruvchi"))
    type = models.CharField(_("Turi"), max_length=30, choices=Type.choices, default=Type.SYSTEM)
    title = models.CharField(_("Sarlavha"), max_length=255)
    message = models.TextField(_("Matn"), blank=True)
    url = models.CharField(_("Havola"), max_length=500, blank=True)
    is_read = models.BooleanField(_("O‘qilgan"), default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        verbose_name = _("Bildirishnoma")
        verbose_name_plural = _("Bildirishnomalar")
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return self.title

    @property
    def icon(self):
        return self.ICONS.get(self.type, ("bi-bell", "secondary"))[0]

    @property
    def color(self):
        return self.ICONS.get(self.type, ("bi-bell", "secondary"))[1]
