from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import NotificationViewSet

router = SimpleRouter()
router.register(r"", NotificationViewSet, basename="notifications")

urlpatterns = [
    path("", include(router.urls)),
]
