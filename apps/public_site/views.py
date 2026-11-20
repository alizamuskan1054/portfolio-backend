"""
Public API Views.
"""
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.throttling import AnonRateThrottle
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from rest_framework.throttling import ScopedRateThrottle
from apps.common.responses import success_response, error_response
from apps.portfolios.models import (
    Portfolio, Education, Experience, ResearchInterest, Expertise, Award, Membership,
    Service, Project, Publication, Blog, Testimonial, Category, ContactMessage
)
from .serializers import (
    PublicPortfolioSerializer, PublicContactSerializer, PublicPageIntroSerializer,
    PublicProcessStepSerializer, PublicEducationSerializer, PublicExperienceSerializer,
    PublicResearchInterestSerializer, PublicExpertiseSerializer, PublicAwardSerializer,
    PublicMembershipSerializer, PublicServiceSerializer, PublicProjectSerializer,
    PublicPublicationSerializer, PublicBlogSerializer, PublicTestimonialSerializer,
    PublicContactMessageSerializer 
)
from .pdf import generate_portfolio_pdf


def get_published_portfolio(slug):
    """
    Helper to fetch a portfolio only if:
    - It is published
    - The portfolio itself is not soft-deleted
    - The client (owner) is not soft-deleted
    """
    return get_object_or_404(
        Portfolio, 
        slug=slug, 
        status="published",
        deleted_at__isnull=True,
        client__deleted_at__isnull=True
    )


class PublicPortfolioDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        portfolio = get_published_portfolio(slug)
        contact = getattr(portfolio, "contact", None)
        page_intros = portfolio.page_intros.all()
        process_steps = portfolio.process_steps.all()

        data = {
            "portfolio": PublicPortfolioSerializer(portfolio).data,
            "contact": PublicContactSerializer(contact).data if contact else None,
            "page_intros": PublicPageIntroSerializer(page_intros, many=True).data,
            "process_steps": PublicProcessStepSerializer(process_steps, many=True).data,
        }
        return success_response(data=data)


class PublicAcademicDataView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        portfolio = get_published_portfolio(slug)
        data = {
            "educations": PublicEducationSerializer(portfolio.education_set.all(), many=True).data,
            "experiences": PublicExperienceSerializer(portfolio.experience_set.all(), many=True).data,
            "research_interests": PublicResearchInterestSerializer(portfolio.researchinterest_set.all(), many=True).data,
            "expertise": PublicExpertiseSerializer(portfolio.expertise_set.all(), many=True).data,
            "awards": PublicAwardSerializer(portfolio.award_set.all(), many=True).data,
            "memberships": PublicMembershipSerializer(portfolio.membership_set.all(), many=True).data,
        }
        return success_response(data=data)


class PublicServicesView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        portfolio = get_published_portfolio(slug)
        services = portfolio.service_set.filter(is_visible=True).order_by("display_order")
        return success_response(data=PublicServiceSerializer(services, many=True).data)


class PublicServiceDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug, service_id):
        portfolio = get_published_portfolio(slug)
        service = get_object_or_404(Service, id=service_id, portfolio=portfolio, is_visible=True)
        return success_response(data=PublicServiceSerializer(service).data)


class PublicProjectsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        portfolio = get_published_portfolio(slug)
        # prefetch_related fix for N+1 query
        projects = portfolio.project_set.filter(is_visible=True).prefetch_related("gallery_images").order_by("display_order")
        return success_response(data=PublicProjectSerializer(projects, many=True).data)


class PublicProjectDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug, project_id):
        portfolio = get_published_portfolio(slug)
        project = get_object_or_404(
            Project.objects.prefetch_related("gallery_images"), 
            id=project_id, portfolio=portfolio, is_visible=True
        )
        return success_response(data=PublicProjectSerializer(project).data)


class PublicPublicationsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        portfolio = get_published_portfolio(slug)
        publications = portfolio.publication_set.all().order_by("display_order", "-year")
        return success_response(data=PublicPublicationSerializer(publications, many=True).data)


class PublicBlogsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        portfolio = get_published_portfolio(slug)
        blogs = portfolio.blog_set.filter(status="published").order_by("-published_at")
        return success_response(data=PublicBlogSerializer(blogs, many=True).data)


class PublicBlogDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug, blog_slug):
        portfolio = get_published_portfolio(slug)
        blog = get_object_or_404(Blog, slug=blog_slug, portfolio=portfolio, status="published")
        return success_response(data=PublicBlogSerializer(blog).data)


class PublicTestimonialsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        portfolio = get_published_portfolio(slug)
        testimonials = portfolio.testimonial_set.filter(is_visible=True).order_by("display_order")
        return success_response(data=PublicTestimonialSerializer(testimonials, many=True).data)

class PublicContactFormView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact_form"

    def post(self, request, slug):
        portfolio = get_published_portfolio(slug)
        
        # Professional validation via Serializer
        serializer = PublicContactMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(errors=serializer.errors, message="Validation failed.")
        
        # 1. Message save karein
        message = serializer.save(portfolio=portfolio)

        # In-app notification for the portfolio's client (kabhi form ko fail nahi karti)
        from apps.notifications.services import notify_contact_message
        notify_contact_message(message)

        # 2. Email Notification Logic
        contact = getattr(portfolio, "contact", None)
        notify_email = None
        
        if contact and contact.notification_email:
            notify_email = contact.notification_email
        elif contact and contact.email:
            notify_email = contact.email
        else:
            notify_email = settings.DEFAULT_FROM_EMAIL

        if notify_email:
            try:
                send_mail(
                    subject=f"New Contact: {message.subject}",
                    message=f"From: {message.full_name} ({message.email})\n\n{message.message}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[notify_email],
                    fail_silently=True, # SMTP fail ho toh visitor ko error na dikhe
                )
            except Exception as e:
                print(f"Email notification failed: {e}")

        # 3. Success Message return karein
        success_msg = "Thank you for your message."
        if contact and contact.form_success_message:
            success_msg = contact.form_success_message

        return success_response(message=success_msg)

class PortfolioPDFDownloadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]  # <--- AnonRateThrottle ki jagah ScopedRateThrottle
    throttle_scope = "pdf_download"

    def get(self, request, slug):
        portfolio = get_published_portfolio(slug)
        try:
            pdf_path = generate_portfolio_pdf(portfolio)
            return FileResponse(
                open(pdf_path, 'rb'), 
                as_attachment=True, 
                filename=f"{portfolio.slug}_portfolio.pdf", 
                content_type="application/pdf"
            )
        except Exception:
            # Test ke mutabiq exact message, internal error details leak na karein
            return error_response(message="PDF generation failed.", status_code=500)