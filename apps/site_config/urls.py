from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TemplateViewSet, PlatformSettingsView, PublicPlatformSettingsView

router = DefaultRouter()
router.register(r"templates", TemplateViewSet, basename="templates")

urlpatterns = [
    path("settings/", PlatformSettingsView.as_view(), name="platform-settings"),
    path("public/settings/", PublicPlatformSettingsView.as_view(), name="public-platform-settings"),
    path("", include(router.urls)),
]