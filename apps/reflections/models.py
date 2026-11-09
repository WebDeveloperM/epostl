from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.files import random_upload_name
from apps.core.utils import tr

from .frameworks import DEFAULT_FRAMEWORK, Framework, get_framework, stage_of


class ReflectionQuestion(models.Model):
    """Refleksiya savoli (administrator boshqaradi)."""

    framework = models.CharField(_("Model"), max_length=20, choices=Framework.choices,
                                 default=DEFAULT_FRAMEWORK.value)
    stage = models.CharField(_("Bosqich"), max_length=40, blank=True)
    text = models.CharField(_("Savol matni"), max_length=500)
    help_text = models.CharField(_("Yordamchi izoh"), max_length=500, blank=True)
    order = models.PositiveSmallIntegerField(_("Tartib"), default=0)
    is_required = models.BooleanField(_("Majburiy"), default=True)
    is_active = models.BooleanField(_("Faol"), default=True)

    class Meta:
        db_table = "reflection_questions"
        ordering = ["framework", "order", "id"]
        verbose_name = _("Refleksiya savoli")
        verbose_name_plural = _("Refleksiya savollari")
        indexes = [models.Index(fields=["framework", "is_active"], name="refl_q_framework_active")]

    def __str__(self):
        return self.text

    @property
    def stage_label(self):
        _info, stage = stage_of(self.stage)
        return stage.label if stage else ""


class Reflection(models.Model):
    """Talabaning ish versiyasi bo‘yicha refleksiyasi."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Qoralama")
        SUBMITTED = "submitted", _("Ustozga yuborilgan")

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reflections",
                                verbose_name=_("Talaba"))
    portfolio_version = models.OneToOneField("portfolios.PortfolioVersion", on_delete=models.CASCADE,
                                             related_name="reflection", verbose_name=_("Ish versiyasi"))
    framework = models.CharField(_("Model"), max_length=20, choices=Framework.choices,
                                 default=DEFAULT_FRAMEWORK.value, db_index=True)
    status = models.CharField(_("Holati"), max_length=20, choices=Status.choices, default=Status.DRAFT,
                              db_index=True)
    submitted_at = models.DateTimeField(_("Yuborilgan vaqt"), null=True, blank=True)
    created_at = models.DateTimeField(_("Yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Yangilangan"), auto_now=True)

    class Meta:
        db_table = "reflections"
        ordering = ["-created_at"]
        verbose_name = _("Refleksiya")
        verbose_name_plural = _("Refleksiyalar")

    def __str__(self):
        return f"{self.student} — {self.portfolio_version}"

    @property
    def framework_info(self):
        return get_framework(self.framework)

    def grouped_answers(self):
        """Javoblar bosqichlar bo‘yicha: [(bosqich yoki None, bosqich raqami, [javoblar])].

        Har bir javobga umumiy `number` beriladi. Bosqichsiz javoblar (qisqa refleksiya, eski ma’lumot)
        oxirida bitta guruhga yig‘iladi.
        """
        info = self.framework_info
        by_stage = {}
        for a in self.answers.all():
            by_stage.setdefault(a.stage if info.stage(a.stage) else "", []).append(a)
        groups = [(st, index, by_stage.pop(st.code))
                  for index, st in enumerate(info.stages, start=1) if st.code in by_stage]
        if by_stage:
            groups.append((None, 0, [a for rest in by_stage.values() for a in rest]))
        number = 0
        for _stage, _index, items in groups:
            for a in items:
                number += 1
                a.number = number
        return groups

    def insights(self):
        """Asosiy xulosalar: [{"label", "text"}]. Gibbs — xulosa va harakat rejasi, Kolb — mavhum tushunchalash
        va faol tajriba; qisqa refleksiyada — oxirgi javob («keyingi safar nimani o‘zgartiraman»)."""
        info = self.framework_info
        answers = [a for a in self.answers.all() if a.answer.strip()]
        if not info.stages:
            return [{"label": tr(a.question_text), "text": a.answer} for a in answers[-1:]]
        wanted = {code: info.stage(code) for code in info.insight_stages}
        return [{"label": wanted[a.stage].label, "text": a.answer}
                for code in info.insight_stages for a in answers if a.stage == code]

    @property
    def is_locked(self):
        """Ustoz baholagandan keyin refleksiya o‘zgartirilmaydi."""
        from apps.assessments.models import Assessment

        return Assessment.objects.filter(portfolio_version_id=self.portfolio_version_id).exists()


class ReflectionAnswer(models.Model):
    """Har bir refleksiya savoliga alohida javob."""

    reflection = models.ForeignKey(Reflection, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(ReflectionQuestion, on_delete=models.PROTECT, related_name="answers")
    question_text = models.CharField(_("Savol (nusxa)"), max_length=500)
    stage = models.CharField(_("Bosqich (nusxa)"), max_length=40, blank=True)
    answer = models.TextField(_("Javob"), blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reflection_answers"
        ordering = ["question__order", "question_id"]
        verbose_name = _("Refleksiya javobi")
        verbose_name_plural = _("Refleksiya javoblari")
        constraints = [
            models.UniqueConstraint(fields=["reflection", "question"], name="uniq_reflection_answer"),
        ]

    def __str__(self):
        return self.question_text


def evidence_upload_to(instance, filename):
    return random_upload_name(f"reflections/{instance.reflection.student_id}", filename)


class ReflectionEvidence(models.Model):
    """Refleksiyaga biriktirilgan dalil: fayl yoki havola."""

    reflection = models.ForeignKey(Reflection, on_delete=models.CASCADE, related_name="evidence")
    file = models.FileField(_("Fayl"), upload_to=evidence_upload_to, max_length=255, blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=20, blank=True)
    link = models.URLField(_("Havola"), blank=True)
    description = models.CharField(_("Izoh"), max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reflection_evidence"
        ordering = ["created_at"]
        verbose_name = _("Refleksiya dalili")
        verbose_name_plural = _("Refleksiya dalillari")

    def __str__(self):
        return self.original_name or self.link or self.description
