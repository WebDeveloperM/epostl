from django.contrib import admin

from .models import Reflection, ReflectionAnswer, ReflectionEvidence, ReflectionQuestion


@admin.register(ReflectionQuestion)
class ReflectionQuestionAdmin(admin.ModelAdmin):
    list_display = ("framework", "stage", "order", "text", "is_required", "is_active")
    list_display_links = ("text",)
    list_filter = ("framework", "is_active")


class AnswerInline(admin.StackedInline):
    model = ReflectionAnswer
    extra = 0


class EvidenceInline(admin.TabularInline):
    model = ReflectionEvidence
    extra = 0


@admin.register(Reflection)
class ReflectionAdmin(admin.ModelAdmin):
    list_display = ("student", "portfolio_version", "framework", "status", "submitted_at")
    list_filter = ("framework", "status")
    raw_id_fields = ("student", "portfolio_version")
    inlines = [AnswerInline, EvidenceInline]
