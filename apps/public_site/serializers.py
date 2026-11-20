"""
Serializers for the public site.
These are optimized to only return what the public template needs.
"""
from rest_framework import serializers
from apps.portfolios.models import (
    Portfolio, PortfolioContact, SocialLink, ProcessStep, PageIntro,
    Education, Experience, ResearchInterest, Expertise, Award, Membership,
    Service, Category, Project, ProjectImage, Publication, Blog, Testimonial,
    ContactMessage
)


class PublicSocialLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialLink
        fields = ["platform", "url"]


class PublicPortfolioSerializer(serializers.ModelSerializer):
    social_links = PublicSocialLinkSerializer(many=True, read_only=True)
    cv_url = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = [
            "slug", "title", "full_name", "designation", "profile_photo", 
            "hero_image", "logo", "short_intro", "biography","favicon",
            "total_publications", "citations", "h_index", "social_links", "cv_url"
        ]

    def get_cv_url(self, obj):
        if obj.cv_file:
            return obj.cv_file.url
        return None


class PublicContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioContact
        fields = ["email", "phone", "city", "country"]


class PublicPageIntroSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageIntro
        fields = ["page", "title", "intro", "cta_text", "cta_button_label"]


class PublicProcessStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessStep
        fields = ["title", "description", "display_order"]


class PublicEducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = ["degree", "institution", "field_of_study", "start_year", "end_year", "description"]


class PublicExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = ["job_title", "organization", "employment_type", "start_date", "end_date", "is_current", "description"]


class PublicResearchInterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchInterest
        fields = ["title", "description"]


class PublicExpertiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expertise
        fields = ["name", "description"]


class PublicAwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Award
        fields = ["title", "issuing_organization", "year", "description"]


class PublicMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["organization_name", "role", "membership_date", "description"]


class PublicServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "title", "short_description", "detailed_description", "image", "icon", "external_link", "is_featured"]


class PublicProjectImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectImage
        fields = ["id", "image", "caption"]


class PublicProjectSerializer(serializers.ModelSerializer):
    gallery_images = PublicProjectImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Project
        fields = ["id", "title", "short_description", "full_description", "thumbnail", "status", "year", "objectives", "methodology", "outcomes", "gallery_images", "is_featured"]


class PublicPublicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publication
        fields = ["id", "title", "authors", "venue", "year", "type", "abstract", "doi", "external_url", "cover_image", "is_featured"]


class PublicBlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = ["id", "title", "slug", "excerpt", "content", "cover_image", "author_name", "reading_time", "published_at", "is_featured"]


class PublicTestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = ["id", "author_name", "author_title", "author_photo", "quote"]


# Contact Form ke liye serializer
class PublicContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ["full_name", "email", "subject", "inquiry_type", "message"]

    def validate_full_name(self, value):
        if len(value) > 255:
            raise serializers.ValidationError("Full name must be less than 255 characters.")
        return value

    def validate_subject(self, value):
        if len(value) > 255:
            raise serializers.ValidationError("Subject must be less than 255 characters.")
        return value

    def validate_inquiry_type(self, value):
        valid_types = ["general", "collaboration", "speaking", "research_inquiry", "other"]
        if value not in valid_types:
            raise serializers.ValidationError("Invalid inquiry type.")
        return value