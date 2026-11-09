from django.contrib import admin

from .models import Department, Direction, Faculty, StudyGroup


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "is_active")
    search_fields = ("name", "short_name")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "faculty", "is_active")
    list_filter = ("faculty",)
    search_fields = ("name",)


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "faculty", "department", "is_active")
    list_filter = ("faculty",)
    search_fields = ("code", "name")


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "direction", "course", "academic_year", "is_active")
    list_filter = ("course", "direction__faculty")
    search_fields = ("name",)
