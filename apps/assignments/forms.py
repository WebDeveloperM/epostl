from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.accounts.services import mentor_groups, mentor_students
from apps.competencies.models import AssessmentCriterion, Competency
from apps.core.forms import BootstrapFormMixin, DateTimeInput, MultipleFileField
from apps.subjects.models import Subject

from .models import Assignment, AssignmentTarget


class AssignmentForm(BootstrapFormMixin, forms.ModelForm):
    students = forms.ModelMultipleChoiceField(
        label=_("Alohida talabalar"), queryset=None, required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
        help_text=_("Ctrl (Cmd) tugmasini bosib bir nechtasini tanlang"),
    )
    attachments = MultipleFileField(label=_("Qo‘shimcha fayllar"), required=False)

    class Meta:
        model = Assignment
        fields = [
            "title", "description", "subject", "competency", "instructions", "criteria", "criteria_notes",
            "start_date", "due_date", "groups", "students", "attachments", "is_active",
        ]
        widgets = {
            "start_date": DateTimeInput(),
            "due_date": DateTimeInput(),
            "criteria": forms.CheckboxSelectMultiple(),
            "groups": forms.CheckboxSelectMultiple(),
            "description": forms.Textarea(attrs={"rows": 4}),
            "instructions": forms.Textarea(attrs={"rows": 5}),
            "criteria_notes": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "criteria": _("Hech biri tanlanmasa, barcha faol mezonlar qo‘llaniladi."),
        }

    def __init__(self, *args, mentor, **kwargs):
        super().__init__(*args, **kwargs)
        self.mentor = mentor
        self.fields["subject"].queryset = Subject.objects.filter(is_active=True)
        self.fields["competency"].queryset = Competency.objects.filter(is_active=True)
        self.fields["criteria"].queryset = AssessmentCriterion.objects.filter(is_active=True)
        self.fields["groups"].queryset = mentor_groups(mentor)
        self.fields["students"].queryset = mentor_students(mentor).order_by("group__name", "last_name")
        self.fields["students"].label_from_instance = lambda u: f"{u.full_name} — {u.group or ''}"
        if self.instance.pk:
            self.fields["students"].initial = list(
                AssignmentTarget.objects.filter(assignment=self.instance, source_group__isnull=True)
                .values_list("student_id", flat=True))
        self.apply_bootstrap()

    def clean(self):
        cleaned = super().clean()
        start, due = cleaned.get("start_date"), cleaned.get("due_date")
        if start and due and due <= start:
            self.add_error("due_date", _("Yakuniy muddat boshlanish muddatidan keyin bo‘lishi kerak."))
        has_targets = bool(self.instance.pk and self.instance.targets.exists())
        if not cleaned.get("groups") and not cleaned.get("students") and not has_targets:
            raise ValidationError(_("Kamida bitta guruh yoki talabani tanlang."))
        return cleaned
