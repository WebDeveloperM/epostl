from django import forms

from apps.core.forms import BootstrapFormMixin

from .models import Subject


class SubjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Subject
        fields = ["name", "code", "department", "description", "is_active"]
