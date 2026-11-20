from django.urls import path
from .views import RecentActivityListView, DashboardStatsView

urlpatterns = [
    path("stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("recent-activity/", RecentActivityListView.as_view(), name="dashboard-recent-activity"),
]