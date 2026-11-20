"""
Serializers for the core portfolio tables.
"""
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from django.utils.text import slugify
from django.utils import timezone

from apps.common.validators import validate_image_file, validate_cv_file, RESERVED_SLUGS
from apps.common.utils import generate_unique_slug
from ..models import Portfolio, PortfolioContact, SocialLink, ProcessStep, PageIntro


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = "__all__"
        # deleted_at ko read-only karein taake koi API se soft-delete na kar sake
        read_only_fields = ["created_at", "updated_at", "published_at","status", "deleted_at"]
        # Client token ke liye `client` optional hai (backend khud set karta hai)
        extra_kwargs = {"client": {"required": False}}

    def validate_profile_photo(self, value):
        if value: validate_image_file(value)
        return value

    def validate_hero_image(self, value):
        if value: validate_image_file(value)
        return value

    def validate_logo(self, value):
        if value: validate_image_file(value)
        return value

    def validate_cv_file(self, value):
        if value: validate_cv_file(value)
        return value

    def validate_section_visibility(self, value):
        """Ensure section_visibility is a valid dictionary (JSON object)."""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("section_visibility must be a valid JSON object.")
        return value

    def validate_slug(self, value):
        """Case-insensitive unique + reserved check (soft-deleted portfolios bhi count hote hain)."""
        value = value.strip().lower()
        if value in RESERVED_SLUGS:
            raise serializers.ValidationError("This slug is reserved.")
        taken = Portfolio.all_objects.filter(slug__iexact=value)
        if self.instance:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("This slug is already taken.")
        return value

    def validate(self, attrs):
        """
        - Client token: `client` backend khud apne user se set karta hai. Agar frontend
          koi client id bheje aur wo apni na ho to reject (403).
        - Admin: create par `client` zaroori hai.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not user.is_staff:
            own = getattr(user, "client_profile", None)
            if own is None:
                raise PermissionDenied("Only clients or admins can manage portfolios.")
            sent = attrs.get("client")
            if sent is not None and sent.pk != own.pk:
                raise PermissionDenied("You can only manage your own portfolios.")
            attrs["client"] = own
        elif not self.instance and attrs.get("client") is None:
            raise serializers.ValidationError({"client": "This field is required."})
        return attrs

    def create(self, validated_data):
        # 1. Slug generate karein title/full_name se
        base_slug = slugify(validated_data.get("title", validated_data.get("full_name", "portfolio")))
        
        # 2. Agar non-latin title hai aur slug khali reh gaya, toh fallback use karein
        if not base_slug:
            base_slug = "portfolio"
        
        # 3. Reserved slugs check karein
        if base_slug in RESERVED_SLUGS:
            base_slug = f"{base_slug}-portfolio"
        
        # 4. Unique slug generate karein (all_objects use karein taake soft-deleted bhi check hon)
        validated_data["slug"] = generate_unique_slug(
            self.instance, base_slug, queryset=Portfolio.all_objects.all()
        )
        
        # 5. Agar status published hai, toh published_at set karein
        if validated_data.get("status") == "published":
            validated_data["published_at"] = timezone.now()
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        new_status = validated_data.get("status", instance.status)
        if new_status == "published" and instance.status != "published":
            validated_data["published_at"] = timezone.now()
        elif new_status != "published":
            validated_data["published_at"] = None
        return super().update(instance, validated_data)
    def validate_favicon(self, value):
        if value: validate_image_file(value)
        return value
    def validate_total_publications(self, value):
        if value < 0:
            raise serializers.ValidationError("Total publications cannot be negative.")
        return value

    def validate_citations(self, value):
        if value < 0:
            raise serializers.ValidationError("Citations cannot be negative.")
        return value

    def validate_h_index(self, value):
        if value < 0:
            raise serializers.ValidationError("H-index cannot be negative.")
        return value


class PortfolioContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioContact
        fields = "__all__"


class SocialLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialLink
        fields = "__all__"


class ProcessStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessStep
        fields = "__all__"

    def validate(self, attrs):
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        if portfolio and not self.instance:
            if portfolio.process_steps.count() >= 4:
                raise serializers.ValidationError({"detail": "Maximum of 4 process steps allowed per portfolio."})
        return attrs


class PageIntroSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageIntro
        fields = "__all__"

    def validate(self, attrs):
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        page = attrs.get("page", getattr(self.instance, "page", None))
        if portfolio and page:
            existing = PageIntro.objects.filter(portfolio=portfolio, page=page)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"page": "An intro already exists for this page."})
        return attrs