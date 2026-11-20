from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "organization", "is_deleted", "created_at")
    search_fields = ("full_name", "email", "organization")
    list_filter = ("profession", "created_at")
    readonly_fields = ("created_at", "updated_at")
    
    def get_queryset(self, request):
        """
        Show all records (including soft-deleted) in the Admin panel.
        We use `all_objects` from the SoftDeleteMixin.
        """
        return Client.all_objects.all()