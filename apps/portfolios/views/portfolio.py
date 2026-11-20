"""
Views for the core portfolio tables.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated # <--- IsVerifiedAdmin ki jagah
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone

from apps.common.pagination import StandardResultsPagination
from apps.common.responses import success_response, error_response
from apps.common.validators import RESERVED_SLUGS
from apps.notifications.models import Notification
from apps.notifications.services import notify_portfolio_event

from ..models import (
    Portfolio, PortfolioContact, SocialLink, ProcessStep, PageIntro, ActivityLog
)
from ..serializers import (
    PortfolioSerializer, PortfolioContactSerializer, SocialLinkSerializer,
    ProcessStepSerializer, PageIntroSerializer
)


MAX_PORTFOLIOS_PER_CLIENT = 5


class PortfolioViewSet(viewsets.ModelViewSet):
    """
    CRUD for Portfolios.
    Includes custom actions: publish, unpublish.
    """
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated] #Admin aur Client dono access kar sakte hain
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "full_name", "slug"]
    filterset_fields = ["status", "client", "template"]
    ordering_fields = ["created_at", "title", "status"]

    def get_queryset(self):
        user = self.request.user
        # Agar Admin hai, toh saare portfolios dekh sake
        if user.is_staff:
            return Portfolio.objects.all()
        
        # Agar Client hai, toh sirf apne portfolios dekh sake
        elif hasattr(user, 'client_profile'):
            return Portfolio.objects.filter(client=user.client_profile)
            
        return Portfolio.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user
        if not user.is_staff:
            client = getattr(user, "client_profile", None)
            if client is None:
                return error_response(message="Only clients or admins can create portfolios.", status_code=403)
            # Soft-deleted portfolios count mein nahi (Portfolio.objects unhein chupata hai)
            if Portfolio.objects.filter(client=client).count() >= MAX_PORTFOLIOS_PER_CLIENT:
                return error_response(
                    message=f"You can create up to {MAX_PORTFOLIOS_PER_CLIENT} portfolios.",
                    status_code=403,
                )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_staff:
            # Admin kisi ke bhi liye bana sakta hai
            portfolio = serializer.save()
        else:
            # Client: serializer.validate() pehle hi client set kar chuka hai; status hamesha draft
            portfolio = serializer.save(client=user.client_profile, status="draft")
            notify_portfolio_event(portfolio, Notification.PORTFOLIO_CREATED, user)

    def destroy(self, request, *args, **kwargs):
        """Soft delete the portfolio instead of hard delete."""
        instance = self.get_object()
        instance.soft_delete()
        notify_portfolio_event(instance, Notification.PORTFOLIO_DELETED, request.user)
        return success_response(message="Portfolio deleted successfully (can be recovered).")

    @action(detail=True, methods=["post"], url_path="publish")
    def publish_portfolio(self, request, pk=None):
        """Set portfolio status to published."""
        portfolio = self.get_object()  # get_queryset handle kar lega ke yeh usi ka portfolio hai

        missing = []
        if not (portfolio.title or "").strip():
            missing.append("title")
        if not (portfolio.slug or "").strip():
            missing.append("slug")
        if not portfolio.template_id:
            missing.append("template")
        if missing:
            return error_response(
                message=f"Cannot publish: please set {', '.join(missing)} first.",
                errors={f: ["This field is required to publish."] for f in missing},
            )

        portfolio.status = "published"
        portfolio.published_at = timezone.now()
        portfolio.save()

        ActivityLog.objects.create(
            actor=request.user,
            action="portfolio_published",
            client=portfolio.client,
            portfolio=portfolio,
            description=f"Portfolio '{portfolio.title}' published"
        )
        notify_portfolio_event(portfolio, Notification.PORTFOLIO_PUBLISHED, request.user)
        return success_response(message="Portfolio published successfully.")

    @action(detail=True, methods=["post"], url_path="unpublish")
    def unpublish_portfolio(self, request, pk=None):
        """Set portfolio status to unpublished."""
        portfolio = self.get_object()
        portfolio.status = "unpublished"
        portfolio.published_at = None
        portfolio.save()

        ActivityLog.objects.create(
            actor=request.user,
            action="portfolio_unpublished",
            client=portfolio.client,
            portfolio=portfolio,
            description=f"Portfolio '{portfolio.title}' unpublished"
        )
        notify_portfolio_event(portfolio, Notification.PORTFOLIO_UNPUBLISHED, request.user)
        return success_response(message="Portfolio unpublished successfully.")

    @action(detail=False, methods=["get"], url_path="check-slug")
    def check_slug(self, request):
        """Check if a slug is available (works for both Admin and Client)."""
        slug = request.query_params.get("slug", "").strip().lower()
        if not slug:
            return success_response(data={"available": False, "message": "Slug is required."})
        
        if slug in RESERVED_SLUGS:
            return success_response(data={"available": False, "message": "This slug is reserved."})

        taken = Portfolio.all_objects.filter(slug__iexact=slug)
        # Edit form: apni hi portfolio ka slug "taken" na dikhe (?portfolio=<id>)
        own_id = request.query_params.get("portfolio")
        if own_id and own_id.isdigit():
            taken = taken.exclude(pk=int(own_id))
        is_taken = taken.exists()
        
        return success_response(data={
            "available": not is_taken,
            "slug": slug,
            "message": "Slug is available." if not is_taken else "Slug is already taken."
        })


# ==========================================
# Child Viewsets (Security Fix)
# ==========================================
# In sab mein bhi permission_classes change karni hai

class BaseChildViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated] # Admin aur Client dono ke liye

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        
        # Security filter based on role
        if not user.is_staff:
            if hasattr(user, 'client_profile'):
                qs = qs.filter(portfolio__client=user.client_profile)
            else:
                return qs.none()
                
        portfolio_id = self.request.query_params.get("portfolio")
        if portfolio_id:
            return qs.filter(portfolio_id=portfolio_id)
        return qs


class PortfolioContactViewSet(BaseChildViewSet):
    queryset = PortfolioContact.objects.all()
    serializer_class = PortfolioContactSerializer


class SocialLinkViewSet(BaseChildViewSet):
    queryset = SocialLink.objects.all()
    serializer_class = SocialLinkSerializer


class ProcessStepViewSet(BaseChildViewSet):
    queryset = ProcessStep.objects.all()
    serializer_class = ProcessStepSerializer


class PageIntroViewSet(BaseChildViewSet):
    queryset = PageIntro.objects.all()
    serializer_class = PageIntroSerializer