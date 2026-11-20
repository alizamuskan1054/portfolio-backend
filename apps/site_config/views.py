"""
API Views for Platform Configuration.
"""
from rest_framework import viewsets, generics
from apps.common.permissions import IsVerifiedAdmin
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from apps.common.permissions import IsVerifiedAdmin
from apps.common.responses import success_response, created_response
from apps.common.pagination import StandardResultsPagination
from .models import Template, PlatformSettings
from .serializers import TemplateSerializer, PlatformSettingsSerializer


class TemplateViewSet(viewsets.ModelViewSet):
    """CRUD for Templates."""
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    pagination_class = StandardResultsPagination
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        # Admin sab dekh sakta hai, Client/Public sirf active templates
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return qs
        return qs.filter(is_active=True)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return created_response(data=serializer.data, message="Template created.")


class PlatformSettingsView(generics.RetrieveUpdateAPIView):
    """Retrieve and update the singleton platform settings."""
    permission_classes = [IsVerifiedAdmin]
    serializer_class = PlatformSettingsSerializer

    def get_object(self):
        obj, created = PlatformSettings.objects.get_or_create(
            id=1, defaults={"admin_contact_email": "admin@example.com"}
        )
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(data=serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(data=serializer.data, message="Settings updated successfully.")


class PublicPlatformSettingsView(generics.RetrieveAPIView):
    """Public endpoint for basic platform info."""
    permission_classes = []
    authentication_classes = []
    serializer_class = PlatformSettingsSerializer

    def get_object(self):
        obj, created = PlatformSettings.objects.get_or_create(id=1)
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        public_data = {
            "platform_name": serializer.data.get("platform_name"),
            "logo": serializer.data.get("logo"),
            "default_theme": serializer.data.get("default_theme"),
            "default_typography": serializer.data.get("default_typography"),
        }
        return success_response(data=public_data)