"""
Website content models (Step 4).
Includes Service, Category, Project, ProjectImage, Publication, Blog,
Testimonial, ContactMessage, and ActivityLog.
"""
from django.db import models
from .portfolio import Portfolio
from apps.common.models import BaseModel, PortfolioOwnedMixin, OrderedMixin, FeaturedMixin, VisibilityMixin
from apps.common.validators import validate_reserved_slug, validate_image_file


class Service(BaseModel, PortfolioOwnedMixin, OrderedMixin, FeaturedMixin, VisibilityMixin):
    title = models.CharField(max_length=255)
    short_description = models.TextField()
    detailed_description = models.TextField()
    image = models.ImageField(upload_to="services/", null=True, blank=True)
    icon = models.CharField(max_length=100, null=True, blank=True)
    external_link = models.URLField(null=True, blank=True)

    class Meta:
        db_table = "services"
        ordering = ["display_order"]
        constraints = [
            # Only one featured service per portfolio
            models.UniqueConstraint(
                fields=["portfolio"], 
                condition=models.Q(is_featured=True), 
                name="unique_featured_service_per_portfolio"
            )
        ]


# Upar imports mein yeh add karein:
from django.db.models.functions import Lower

class Category(BaseModel, PortfolioOwnedMixin, OrderedMixin):
    """Shared by Projects and Blogs for filter chips."""
    kind = models.CharField(
        max_length=20, 
        choices=[("project", "Project"), ("blog", "Blog")]
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, validators=[validate_reserved_slug])

    class Meta:
        db_table = "categories"
        ordering = ["display_order"]
        constraints = [
            # Same portfolio aur same kind (project/blog) mein same name (case-insensitive) na ho
            models.UniqueConstraint(
                Lower('name'),
                'portfolio',
                'kind',
                name='unique_category_name_per_portfolio_kind'
            )
        ]


class Project(BaseModel, PortfolioOwnedMixin, OrderedMixin, FeaturedMixin, VisibilityMixin):
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects"
    )
    title = models.CharField(max_length=255)
    short_description = models.TextField()
    full_description = models.TextField()
    thumbnail = models.ImageField(upload_to="projects/thumbnails/", null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=[("ongoing", "Ongoing"), ("completed", "Completed"), ("planned", "Planned")],
        default="ongoing"
    )
    year = models.PositiveIntegerField()
    objectives = models.TextField(blank=True, null=True)
    methodology = models.TextField(blank=True, null=True)
    outcomes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "projects"
        ordering = ["display_order"]
        indexes = [models.Index(fields=["portfolio", "is_featured"])]


class ProjectImage(BaseModel, OrderedMixin):
    """Separate table for project gallery images (unlimited per project)."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ImageField(upload_to="projects/gallery/")
    caption = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "project_images"
        ordering = ["display_order"]


class Publication(BaseModel, PortfolioOwnedMixin, OrderedMixin, FeaturedMixin):
    title = models.CharField(max_length=255)
    authors = models.TextField(help_text="Plain text, comma-separated")
    venue = models.CharField(max_length=255)
    year = models.PositiveIntegerField()
    type = models.CharField(
        max_length=50,
        choices=[
            ("journal_article", "Journal Article"), ("conference_paper", "Conference Paper"),
            ("book_chapter", "Book Chapter"), ("book", "Book")
        ]
    )
    abstract = models.TextField(blank=True, null=True)
    doi = models.CharField(max_length=100, blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
    cover_image = models.ImageField(upload_to="publications/", null=True, blank=True)

    class Meta:
        db_table = "publications"
        ordering = ["display_order"]
        indexes = [models.Index(fields=["portfolio", "type", "year"])]


class Blog(BaseModel, PortfolioOwnedMixin, OrderedMixin, FeaturedMixin):
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="blogs"
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, validators=[validate_reserved_slug])
    excerpt = models.TextField()
    content = models.TextField()
    cover_image = models.ImageField(upload_to="blogs/", null=True, blank=True)
    author_name = models.CharField(max_length=255, blank=True, null=True)
    reading_time = models.PositiveIntegerField(help_text="In minutes", default=5)
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("published", "Published")], default="draft")
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "blogs"
        ordering = ["display_order"]
        constraints = [
            models.UniqueConstraint(fields=["portfolio", "slug"], name="unique_blog_slug_per_portfolio")
        ]
        indexes = [models.Index(fields=["portfolio", "status", "-published_at"])]


class Testimonial(BaseModel, PortfolioOwnedMixin, OrderedMixin, VisibilityMixin):
    author_name = models.CharField(max_length=255)
    author_title = models.CharField(max_length=255, null=True, blank=True)
    author_photo = models.ImageField(upload_to="testimonials/", null=True, blank=True)
    quote = models.TextField()

    class Meta:
        db_table = "testimonials"
        ordering = ["display_order"]


class ContactMessage(BaseModel):
    """Public contact form submissions."""
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="messages")
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    inquiry_type = models.CharField(
        max_length=50,
        choices=[
            ("general", "General"), ("collaboration", "Collaboration"),
            ("speaking", "Speaking"), ("research_inquiry", "Research Inquiry"), ("other", "Other")
        ],
        default="general"
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "contact_messages"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["portfolio", "-created_at"])]


class ActivityLog(BaseModel):
    """Tracks admin actions for the Dashboard and Client Detail timeline."""
    actor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)
    action = models.CharField(
        max_length=50,
        choices=[
            ("client_created", "Client Created"), ("portfolio_created", "Portfolio Created"),
            ("portfolio_updated", "Portfolio Updated"), ("portfolio_published", "Portfolio Published"),
            ("portfolio_unpublished", "Portfolio Unpublished")
        ]
    )
    # SET_NULL so logs survive client/portfolio deletion
    client = models.ForeignKey("clients.Client", on_delete=models.SET_NULL, null=True, blank=True)
    portfolio = models.ForeignKey(Portfolio, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(help_text="Snapshot, e.g., 'Portfolio Dr. Ahmad published'")

    class Meta:
        db_table = "activity_logs"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"])]