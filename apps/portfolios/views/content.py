"""
Views for website content models.
Uses the same security pattern: always filter by portfolio.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.common.responses import success_response, error_response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from apps.common.pagination import StandardResultsPagination
from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from apps.common.permissions import IsVerifiedAdmin
from apps.common.pagination import StandardResultsPagination
from rest_framework.permissions import IsAuthenticated

from ..models import (
    Service, Category, Project, ProjectImage, Publication, 
    Blog, Testimonial, ContactMessage
)
from ..serializers import (
    ServiceSerializer, CategorySerializer, ProjectSerializer, ProjectImageSerializer,
    PublicationSerializer, BlogSerializer, TestimonialSerializer, ContactMessageSerializer
)
class BaseContentViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for website content.
    Ensures security: Client sirf apna data dekhe, Admin sabka.
    """
    permission_classes = [IsAuthenticated] # <--- YAHAN CHANGE KAREIN
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

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


class ServiceViewSet(BaseContentViewSet):
    """CRUD for Services."""
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    search_fields = ["title", "short_description"]
    filterset_fields = ["is_featured", "is_visible"]
    ordering_fields = ["display_order", "created_at"]

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        """
        Bulk update display_order.
        Request Body: [{"id": 1, "display_order": 0}, {"id": 2, "display_order": 1}]
        """
        items = request.data
        if not isinstance(items, list):
            return error_response(message="Expected a list of objects.")

        for item in items:
            service_id = item.get("id")
            new_order = item.get("display_order")
            if service_id is not None and new_order is not None:
                # Security: Only update services that belong to the same portfolio (optional but recommended)
                Service.objects.filter(id=service_id).update(display_order=new_order)

        return success_response(message="Services reordered successfully.")


class CategoryViewSet(BaseContentViewSet):
    """CRUD for Categories (shared by Projects and Blogs)."""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filterset_fields = ["kind"]
    search_fields = ["name"]


class ProjectViewSet(BaseContentViewSet):
    """CRUD for Projects."""
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    search_fields = ["title", "short_description"]
    filterset_fields = ["status", "is_featured", "is_visible", "category"]
    ordering_fields = ["display_order", "year", "created_at"]


class ProjectImageViewSet(viewsets.ModelViewSet):
    """
    CRUD for Project Gallery Images.
    Security check: filtered by project_id.
    """
    queryset = ProjectImage.objects.all()
    serializer_class = ProjectImageSerializer
    permission_classes = [IsVerifiedAdmin]
    
    def get_queryset(self):
        qs = super().get_queryset()
        # Filter images by the specific project
        project_id = self.request.query_params.get("project")
        if project_id:
            return qs.filter(project_id=project_id)
        return qs


class PublicationViewSet(BaseContentViewSet):
    """CRUD for Publications."""
    queryset = Publication.objects.all()
    serializer_class = PublicationSerializer
    search_fields = ["title", "authors", "venue"]
    filterset_fields = ["type", "year", "is_featured"]
    ordering_fields = ["display_order", "year", "created_at"]


class BlogViewSet(BaseContentViewSet):
    """CRUD for Blog Posts."""
    queryset = Blog.objects.all()
    serializer_class = BlogSerializer
    search_fields = ["title", "excerpt", "content"]
    filterset_fields = ["status", "category", "is_featured"]
    ordering_fields = ["display_order", "published_at", "created_at"]


class TestimonialViewSet(BaseContentViewSet):
    """CRUD for Testimonials."""
    queryset = Testimonial.objects.all()
    serializer_class = TestimonialSerializer
    search_fields = ["author_name", "quote"]
    filterset_fields = ["is_visible"]
    ordering_fields = ["display_order", "created_at"]

class ContactMessageViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, 
    viewsets.GenericViewSet
):
    """
    Inbox messages for Admin and Clients. 
    Clients can only see messages for their own portfolios.
    """
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    http_method_names = ["get", "patch", "head", "options"]
    
    def get_queryset(self):
        qs = super().get_queryset().order_by('-created_at')
        user = self.request.user
        
        # Agar Admin hai, toh sab dekh sake
        if user.is_staff:
            pass # Saare messages allowed
            
        # Agar Client hai, toh sirf apne messages
        elif hasattr(user, 'client_profile'):
            qs = qs.filter(portfolio__client=user.client_profile)
        else:
            return qs.none()

        # Filter by specific portfolio (dashboard se)
        portfolio_id = self.request.query_params.get("portfolio")
        if portfolio_id:
            return qs.filter(portfolio_id=portfolio_id)
        return qs

    # PATCH sirf `is_read` badalta hai (serializer ke baqi fields read-only hain)