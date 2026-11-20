"""
API Views for the Dashboard.
Allows the admin to see recent activity and platform statistics.
"""
from rest_framework.views import APIView
from rest_framework import generics

from apps.common.permissions import IsVerifiedAdmin
from apps.common.responses import success_response
from apps.common.pagination import StandardResultsPagination
from apps.portfolios.models import ActivityLog, Portfolio
from apps.clients.models import Client
from .serializers import RecentActivitySerializer


class RecentActivityListView(generics.ListAPIView):
    """
    Returns the latest 10 activity logs for the dashboard timeline.
    """
    serializer_class = RecentActivitySerializer
    permission_classes = [IsVerifiedAdmin]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        # N+1 fix: select_related taake actor/user ki alag query na chale
        return ActivityLog.objects.select_related("actor", "client", "portfolio").order_by("-created_at")

    def list(self, request, *args, **kwargs):
        # Professional fix: Pehle filter karein, phir slice karein
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset[:10]  # Limit after filtering
        
        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data)


class DashboardStatsView(APIView):
    """
    Returns high-level statistics for the Dashboard cards.
    Only the 4 cards specified in the planning are returned.
    """
    permission_classes = [IsVerifiedAdmin]

    def get(self, request):
        # 4 Cards
        total_clients = Client.objects.count()
        total_portfolios = Portfolio.objects.count()
        published_portfolios = Portfolio.objects.filter(status="published").count()
        draft_portfolios = Portfolio.objects.filter(status="draft").count()

        data = {
            "total_clients": total_clients,
            "total_portfolios": total_portfolios,
            "published_portfolios": published_portfolios,
            "draft_portfolios": draft_portfolios,
        }
        return success_response(data=data)