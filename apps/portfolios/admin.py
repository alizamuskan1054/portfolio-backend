from django.contrib import admin
from .models import (
    Portfolio, PortfolioContact, SocialLink, ProcessStep, PageIntro,
    Education, Experience, ResearchInterest, Expertise, Award, Membership,
    Service, Category, Project, ProjectImage, Publication, Blog, Testimonial, ContactMessage, ActivityLog
)

@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "status", "slug", "created_at")
    list_filter = ("status", "template")
    search_fields = ("title", "full_name", "slug", "client__full_name")
    prepopulated_fields = {"slug": ("title",)} # Auto-fill slug from title

@admin.register(PortfolioContact)
class PortfolioContactAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "email", "phone", "city", "country")
    search_fields = ("portfolio__title", "email")

@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "platform", "url")
    list_filter = ("platform",)

@admin.register(ProcessStep)
class ProcessStepAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "title", "display_order")
    list_filter = ("portfolio",)

@admin.register(PageIntro)
class PageIntroAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "page", "title")
    list_filter = ("page",)

@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "degree", "institution", "start_year", "end_year")
    search_fields = ("degree", "institution")

@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "job_title", "organization", "is_current")
    list_filter = ("is_current",)

@admin.register(ResearchInterest)
class ResearchInterestAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "title")

@admin.register(Expertise)
class ExpertiseAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "name")

@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "title", "issuing_organization", "year")

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "organization_name", "role")

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "title", "is_featured", "is_visible", "display_order")
    list_filter = ("is_featured", "is_visible")

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "name", "kind", "slug")
    list_filter = ("kind",)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "title", "category", "status", "year", "is_featured", "is_visible")
    list_filter = ("status", "is_featured", "is_visible")
    search_fields = ("title", "short_description")

@admin.register(ProjectImage)
class ProjectImageAdmin(admin.ModelAdmin):
    list_display = ("project", "caption", "display_order")

@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "title", "venue", "year", "type", "is_featured")
    list_filter = ("type", "year", "is_featured")
    search_fields = ("title", "authors", "venue")

@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "title", "status", "author_name", "is_featured", "published_at")
    list_filter = ("status", "is_featured")
    search_fields = ("title", "slug", "excerpt")

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "author_name", "author_title", "is_visible")
    list_filter = ("is_visible",)

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "full_name", "email", "subject", "inquiry_type", "is_read", "created_at")
    list_filter = ("is_read", "inquiry_type")
    search_fields = ("full_name", "email", "subject")

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "description", "created_at")
    list_filter = ("action",)
    search_fields = ("description",)
    