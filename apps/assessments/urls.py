from django.urls import path

from . import views

app_name = "assessments"

urlpatterns = [
    path("", views.AssessmentListView.as_view(), name="list"),
    path("queue/", views.ReviewQueueView.as_view(), name="queue"),
    path("<int:pk>/", views.AssessmentDetailView.as_view(), name="detail"),
    path("version/<int:version_pk>/", views.AssessView.as_view(), name="assess"),
    path("baseline/<int:student_pk>/", views.BaselineCreateView.as_view(), name="baseline"),
    path("feedback/<int:portfolio_pk>/", views.FeedbackCreateView.as_view(), name="feedback"),
]
