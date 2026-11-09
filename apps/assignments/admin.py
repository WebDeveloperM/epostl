from django.contrib import admin

from .models import Assignment, AssignmentAttachment, AssignmentTarget


class AttachmentInline(admin.TabularInline):
    model = AssignmentAttachment
    extra = 0


class TargetInline(admin.TabularInline):
    model = AssignmentTarget
    extra = 0
    raw_id_fields = ("student",)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "subject", "start_date", "due_date", "is_active")
    list_filter = ("is_active", "subject", "competency")
    search_fields = ("title",)
    filter_horizontal = ("criteria", "groups")
    inlines = [AttachmentInline, TargetInline]


@admin.register(AssignmentTarget)
class AssignmentTargetAdmin(admin.ModelAdmin):
    list_display = ("assignment", "student", "status", "source_group", "submitted_at")
    list_filter = ("status",)
    raw_id_fields = ("student", "assignment")
