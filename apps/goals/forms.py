from django import forms
from django.utils.translation import gettext_lazy as _

from apps.competencies.models import Competency
from apps.core.forms import BootstrapFormMixin, DateInput

from .models import Goal


class GoalForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Goal
        fields = ["title", "description", "competency", "start_date", "target_date", "expected_outcome"]
        widgets = {
            "start_date": DateInput(),
            "target_date": DateInput(),
            "title": forms.TextInput(attrs={
                "placeholder": _("Masalan: Dars jarayonida barcha o‘quvchilarni savol-javobga jalb qilish "
                                "ko‘nikmasini rivojlantirish")}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["competency"].queryset = Competency.objects.filter(is_active=True)
        self.fields["competency"].required = True


class GoalStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Goal.Status.choices)
