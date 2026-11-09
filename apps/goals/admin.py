from django.contrib import admin

from .models import Goal


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "competency", "status", "start_date", "target_date")
    list_filter = ("status", "competency")
    search_fields = ("title", "student__last_name", "student__username")
    raw_id_fields = ("student",)
