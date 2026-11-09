from django.utils.translation import gettext_lazy as _

from apps.core.crud import crud_urls

from .forms import DepartmentForm, DirectionForm, FacultyForm, StudyGroupForm
from .models import Department, Direction, Faculty, StudyGroup

app_name = "organization"

urlpatterns = [
    *crud_urls(
        "faculty", "faculties", Faculty, FacultyForm,
        title=_("Fakultet"), title_plural=_("Fakultetlar"), icon="bi-bank",
        columns=[(_("Nomi"), "name"), (_("Qisqa nomi"), "short_name"), (_("Faol"), "is_active")],
        search_fields=("name", "short_name"),
    ),
    *crud_urls(
        "department", "departments", Department, DepartmentForm,
        title=_("Kafedra"), title_plural=_("Kafedralar"), icon="bi-diagram-2",
        columns=[(_("Nomi"), "name"), (_("Fakultet"), "faculty"), (_("Faol"), "is_active")],
        search_fields=("name", "faculty__name"), select_related=("faculty",),
    ),
    *crud_urls(
        "direction", "directions", Direction, DirectionForm,
        title=_("Ta’lim yo‘nalishi"), title_plural=_("Ta’lim yo‘nalishlari"), icon="bi-signpost-split",
        columns=[(_("Shifr"), "code"), (_("Nomi"), "name"), (_("Fakultet"), "faculty"),
                 (_("Kafedra"), "department"), (_("Faol"), "is_active")],
        search_fields=("code", "name"), select_related=("faculty", "department"),
    ),
    *crud_urls(
        "group", "groups", StudyGroup, StudyGroupForm,
        title=_("Guruh"), title_plural=_("Guruhlar"), icon="bi-people",
        columns=[(_("Guruh"), "name"), (_("Yo‘nalish"), "direction"), (_("Kurs"), "course"),
                 (_("O‘quv yili"), "academic_year"), (_("Faol"), "is_active")],
        search_fields=("name", "direction__name", "direction__code"),
        select_related=("direction",),
    ),
]
