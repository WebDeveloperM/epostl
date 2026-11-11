from django.contrib import admin
from django.urls import include, path

from apps.analytics.views import DashboardView
from apps.core.views import LandingView, set_language

admin.site.site_header = "Growth Portfolio — Django admin"
admin.site.site_title = "Growth Portfolio"

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("admincha/", admin.site.urls),
    path("language/", set_language, name="set_language"),
    path("accounts/", include("apps.accounts.urls")),
    path("organization/", include("apps.organization.urls")),
    path("subjects/", include("apps.subjects.urls")),
    path("competencies/", include("apps.competencies.urls")),
    path("goals/", include("apps.goals.urls")),
    path("assignments/", include("apps.assignments.urls")),
    path("portfolio/", include("apps.portfolios.urls")),
    path("reflections/", include("apps.reflections.urls")),
    path("assessments/", include("apps.assessments.urls")),
    path("analytics/", include("apps.analytics.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("audit/", include("apps.audit.urls")),
    path("system/", include("apps.core.urls")),
]

handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
