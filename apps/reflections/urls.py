from django.urls import path
from django.utils.translation import gettext_lazy as _

from apps.core.crud import crud_urls

from . import views
from .forms import ReflectionQuestionForm
from .models import ReflectionQuestion

app_name = "reflections"

urlpatterns = [
    path("", views.ReflectionListView.as_view(), name="list"),
    path("<int:pk>/", views.ReflectionDetailView.as_view(), name="detail"),
    path("version/<int:version_pk>/", views.ReflectionEditView.as_view(), name="edit"),
    path("version/<int:version_pk>/model/", views.ReflectionModelChangeView.as_view(), name="change_model"),
    path("evidence/<int:pk>/", views.EvidenceFileView.as_view(), name="evidence"),
    path("evidence/<int:pk>/delete/", views.EvidenceDeleteView.as_view(), name="evidence_delete"),
    *crud_urls(
        "question", "questions", ReflectionQuestion, ReflectionQuestionForm,
        title=_("Refleksiya savoli"), title_plural=_("Refleksiya savollari"), icon="bi-patch-question",
        description=_("Savollar model (Gibbs, Kolb) va bosqich bo‘yicha guruhlanadi. Talaba tanlagan modelning "
                      "savollariga alohida javob beradi. Savol matni o‘zgarsa, oldingi javoblarda eski matn "
                      "nusxasi saqlanib qoladi."),
        columns=[(_("Model"), "get_framework_display"), (_("Bosqich"), "stage_label"), (_("Tartib"), "order"),
                 (_("Savol"), "text"), (_("Majburiy"), "is_required"), (_("Faol"), "is_active")],
        search_fields=("text",), translate=("text",),
    ),
]
