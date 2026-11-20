from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/config/", include("apps.site_config.urls")),
    path("api/clients/", include("apps.clients.urls")),
    path("api/portfolios/", include("apps.portfolios.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/public/", include("apps.public_site.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
]