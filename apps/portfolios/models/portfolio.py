"""
Core models for the Portfolio.
"""
from django.db import models
from django.db.models.functions import Lower
from apps.common.models import BaseModel, SoftDeleteMixin, OrderedMixin, SoftDeleteManager
from apps.common.validators import validate_reserved_slug


class Portfolio(BaseModel, SoftDeleteMixin):
    """The main hub. A client can own up to 5 portfolios (limit enforced in the API)."""
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    template = models.ForeignKey(
        "site_config.Template",
        on_delete=models.PROTECT,
        related_name="portfolios",
    )
    slug = models.SlugField(
        max_length=255, unique=True, db_index=True,
        validators=[validate_reserved_slug],
    )
    title = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    profile_photo = models.ImageField(upload_to="portfolios/", null=True, blank=True)
    hero_image = models.ImageField(upload_to="portfolios/hero/", null=True, blank=True)
    logo = models.ImageField(upload_to="portfolios/logos/", null=True, blank=True)
    favicon = models.ImageField(upload_to="portfolios/favicons/", null=True, blank=True)
    cv_file = models.FileField(upload_to="portfolios/cv/", null=True, blank=True)
    short_intro = models.TextField(blank=True, null=True)
    biography = models.TextField(blank=True, null=True)
    
    # NAYA FIELD: Frontend section visibility settings store karne ke liye
    section_visibility = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Stores frontend visibility settings for sections (e.g., {'home': true, 'about': false})"
    )
    
    total_publications = models.PositiveIntegerField(default=0)
    citations = models.PositiveIntegerField(default=0)
    h_index = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[("draft", "Draft"), ("published", "Published"), ("unpublished", "Unpublished")],
        default="draft", db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()

    class Meta:
        db_table = "portfolios"
        ordering = ["-created_at"]
        base_manager_name = "objects"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            # Slug case-insensitive unique (soft-deleted rows included)
            models.UniqueConstraint(Lower("slug"), name="unique_portfolio_slug_ci"),
        ]

    def __str__(self):
        return f"{self.title} ({self.client.full_name})"

class PortfolioContact(BaseModel):
    """One-to-one contact info for a portfolio."""
    portfolio = models.OneToOneField(Portfolio, on_delete=models.CASCADE, related_name="contact")
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    notification_email = models.EmailField(null=True, blank=True)
    form_success_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "portfolio_contacts"


class SocialLink(BaseModel):
    """Social media and academic profile links."""
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="social_links")
    platform = models.CharField(
        max_length=50,
        choices=[
            ("linkedin", "LinkedIn"), ("google_scholar", "Google Scholar"),
            ("researchgate", "ResearchGate"), ("orcid", "ORCID"),
            ("github", "GitHub"), ("instagram", "Instagram"),
            ("twitter", "Twitter"), ("whatsapp", "WhatsApp"),
        ],
    )
    url = models.URLField()

    class Meta:
        db_table = "social_links"
        constraints = [
            models.UniqueConstraint(fields=["portfolio", "platform"], name="unique_social_per_portfolio")
        ]


class ProcessStep(BaseModel, OrderedMixin):
    """How I Work steps (max 4)."""
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="process_steps")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "process_steps"
        ordering = ["display_order"]


class PageIntro(BaseModel):
    """Text content for each page's headings and CTAs."""
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="page_intros")
    page = models.CharField(
        max_length=20,
        choices=[
            ("home", "Home"), ("services", "Services"),
            ("projects", "Projects"), ("publications", "Publications"),
            ("blogs", "Blogs"), ("contact", "Contact"), ("about", "About"),
        ],
    )
    title = models.CharField(max_length=255, blank=True, null=True)
    intro = models.TextField(blank=True, null=True)
    cta_text = models.TextField(blank=True, null=True)
    cta_button_label = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "page_intros"
        ordering = ["page", "id"]
        constraints = [
            models.UniqueConstraint(fields=["portfolio", "page"], name="unique_page_per_portfolio")
        ]