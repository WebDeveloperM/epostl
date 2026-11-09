from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("password/", views.PasswordChangeView.as_view(), name="password_change"),
    path("avatar/<int:pk>/", views.AvatarView.as_view(), name="avatar"),
    # Administrator: foydalanuvchilar
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/new/", views.UserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/edit/", views.UserUpdateView.as_view(), name="user_update"),
    path("users/<int:pk>/toggle-active/", views.UserToggleActiveView.as_view(), name="user_toggle"),
    path("users/import/", views.UserImportView.as_view(), name="user_import"),
    path("users/import/template.xlsx", views.UserImportTemplateView.as_view(), name="user_import_template"),
    # Administrator: ustoz biriktiruvlari
    path("mentor-assignments/", views.MentorAssignmentListView.as_view(), name="mentor_assignment_list"),
    path("mentor-assignments/new/", views.MentorAssignmentCreateView.as_view(), name="mentor_assignment_create"),
    path("mentor-assignments/<int:pk>/toggle/", views.MentorAssignmentToggleView.as_view(),
         name="mentor_assignment_toggle"),
]
