"""
Views for academic information models.
These are simple ViewSets since they are just list tables hanging off a portfolio.
"""
from rest_framework import viewsets
from apps.common.permissions import IsVerifiedAdmin
from apps.common.pagination import StandardResultsPagination
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import Education, Experience, ResearchInterest, Expertise, Award, Membership
from ..serializers import (
    EducationSerializer, ExperienceSerializer, ResearchInterestSerializer,
    ExpertiseSerializer, AwardSerializer, MembershipSerializer
)

class BaseAcademicViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for all academic tables.
    Ensures security: Client sirf apna data dekhe, Admin sabka.
    """
    permission_classes = [IsAuthenticated] # <--- YAHAN CHANGE KAREIN
    pagination_class = StandardResultsPagination

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
    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        """Bulk update display_order for academic items."""
        items = request.data # [{"id": 1, "display_order": 0}, ...]
        if not isinstance(items, list):
            return Response({"detail": "Expected a list of objects."}, status=400)

        for item in items:
            item_id = item.get("id")
            new_order = item.get("display_order")
            if item_id is not None and new_order is not None:
                # Security: Ensure client only updates their own items
                self.get_queryset().filter(id=item_id).update(display_order=new_order)

        return Response({"success": True, "message": "Reordered successfully."})

class EducationViewSet(BaseAcademicViewSet):
    queryset = Education.objects.all()
    serializer_class = EducationSerializer


class ExperienceViewSet(BaseAcademicViewSet):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer


class ResearchInterestViewSet(BaseAcademicViewSet):
    queryset = ResearchInterest.objects.all()
    serializer_class = ResearchInterestSerializer


class ExpertiseViewSet(BaseAcademicViewSet):
    queryset = Expertise.objects.all()
    serializer_class = ExpertiseSerializer


class AwardViewSet(BaseAcademicViewSet):
    queryset = Award.objects.all()
    serializer_class = AwardSerializer


class MembershipViewSet(BaseAcademicViewSet):
    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer