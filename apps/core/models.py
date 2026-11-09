from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """Yaratilgan va yangilangan vaqtni saqlovchi abstrakt model."""

    created_at = models.DateTimeField(_("Yaratilgan vaqt"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Yangilangan vaqt"), auto_now=True)

    class Meta:
        abstract = True


class SystemSettings(models.Model):
    """Administrator boshqaradigan tizim sozlamalari (yagona yozuv)."""

    CACHE_KEY = "core:system_settings"

    platform_name = models.CharField(
        _("Platforma nomi"), max_length=150, default="Refleksiv portfolio"
    )
    organization_name = models.CharField(_("Ta’lim muassasasi"), max_length=255, blank=True)
    max_upload_size_mb = models.PositiveIntegerField(
        _("Hujjat/rasm/audio fayl hajmi limiti (MB)"),
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(2048)],
    )
    max_video_size_mb = models.PositiveIntegerField(
        _("Video fayl hajmi limiti (MB)"),
        default=1024,
        validators=[MinValueValidator(1), MaxValueValidator(20480)],
    )
    allowed_video_extensions = models.CharField(
        _("Ruxsat etilgan video formatlari"),
        max_length=100,
        default="mp4,webm,mov",
        help_text=_("Vergul bilan ajrating. Mumkin bo‘lganlari: mp4, webm, mov, m4v, mkv, avi"),
    )
    deadline_reminder_hours = models.PositiveIntegerField(
        _("Muddat eslatmasi (soat oldin)"), default=24,
        validators=[MinValueValidator(1), MaxValueValidator(720)],
    )
    allow_late_submission = models.BooleanField(
        _("Muddatdan keyin topshirishga ruxsat"), default=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "system_settings"
        verbose_name = _("Tizim sozlamalari")
        verbose_name_plural = _("Tizim sozlamalari")

    def __str__(self):
        return str(self.platform_name)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    def delete(self, *args, **kwargs):  # yagona yozuv o‘chirilmaydi
        return (0, {})

    @classmethod
    def get_solo(cls) -> "SystemSettings":
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _created = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 300)
        return obj

    @property
    def video_extensions(self) -> set[str]:
        return {
            ext.strip().lower().lstrip(".")
            for ext in self.allowed_video_extensions.split(",")
            if ext.strip()
        }
