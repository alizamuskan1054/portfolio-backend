"""
Client model. Clients are data records managed by the admin, not platform users.
"""
from django.conf import settings
from django.db import models
from apps.common.models import BaseModel, SoftDeleteMixin


class Client(BaseModel, SoftDeleteMixin):
    """
    Represents a researcher/client whose portfolio is managed by the admin.
    Inherits soft delete so data can be recovered.
    """
    full_name = models.CharField(
        max_length=255, 
        db_index=True,
        help_text="Indexed for quick search"
    )
    
    # unique=True hata diya, kyunke soft-delete ke baad email dobara use ho sakti hai
    email = models.EmailField(
        help_text="Unique email address for the client"
    )
    
    profile_photo = models.ImageField(upload_to="clients/", null=True, blank=True)
    profession = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    organization = models.CharField(max_length=255, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)

    #Client Portal ke liye User account ka link
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_profile",
        help_text="The User account linked to this client for portal access."
    )
    
#  Portal Status (Invite flow ke liye)
    PORTAL_STATUS_CHOICES = (
        ("not_invited", "Not Invited"),
        ("invited", "Invited"),
        ("active", "Active"),
        ("disabled", "Disabled"),
    )
    portal_status = models.CharField(
        max_length=20, 
        choices=PORTAL_STATUS_CHOICES, 
        default="not_invited",
        help_text="Current status of the client's portal access."
    )

    class Meta:
        db_table = "clients"
        ordering = ["-created_at"]
        constraints = [
            # Sirf ACTIVE (non-deleted) clients ke darmiyan email unique 
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_client_email"
            )
        ]

    def __str__(self):
        return self.full_name