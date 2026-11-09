from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient", "type", "title", "is_read")
    list_filter = ("type", "is_read")
    search_fields = ("title", "recipient__username", "recipient__last_name")
    raw_id_fields = ("recipient", "actor")
