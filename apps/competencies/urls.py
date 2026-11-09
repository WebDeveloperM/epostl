from django.utils.translation import gettext_lazy as _

from apps.core.crud import crud_urls

from .forms import AssessmentCriterionForm, CompetencyForm
from .models import AssessmentCriterion, Competency

app_name = "competencies"

urlpatterns = [
    *crud_urls(
        "competency", "items", Competency, CompetencyForm,
        title=_("Kompetensiya"), title_plural=_("Pedagogik kompetensiyalar"), icon="bi-stars",
        columns=[(_("Tartib"), "order"), (_("Kod"), "code"), (_("Nomi"), "name"), (_("Faol"), "is_active")],
        search_fields=("name", "code"), translate=("name",),
    ),
    *crud_urls(
        "criterion", "criteria", AssessmentCriterion, AssessmentCriterionForm,
        title=_("Baholash mezoni"), title_plural=_("Baholash mezonlari"), icon="bi-list-check",
        description=_("Ustoz ishlarni shu mezonlar asosida baholaydi. Mezonni o‘zgartirish oldingi "
                      "baholarga ta’sir qilmaydi — har bir bahoda maksimal ball nusxasi saqlanadi."),
        columns=[(_("Tartib"), "order"), (_("Mezon"), "name"), (_("Kompetensiya"), "competency"),
                 (_("Maks. ball"), "max_score"), (_("Faol"), "is_active")],
        search_fields=("name",), select_related=("competency",), translate=("name",),
    ),
]
