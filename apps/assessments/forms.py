from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import BootstrapFormMixin
from apps.goals.models import Goal

from .models import Assessment, MentorFeedback


class AssessmentForm(BootstrapFormMixin, forms.Form):
    """Mezonlar bo‘yicha dinamik baholash formasi."""

    decision = forms.ChoiceField(label=_("Qaror"), choices=Assessment.Decision.choices,
                                 widget=forms.RadioSelect, initial=Assessment.Decision.APPROVED)
    overall_comment = forms.CharField(label=_("Umumiy xulosa"), required=False,
                                      widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, criteria, details=None, baseline=False, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.criteria = list(criteria)
        details = details or {}
        if baseline:
            del self.fields["decision"]
            self.fields["goal"] = forms.ModelChoiceField(
                label=_("Rivojlanish maqsadi (ixtiyoriy)"), required=False,
                queryset=Goal.objects.filter(student=student) if student else Goal.objects.none())
        for c in self.criteria:
            d = details.get(c.pk)
            self.fields[f"score_{c.pk}"] = forms.IntegerField(
                label=_("Ball"), min_value=0, max_value=c.max_score, initial=d.score if d else None,
                widget=forms.NumberInput(attrs={"min": 0, "max": c.max_score, "data-score-input": "1",
                                                "data-max": c.max_score}),
            )
            self.fields[f"comment_{c.pk}"] = forms.CharField(
                label=_("Izoh"), required=False, initial=d.comment if d else "",
                widget=forms.Textarea(attrs={"rows": 2}))
            self.fields[f"weaknesses_{c.pk}"] = forms.CharField(
                label=_("Kamchiliklar"), required=False, initial=d.weaknesses if d else "",
                widget=forms.Textarea(attrs={"rows": 2}))
            self.fields[f"recommendations_{c.pk}"] = forms.CharField(
                label=_("Tavsiya"), required=False, initial=d.recommendations if d else "",
                widget=forms.Textarea(attrs={"rows": 2}))
        self.apply_bootstrap()

    def criterion_rows(self):
        for c in self.criteria:
            yield {
                "criterion": c,
                "score": self[f"score_{c.pk}"],
                "comment": self[f"comment_{c.pk}"],
                "weaknesses": self[f"weaknesses_{c.pk}"],
                "recommendations": self[f"recommendations_{c.pk}"],
            }

    def details_data(self):
        return [
            {
                "criterion": c,
                "score": self.cleaned_data[f"score_{c.pk}"],
                "comment": self.cleaned_data.get(f"comment_{c.pk}", ""),
                "weaknesses": self.cleaned_data.get(f"weaknesses_{c.pk}", ""),
                "recommendations": self.cleaned_data.get(f"recommendations_{c.pk}", ""),
            }
            for c in self.criteria
        ]

    @property
    def max_total(self):
        return sum(c.max_score for c in self.criteria)


class FeedbackForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MentorFeedback
        fields = ["kind", "text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": _("Izoh yoki tavsiya yozing...")})}
