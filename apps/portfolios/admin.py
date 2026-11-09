from django.contrib import admin

from .models import Portfolio, PortfolioFile, PortfolioVersion


class VersionInline(admin.TabularInline):
    model = PortfolioVersion
    extra = 0
    readonly_fields = ("version_number", "created_at", "submitted_at")
    can_delete = False


class FileInline(admin.TabularInline):
    model = PortfolioFile
    extra = 0
    readonly_fields = ("original_name", "file_size", "mime_type", "category", "uploaded_at")
    can_delete = False


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "assignment", "goal", "status", "current_version", "updated_at")
    list_filter = ("status", "material_type")
    search_fields = ("title", "student__last_name", "student__username")
    raw_id_fields = ("student", "assignment", "goal")
    inlines = [VersionInline]


@admin.register(PortfolioVersion)
class PortfolioVersionAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "version_number", "created_at", "submitted_at")
    inlines = [FileInline]
    raw_id_fields = ("portfolio",)

    def has_delete_permission(self, request, obj=None):
        return False  # versiyalar tarixi o‘chirilmaydi
