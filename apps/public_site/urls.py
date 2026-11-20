
from django.urls import path
from .views import (
    PublicPortfolioDetailView, PublicAcademicDataView, PublicServicesView,
    PublicProjectsView, PublicProjectDetailView, PublicPublicationsView,
    PublicBlogsView, PublicBlogDetailView, PublicTestimonialsView, PublicContactFormView,
    PortfolioPDFDownloadView,PublicServiceDetailView
)

urlpatterns = [
    path("<slug:slug>/", PublicPortfolioDetailView.as_view(), name="public-portfolio"),
    path("<slug:slug>/academic/", PublicAcademicDataView.as_view(), name="public-academic"),
    path("<slug:slug>/services/", PublicServicesView.as_view(), name="public-services"),
    path("<slug:slug>/projects/", PublicProjectsView.as_view(), name="public-projects"),
    path("<slug:slug>/projects/<int:project_id>/", PublicProjectDetailView.as_view(), name="public-project-detail"),
    path("<slug:slug>/publications/", PublicPublicationsView.as_view(), name="public-publications"),
    path("<slug:slug>/blogs/", PublicBlogsView.as_view(), name="public-blogs"),
    path("<slug:slug>/blogs/<slug:blog_slug>/", PublicBlogDetailView.as_view(), name="public-blog-detail"),
    path("<slug:slug>/testimonials/", PublicTestimonialsView.as_view(), name="public-testimonials"),
    path("<slug:slug>/contact/", PublicContactFormView.as_view(), name="public-contact"),
    path("<slug:slug>/pdf/", PortfolioPDFDownloadView.as_view(), name="public-portfolio-pdf"),
     path("<slug:slug>/services/<int:service_id>/", PublicServiceDetailView.as_view(), name="public-service-detail"),
]