from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """Tizimdagi muhim amallar tarixi."""

    class Action(models.TextChoices):
        LOGIN = "login", _("Tizimga kirish")
        LOGOUT = "logout", _("Tizimdan chiqish")
        LOGIN_FAILED = "login_failed", _("Muvaffaqiyatsiz kirish")
        CREATE = "create", _("Yaratish")
        UPDATE = "update", _("O‘zgartirish")
        DELETE = "delete", _("O‘chirish")
        BLOCK = "block", _("Bloklash")
        UNBLOCK = "unblock", _("Faollashtirish")
        IMPORT = "import", _("Import")
        UPLOAD = "upload", _("Fayl yuklash")
        SUBMIT = "submit", _("Tekshirishga yuborish")
        ASSESS = "assess", _("Baholash")
        PASSWORD = "password", _("Parol o‘zgartirish")
        ASSIGN = "assign", _("Biriktirish")
        DOWNLOAD = "download", _("Fayl yuklab olish")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audit_logs", verbose_name=_("Foydalanuvchi"),
    )
    action = models.CharField(_("Amal"), max_length=20, choices=Action.choices, db_index=True)
    object_type = models.CharField(_("Obyekt turi"), max_length=100, blank=True)
    object_id = models.CharField(_("Obyekt ID"), max_length=64, blank=True)
    object_repr = models.CharField(_("Obyekt"), max_length=255, blank=True)
    message = models.TextField(_("Izoh"), blank=True)
    extra = models.JSONField(_("Qo‘shimcha ma’lumot"), default=dict, blank=True)
    ip_address = models.GenericIPAddressField(_("IP manzil"), null=True, blank=True)
    user_agent = models.CharField(_("Brauzer"), max_length=255, blank=True)
    created_at = models.DateTimeField(_("Vaqt"), auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        verbose_name = _("Audit yozuvi")
        verbose_name_plural = _("Audit log")
        indexes = [models.Index(fields=["object_type", "object_id"])]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.user} {self.get_action_display()}"
