from django.urls import path

from . import views

app_name = "assignments"

urlpatterns = [
    path("", views.AssignmentListView.as_view(), name="list"),
    path("new/", views.AssignmentCreateView.as_view(), name="create"),
    path("<int:pk>/", views.AssignmentDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.AssignmentUpdateView.as_view(), name="update"),
    path("<int:pk>/accept/", views.AssignmentAcceptView.as_view(), name="accept"),
    path("<int:pk>/delete/", views.AssignmentDeleteView.as_view(), name="delete"),
    path("attachments/<int:pk>/", views.AttachmentDownloadView.as_view(), name="attachment"),
    path("attachments/<int:pk>/delete/", views.AttachmentDeleteView.as_view(), name="attachment_delete"),
]
