"""
Serializers for website content models.
"""
from rest_framework import serializers
from django.utils.text import slugify
from django.utils import timezone

from apps.common.validators import validate_image_file
from apps.common.utils import generate_unique_slug
from ..models import (
    Service, Category, Project, ProjectImage, Publication, 
    Blog, Testimonial, ContactMessage, ActivityLog
)


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = "__all__"

    def validate_image(self, value):
        if value: validate_image_file(value)
        return value

    def validate(self, attrs):
        # Rule 1: Only one featured service per portfolio
        is_featured = attrs.get("is_featured", getattr(self.instance, "is_featured", False))
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        
        if is_featured and portfolio:
            existing = Service.objects.filter(portfolio=portfolio, is_featured=True)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"is_featured": "Only one featured service is allowed per portfolio."})
        
        # Rule 2: Duplicate Title Check
        title = attrs.get("title", getattr(self.instance, "title", None))
        if portfolio and title:
            existing_title = Service.objects.filter(portfolio=portfolio, title__iexact=title.strip())
            if self.instance:
                existing_title = existing_title.exclude(pk=self.instance.pk)
            if existing_title.exists():
                raise serializers.ValidationError({"title": "A service with this title already exists."})
                
        return attrs


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ["slug"]

    def validate(self, attrs):
        # Duplicate name check (case-insensitive) for same portfolio and kind
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        
        if portfolio and kind and name:
            existing = Category.objects.filter(
                portfolio=portfolio, 
                kind=kind, 
                name__iexact=name.strip()
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    {"name": f"A {kind} category with this name already exists."}
                )
        return attrs

    def create(self, validated_data):
        # Auto-generate slug from name
        base_slug = slugify(validated_data.get("name", "category"))
        validated_data["slug"] = generate_unique_slug(
            self.instance, 
            base_slug, 
            queryset=Category.objects.filter(portfolio=validated_data["portfolio"], kind=validated_data["kind"])
        )
        return super().create(validated_data)


class ProjectImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectImage
        fields = "__all__"

    def validate_image(self, value):
        if value: validate_image_file(value)
        return value


class ProjectSerializer(serializers.ModelSerializer):
    gallery_images = ProjectImageSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = "__all__"

    def validate_thumbnail(self, value):
        if value: validate_image_file(value)
        return value

    def validate(self, attrs):
        # 1. Duplicate Title Check
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        title = attrs.get("title", getattr(self.instance, "title", None))
        
        if portfolio and title:
            existing = Project.objects.filter(portfolio=portfolio, title__iexact=title.strip())
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"title": "A project with this title already exists."})

        # 2. Year & Status Validation
        status = attrs.get("status", getattr(self.instance, "status", "ongoing"))
        year = attrs.get("year", getattr(self.instance, "year", None))
        current_year = timezone.now().year

        if year:
            if status == "completed" and year > current_year:
                raise serializers.ValidationError(
                    {"year": "A completed project cannot have a future year."}
                )
            
            if status == "ongoing" and year > current_year:
                raise serializers.ValidationError(
                    {"year": "An ongoing project cannot have a future year. Please set the status to 'Planned' if it starts in the future."}
                )

        return attrs


class PublicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publication
        fields = "__all__"

    def validate_cover_image(self, value):
        if value: validate_image_file(value)
        return value

    def validate(self, attrs):
        # Duplicate Title Check
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        title = attrs.get("title", getattr(self.instance, "title", None))
        
        if portfolio and title:
            existing = Publication.objects.filter(portfolio=portfolio, title__iexact=title.strip())
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"title": "A publication with this title already exists."})
        return attrs


class BlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = "__all__"
        read_only_fields = ["slug"]

    def validate_cover_image(self, value):
        if value: validate_image_file(value)
        return value

    def validate(self, attrs):
        # Duplicate Title Check
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        title = attrs.get("title", getattr(self.instance, "title", None))
        
        if portfolio and title:
            existing = Blog.objects.filter(portfolio=portfolio, title__iexact=title.strip())
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"title": "A blog post with this title already exists."})
        return attrs

    def create(self, validated_data):
        # Auto-generate slug unique per portfolio
        base_slug = slugify(validated_data.get("title", "blog-post"))
        validated_data["slug"] = generate_unique_slug(
            self.instance, 
            base_slug, 
            queryset=Blog.objects.filter(portfolio=validated_data["portfolio"])
        )
        if validated_data.get("status") == "published":
            validated_data["published_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # If changing to published, set published_at
        new_status = validated_data.get("status", instance.status)
        if new_status == "published" and instance.status != "published":
            validated_data["published_at"] = timezone.now()
        return super().update(instance, validated_data)


class TestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = "__all__"

    def validate_author_photo(self, value):
        if value: validate_image_file(value)
        return value


class ContactMessageSerializer(serializers.ModelSerializer):
    """Inbox item. Sirf `is_read` writable hai; baqi sab read-only."""
    name = serializers.CharField(source="full_name", read_only=True)
    portfolio_title = serializers.SerializerMethodField()

    class Meta:
        model = ContactMessage
        fields = ["id", "portfolio", "portfolio_title", "name", "full_name", "email",
                  "subject", "inquiry_type", "message", "is_read", "created_at"]
        read_only_fields = [f for f in fields if f != "is_read"]

    def get_portfolio_title(self, obj):
        # Soft-deleted portfolio par FK fetch fail hota hai (base manager unhein chupata hai)
        try:
            return obj.portfolio.title
        except Exception:  # noqa: BLE001
            return None
        


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = "__all__"