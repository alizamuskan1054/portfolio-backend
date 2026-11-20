from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PortfolioViewSet, PortfolioContactViewSet, SocialLinkViewSet, 
    ProcessStepViewSet, PageIntroViewSet,
    EducationViewSet, ExperienceViewSet, ResearchInterestViewSet,
    ExpertiseViewSet, AwardViewSet, MembershipViewSet,
    ServiceViewSet, CategoryViewSet, ProjectViewSet, ProjectImageViewSet,
    PublicationViewSet, BlogViewSet, TestimonialViewSet, ContactMessageViewSet
)

router = DefaultRouter()

# Core
router.register(r"portfolios", PortfolioViewSet, basename="portfolios")
router.register(r"contacts", PortfolioContactViewSet, basename="contacts")
router.register(r"social-links", SocialLinkViewSet, basename="social-links")
router.register(r"process-steps", ProcessStepViewSet, basename="process-steps")
router.register(r"page-intros", PageIntroViewSet, basename="page-intros")

# Academic
router.register(r"educations", EducationViewSet, basename="educations")
router.register(r"experiences", ExperienceViewSet, basename="experiences")
router.register(r"research-interests", ResearchInterestViewSet, basename="research-interests")
router.register(r"expertise", ExpertiseViewSet, basename="expertise")
router.register(r"awards", AwardViewSet, basename="awards")
router.register(r"memberships", MembershipViewSet, basename="memberships")

# Content
router.register(r"services", ServiceViewSet, basename="services")
router.register(r"categories", CategoryViewSet, basename="categories")
router.register(r"projects", ProjectViewSet, basename="projects")
router.register(r"project-images", ProjectImageViewSet, basename="project-images")
router.register(r"publications", PublicationViewSet, basename="publications")
router.register(r"blogs", BlogViewSet, basename="blogs")
router.register(r"testimonials", TestimonialViewSet, basename="testimonials")
router.register(r"messages", ContactMessageViewSet, basename="messages")

urlpatterns = [
    path("", include(router.urls)),
]