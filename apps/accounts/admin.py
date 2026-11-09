from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import MentorAssignment, Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "last_name", "first_name", "role", "group", "is_active", "last_login")
    list_filter = ("role", "is_active", "is_superuser", "group__direction__faculty")
    search_fields = ("username", "first_name", "last_name", "middle_name", "email", "external_id")
    list_select_related = ("role", "group")
    fieldsets = DjangoUserAdmin.fieldsets + (
        (_("Platforma"), {"fields": ("middle_name", "phone", "avatar", "role", "group", "department",
                                     "external_id", "must_change_password")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (_("Platforma"), {"fields": ("last_name", "first_name", "role", "group", "department")}),
    )


@admin.register(MentorAssignment)
class MentorAssignmentAdmin(admin.ModelAdmin):
    list_display = ("mentor", "student", "group", "is_active", "start_date", "end_date")
    list_filter = ("is_active",)
    search_fields = ("mentor__last_name", "student__last_name", "group__name")
    raw_id_fields = ("mentor", "student", "assigned_by")
