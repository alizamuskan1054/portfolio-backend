"""
Shared abstract base models for the Academic Researcher Portfolio Platform.

These classes are inherited by concrete tables so that common fields
(PK, timestamps, ownership, ordering, flags) are defined exactly once.
"""

from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """Every table in the platform inherits this."""
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that hides soft-deleted rows by default."""
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def soft_delete(self):
        return self.update(deleted_at=timezone.now())


class SoftDeleteManager(models.Manager):
    """Default manager: returns only non-deleted rows."""
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class AllObjectsManager(models.Manager):
    """Explicit manager to also see soft-deleted rows (for admin recovery)."""
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteMixin(models.Model):
    """Used by Client and Portfolio only."""
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class PortfolioOwnedMixin(models.Model):
    portfolio = models.ForeignKey(
        "portfolios.Portfolio",
        on_delete=models.CASCADE,
        related_name="%(class)s_set", 
        db_index=True,
    )

    class Meta:
        abstract = True


class OrderedMixin(models.Model):
    """Admin-controlled ordering for every list table."""
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["display_order", "id"]


class FeaturedMixin(models.Model):
    """Used by Service, Project, Publication, Blog."""
    is_featured = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True


class VisibilityMixin(models.Model):
    """Used by Service, Project, Testimonial."""
    is_visible = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True