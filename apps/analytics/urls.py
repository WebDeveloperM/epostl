from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("", views.AnalyticsView.as_view(), name="index"),
    path("students/", views.StudentListView.as_view(), name="students"),
    path("students/<int:pk>/", views.StudentDetailView.as_view(), name="student_detail"),
]
