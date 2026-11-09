from django.utils.translation import gettext_lazy as _

from apps.core.crud import crud_urls

from .forms import SubjectForm
from .models import Subject

app_name = "subjects"

urlpatterns = crud_urls(
    "subject", "items", Subject, SubjectForm,
    title=_("Fan"), title_plural=_("Fanlar"), icon="bi-book",
    columns=[(_("Kod"), "code"), (_("Fan nomi"), "name"), (_("Kafedra"), "department"), (_("Faol"), "is_active")],
    search_fields=("name", "code"), select_related=("department",),
)
