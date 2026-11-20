"""
Academic information models (Step 3 of the wizard).
Each one has portfolio_id and display_order from mixins.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from apps.common.models import BaseModel, OrderedMixin, PortfolioOwnedMixin
from apps.common.validators import validate_date_range


class Education(BaseModel, PortfolioOwnedMixin, OrderedMixin):
    degree = models.CharField(max_length=255)
    institution = models.CharField(max_length=255)
    field_of_study = models.CharField(max_length=255)
    start_year = models.PositiveIntegerField()
    end_year = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "educations"
        ordering = ["display_order"]

    def clean(self):
        if self.end_year and self.start_year and self.end_year < self.start_year:
            raise ValidationError({"end_year": "End year must be after start year."})


class Experience(BaseModel, PortfolioOwnedMixin, OrderedMixin):
    job_title = models.CharField(max_length=255)
    organization = models.CharField(max_length=255)
    employment_type = models.CharField(max_length=100, null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "experiences"
        ordering = ["display_order"]

    def clean(self):
        if not self.is_current and not self.end_date:
            raise ValidationError({"end_date": "End date is required if not current."})
        if self.end_date:
            validate_date_range(self.start_date, self.end_date)


class ResearchInterest(BaseModel, PortfolioOwnedMixin, OrderedMixin):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "research_interests"
        ordering = ["display_order"]


class Expertise(BaseModel, PortfolioOwnedMixin, OrderedMixin):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "expertise"
        ordering = ["display_order"]


class Award(BaseModel, PortfolioOwnedMixin, OrderedMixin):
    title = models.CharField(max_length=255)
    issuing_organization = models.CharField(max_length=255)
    year = models.PositiveIntegerField()
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "awards"
        ordering = ["display_order"]


class Membership(BaseModel, PortfolioOwnedMixin, OrderedMixin):
    organization_name = models.CharField(max_length=255)
    role = models.CharField(max_length=255)
    membership_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "memberships"
        ordering = ["display_order"]