"""
Serializers for academic information models.
"""
from rest_framework import serializers
from django.utils import timezone
from ..models import Education, Experience, ResearchInterest, Expertise, Award, Membership


class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = "__all__"

    def validate(self, attrs):
        start_year = attrs.get("start_year", getattr(self.instance, "start_year", None))
        end_year = attrs.get("end_year", getattr(self.instance, "end_year", None))
        if start_year and end_year and end_year < start_year:
            raise serializers.ValidationError({"end_year": "End year must be after start year."})
        
        # Duplicate check (active records only)
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        degree = attrs.get("degree", getattr(self.instance, "degree", None))
        institution = attrs.get("institution", getattr(self.instance, "institution", None))
        
        if portfolio and degree and institution:
            # all_objects use karein taake soft-deleted filter ho sakein
            existing = Education.objects.filter(
                portfolio=portfolio, degree__iexact=degree.strip(), institution__iexact=institution.strip()
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"detail": "This education entry already exists."})
        
        return attrs


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = "__all__"

    def validate(self, attrs):
        is_current = attrs.get("is_current", getattr(self.instance, "is_current", False))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        
        # Rule 1: Agar is_current=True hai, toh end_date nahi hona chahiye
        if is_current and end_date:
            raise serializers.ValidationError({"end_date": "End date should be empty if it is a current job."})
        
        # Rule 2: Agar is_current=False hai, toh end_date hona chahiye
        if not is_current and not end_date:
            raise serializers.ValidationError({"end_date": "End date is required if it is not a current job."})
        
        # Rule 3: end_date start_date ke baad hona chahiye
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
            
        # Duplicate check
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        job_title = attrs.get("job_title", getattr(self.instance, "job_title", None))
        organization = attrs.get("organization", getattr(self.instance, "organization", None))
        
        if portfolio and job_title and organization:
            existing = Experience.objects.filter(
                portfolio=portfolio, job_title__iexact=job_title.strip(), organization__iexact=organization.strip()
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"detail": "This experience entry already exists."})
        
        return attrs


class ResearchInterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchInterest
        fields = "__all__"

    def validate(self, attrs):
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        title = attrs.get("title", getattr(self.instance, "title", None))
        
        if portfolio and title:
            existing = ResearchInterest.objects.filter(portfolio=portfolio, title__iexact=title.strip())
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"title": "This research interest already exists."})
        return attrs


class ExpertiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expertise
        fields = "__all__"

    def validate(self, attrs):
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        
        if portfolio and name:
            existing = Expertise.objects.filter(portfolio=portfolio, name__iexact=name.strip())
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"name": "This expertise already exists."})
        return attrs


class AwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Award
        fields = "__all__"

    def validate(self, attrs):
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        title = attrs.get("title", getattr(self.instance, "title", None))
        year = attrs.get("year", getattr(self.instance, "year", None))
        
        if portfolio and title and year:
            existing = Award.objects.filter(portfolio=portfolio, title__iexact=title.strip(), year=year)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"title": "An award with this title and year already exists."})
        return attrs
class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = "__all__"

    def validate(self, attrs):
        # 1. Future Date Check
        membership_date = attrs.get("membership_date", getattr(self.instance, "membership_date", None))
        if membership_date and membership_date > timezone.now().date():
            raise serializers.ValidationError({"membership_date": "Membership date cannot be in the future."})

        # 2. Duplicate Entry Check
        portfolio = attrs.get("portfolio", getattr(self.instance, "portfolio", None))
        org_name = attrs.get("organization_name", getattr(self.instance, "organization_name", None))
        role = attrs.get("role", getattr(self.instance, "role", None))
        
        if portfolio and org_name and role:
            existing = Membership.objects.filter(
                portfolio=portfolio, organization_name__iexact=org_name.strip(), role__iexact=role.strip()
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"detail": "This membership entry already exists."})
                
        return attrs