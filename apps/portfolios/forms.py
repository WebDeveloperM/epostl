from django import forms
from django.utils.translation import gettext_lazy as _

from apps.assignments.models import Assignment
from apps.core.forms import BootstrapFormMixin, MultipleFileField
from apps.goals.models import Goal

from .models import Portfolio


class PortfolioCreateForm(BootstrapFormMixin, forms.ModelForm):
    files = MultipleFileField(label=_("Fayllar"), required=True,
                              help_text=_("Dars ishlanmasi, video, audio, rasm yoki taqdimot"))
    note = forms.CharField(label=_("Izoh"), required=False, widget=forms.Textarea(attrs={"rows": 2}))

    class Meta:
        model = Portfolio
        fields = ["title", "description", "assignment", "goal", "material_type", "files", "note"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, student, **kwargs):
        super().__init__(*args, **kwargs)
        taken = Portfolio.objects.filter(student=student, assignment__isnull=False).values("assignment_id")
        self.fields["assignment"].queryset = (
            Assignment.objects.filter(targets__student=student, is_active=True).exclude(pk__in=taken)
            .order_by("due_date").distinct()
        )
        self.fields["assignment"].empty_label = _("— Topshiriqsiz (mustaqil ish) —")
        self.fields["goal"].queryset = Goal.objects.filter(
            student=student, status__in=[Goal.Status.NEW, Goal.Status.IN_PROGRESS])
        self.fields["goal"].empty_label = _("— Maqsad tanlanmagan —")


class PortfolioUpdateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ["title", "description", "goal", "material_type"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Goal.objects.filter(student=self.instance.student)
        if self.instance.goal_id:
            qs = qs.filter(pk=self.instance.goal_id) | qs.filter(status__in=[Goal.Status.NEW, Goal.Status.IN_PROGRESS])
        else:
            qs = qs.filter(status__in=[Goal.Status.NEW, Goal.Status.IN_PROGRESS])
        self.fields["goal"].queryset = qs.distinct()


class UploadForm(BootstrapFormMixin, forms.Form):
    files = MultipleFileField(label=_("Fayllar"), required=True)
    note = forms.CharField(label=_("Nima o‘zgardi?"), required=False,
                           widget=forms.Textarea(attrs={"rows": 3, "placeholder": _(
                               "Ustoz tavsiyalari asosida nimalarni takomillashtirdingiz?")}))
