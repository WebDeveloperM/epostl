from django import forms

from apps.core.forms import BootstrapFormMixin

from .models import Department, Direction, Faculty, StudyGroup


class FacultyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Faculty
        fields = ["name", "short_name", "is_active"]


class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["faculty", "name", "is_active"]


class DirectionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Direction
        fields = ["faculty", "department", "code", "name", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.select_related("faculty")

    def clean(self):
        cleaned = super().clean()
        faculty, department = cleaned.get("faculty"), cleaned.get("department")
        if faculty and department and department.faculty_id != faculty.id:
            self.add_error("department", "Kafedra tanlangan fakultetga tegishli emas.")
        return cleaned


class StudyGroupForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StudyGroup
        fields = ["direction", "name", "course", "academic_year", "is_active"]
