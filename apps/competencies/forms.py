from django import forms

from apps.core.forms import BootstrapFormMixin

from .models import AssessmentCriterion, Competency


class CompetencyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Competency
        fields = ["code", "name", "description", "order", "is_active"]


class AssessmentCriterionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AssessmentCriterion
        fields = ["name", "competency", "description", "max_score", "order", "is_active"]
