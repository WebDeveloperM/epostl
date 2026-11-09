from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("<int:pk>/open/", views.NotificationOpenView.as_view(), name="open"),
    path("mark-all-read/", views.NotificationMarkAllView.as_view(), name="mark_all"),
]
