from django.contrib import admin
from .models import Template, PlatformSettings


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "is_active", "created_at")
    search_fields = ("name", "key")
    list_filter = ("is_active",)


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ("platform_name", "admin_contact_email", "email_notifications_enabled")
    
    def has_add_permission(self, request):
        return not PlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False