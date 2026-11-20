from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientViewSet,PortalMeView

router = DefaultRouter()
router.register(r"", ClientViewSet, basename="clients")

urlpatterns = [
    path("me/", PortalMeView.as_view(), name="portal-me"),
    path("", include(router.urls)),
]