from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import BootstrapFormMixin, MultipleFileField
from apps.core.utils import tr

from .frameworks import DEFAULT_FRAMEWORK, STAGE_CHOICES, get_framework
from .models import ReflectionQuestion


class ReflectionForm(BootstrapFormMixin, forms.Form):
    """Har bir faol savol uchun alohida maydon + dalillar."""

    evidence_files = MultipleFileField(label=_("Dalil fayllari"), required=False, max_files=10)
    evidence_link = forms.URLField(label=_("Dalil havolasi"), required=False, assume_scheme="https",
                                   widget=forms.URLInput(attrs={"placeholder": "https://..."}))
    evidence_description = forms.CharField(label=_("Dalil izohi"), required=False, max_length=255)

    def __init__(self, *args, questions, answers=None, framework=DEFAULT_FRAMEWORK.value, **kwargs):
        super().__init__(*args, **kwargs)
        self.info = get_framework(framework)
        self.questions = list(questions)
        answers = answers or {}
        for q in self.questions:
            self.fields[f"q_{q.pk}"] = forms.CharField(
                label=tr(q.text), required=False, help_text=tr(q.help_text),
                initial=answers.get(q.pk, ""),
                widget=forms.Textarea(attrs={"rows": 4, "data-autosize": "1"}),
            )
        self.apply_bootstrap()

    def question_fields(self):
        for q in self.questions:
            yield q, self[f"q_{q.pk}"]

    def progress(self):
        """Nechta savolga javob yozilgan (qoralama yoki yuborilgan ma’lumot bo‘yicha)."""
        done = sum(1 for q in self.questions if str(self[f"q_{q.pk}"].value() or "").strip())
        total = len(self.questions)
        return {"done": done, "total": total, "percent": round(100 * done / total) if total else 0}

    def sections(self):
        """Savollar bosqichlar bo‘yicha: [{"stage", "index", "items": [(raqam, savol, maydon)]}].

        Qisqa refleksiyada bitta bosqichsiz bo‘lim bo‘ladi.
        """
        order = self.info.stage_codes
        by_code = {}
        for number, q in enumerate(self.questions, start=1):
            code = q.stage if q.stage in order else ""
            section = by_code.setdefault(code, {"stage": self.info.stage(code), "items": [],
                                                "index": order.index(code) + 1 if code else 0})
            section["items"].append((number, q, self[f"q_{q.pk}"]))
        return sorted(by_code.values(), key=lambda s: (s["index"] == 0, s["index"]))

    def answers(self) -> dict[int, str]:
        return {q.pk: (self.cleaned_data.get(f"q_{q.pk}") or "").strip() for q in self.questions}


class ReflectionQuestionForm(BootstrapFormMixin, forms.ModelForm):
    stage = forms.ChoiceField(label=_("Bosqich"), choices=STAGE_CHOICES, required=False,
                              help_text=_("Gibbs va Kolb modellari uchun majburiy. Qisqa refleksiyada bo‘sh qoldiring."))

    class Meta:
        model = ReflectionQuestion
        fields = ["framework", "stage", "text", "help_text", "order", "is_required", "is_active"]

    def clean(self):
        data = super().clean()
        framework, stage = data.get("framework"), data.get("stage") or ""
        if not framework:
            return data
        info = get_framework(framework)
        if info.stages and not stage:
            self.add_error("stage", _("Bu model uchun bosqichni tanlang."))
        elif stage and stage not in info.stage_codes:
            self.add_error("stage", _("Bu bosqich tanlangan modelga tegishli emas."))
        return data
