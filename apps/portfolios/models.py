from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.files import random_upload_name


class Portfolio(models.Model):
    """Portfolio yozuvi — talabaning amaliy ishi (topshiriq va/yoki maqsadga bog‘langan).

    Bitta topshiriq bo‘yicha talabada bitta ish bo‘ladi, ish esa bir nechta
    versiyaga ega bo‘lishi mumkin. Versiyalar hech qachon o‘chirilmaydi.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Qoralama")
        SUBMITTED = "submitted", _("Tekshirishda")
        REVISION = "revision", _("Qayta ishlash talab etiladi")
        APPROVED = "approved", _("Tasdiqlangan")

    class MaterialType(models.TextChoices):
        LESSON_PLAN = "lesson_plan", _("Dars ishlanmasi")
        VIDEO = "video", _("Dars videosi")
        AUDIO = "audio", _("Audio yozuv")
        IMAGE = "image", _("Rasmlar")
        PRESENTATION = "presentation", _("Taqdimot")
        OTHER = "other", _("Boshqa hujjat")

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="portfolios",
                                verbose_name=_("Talaba"))
    title = models.CharField(_("Ish nomi"), max_length=255)
    description = models.TextField(_("Tavsifi"), blank=True)
    assignment = models.ForeignKey("assignments.Assignment", on_delete=models.PROTECT, null=True, blank=True,
                                   related_name="portfolios", verbose_name=_("Bog‘langan topshiriq"))
    goal = models.ForeignKey("goals.Goal", on_delete=models.PROTECT, null=True, blank=True,
                             related_name="portfolios", verbose_name=_("Bog‘langan rivojlanish maqsadi"))
    material_type = models.CharField(_("Material turi"), max_length=20, choices=MaterialType.choices,
                                     default=MaterialType.LESSON_PLAN)
    status = models.CharField(_("Ish holati"), max_length=20, choices=Status.choices, default=Status.DRAFT,
                              db_index=True)
    current_version = models.PositiveSmallIntegerField(_("Joriy versiya"), default=0)
    submitted_at = models.DateTimeField(_("Yuborilgan vaqt"), null=True, blank=True)
    approved_at = models.DateTimeField(_("Tasdiqlangan vaqt"), null=True, blank=True)
    created_at = models.DateTimeField(_("Yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Yangilangan"), auto_now=True)

    class Meta:
        db_table = "portfolios"
        ordering = ["-updated_at"]
        verbose_name = _("Portfolio ishi")
        verbose_name_plural = _("Portfolio ishlari")
        constraints = [
            models.UniqueConstraint(fields=["student", "assignment"], condition=Q(assignment__isnull=False),
                                    name="uniq_portfolio_per_assignment"),
        ]

    def __str__(self):
        return self.title

    @property
    def latest_version(self):
        if not hasattr(self, "_latest_version_cache"):
            self._latest_version_cache = self.versions.order_by("-version_number").first()
        return self._latest_version_cache

    def refresh_from_db(self, *args, **kwargs):
        self.__dict__.pop("_latest_version_cache", None)
        super().refresh_from_db(*args, **kwargs)


class PortfolioVersion(models.Model):
    """Ishning versiyasi. Talaba qayta yuklaganda yangi versiya yaratiladi."""

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="versions",
                                  verbose_name=_("Ish"))
    version_number = models.PositiveSmallIntegerField(_("Versiya raqami"))
    note = models.TextField(_("O‘zgarishlar izohi"), blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name="+")
    created_at = models.DateTimeField(_("Yuklangan sana"), auto_now_add=True)
    submitted_at = models.DateTimeField(_("Tekshirishga yuborilgan"), null=True, blank=True)

    class Meta:
        db_table = "portfolio_versions"
        ordering = ["-version_number"]
        verbose_name = _("Ish versiyasi")
        verbose_name_plural = _("Ish versiyalari")
        constraints = [
            models.UniqueConstraint(fields=["portfolio", "version_number"], name="uniq_portfolio_version"),
        ]

    def __str__(self):
        return f"{self.portfolio} — v{self.version_number}"

    @property
    def is_submitted(self):
        return self.submitted_at is not None


def portfolio_file_upload_to(instance, filename):
    version = instance.version
    return random_upload_name(
        f"portfolio/{version.portfolio.student_id}/{version.portfolio_id}/v{version.version_number}", filename
    )


class PortfolioFile(models.Model):
    """Versiyaga yuklangan fayl (dars ishlanmasi, video, audio, rasm, taqdimot...).

    Fayl media storage'da saqlanadi, bazada faqat metama’lumotlar va manzil.
    """

    version = models.ForeignKey(PortfolioVersion, on_delete=models.CASCADE, related_name="files",
                                verbose_name=_("Versiya"))
    file = models.FileField(_("Fayl"), upload_to=portfolio_file_upload_to, max_length=255)
    original_name = models.CharField(_("Fayl nomi"), max_length=255)
    file_size = models.PositiveBigIntegerField(_("Hajmi (bayt)"), default=0)
    mime_type = models.CharField(_("MIME turi"), max_length=120)
    category = models.CharField(_("Toifa"), max_length=20)
    uploaded_at = models.DateTimeField(_("Yuklangan vaqt"), auto_now_add=True)

    class Meta:
        db_table = "portfolio_files"
        ordering = ["uploaded_at"]
        verbose_name = _("Ish fayli")
        verbose_name_plural = _("Ish fayllari")

    def __str__(self):
        return self.original_name

    @property
    def is_video(self):
        return self.category == "video"

    @property
    def is_audio(self):
        return self.category == "audio"

    @property
    def is_image(self):
        return self.category == "image"

    @property
    def is_pdf(self):
        return self.mime_type == "application/pdf"
