from django.contrib import admin

from .models import AssessmentCriterion, Competency


@admin.register(Competency)
class CompetencyAdmin(admin.ModelAdmin):
    list_display = ("order", "code", "name", "is_active")
    list_display_links = ("name",)


@admin.register(AssessmentCriterion)
class AssessmentCriterionAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "competency", "max_score", "is_active")
    list_display_links = ("name",)
