from django.contrib import admin

from .models import Assessment, AssessmentDetail, MentorFeedback


class DetailInline(admin.TabularInline):
    model = AssessmentDetail
    extra = 0


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("student", "mentor", "kind", "decision", "total_score", "max_score", "created_at")
    list_filter = ("kind", "decision")
    search_fields = ("student__last_name", "mentor__last_name")
    raw_id_fields = ("student", "mentor", "portfolio_version", "goal")
    inlines = [DetailInline]


@admin.register(MentorFeedback)
class MentorFeedbackAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "mentor", "kind", "created_at")
    raw_id_fields = ("portfolio", "version", "mentor")
