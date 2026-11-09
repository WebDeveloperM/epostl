from django.urls import path

from . import views

app_name = "portfolios"

urlpatterns = [
    path("", views.PortfolioListView.as_view(), name="list"),
    path("new/", views.PortfolioCreateView.as_view(), name="create"),
    path("<int:pk>/", views.PortfolioDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.PortfolioUpdateView.as_view(), name="update"),
    path("<int:pk>/upload/", views.PortfolioUploadView.as_view(), name="upload"),
    path("files/<int:pk>/", views.PortfolioFileView.as_view(), name="file"),
    path("files/<int:pk>/delete/", views.PortfolioFileDeleteView.as_view(), name="file_delete"),
]
