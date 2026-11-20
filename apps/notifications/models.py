"""
In-app notifications. Har notification ek recipient user ki hoti hai,
is liye `is_read` har user ka alag rehta hai.
"""
from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Notification(BaseModel):
    CONTACT_MESSAGE = "contact_message"
    PORTFOLIO_CREATED = "portfolio_created"
    PORTFOLIO_DELETED = "portfolio_deleted"
    PORTFOLIO_PUBLISHED = "portfolio_published"
    PORTFOLIO_UNPUBLISHED = "portfolio_unpublished"
    PORTAL_ACTIVATED = "portal_activated"
    PORTAL_WELCOME = "portal_welcome"

    KIND_CHOICES = (
        (CONTACT_MESSAGE, "Contact message"),
        (PORTFOLIO_CREATED, "Portfolio created"),
        (PORTFOLIO_DELETED, "Portfolio deleted"),
        (PORTFOLIO_PUBLISHED, "Portfolio published"),
        (PORTFOLIO_UNPUBLISHED, "Portfolio unpublished"),
        (PORTAL_ACTIVATED, "Portal activated"),
        (PORTAL_WELCOME, "Portal welcome"),
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=40, choices=KIND_CHOICES)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    portfolio = models.ForeignKey(
        "portfolios.Portfolio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # Snapshot: portfolio delete/rename ke baad bhi notification sahi dikhe
    portfolio_title = models.CharField(max_length=255, blank=True, default="")
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["recipient", "is_read"], name="notif_recipient_read_idx"),
            models.Index(fields=["recipient", "-created_at"], name="notif_recipient_created_idx"),
        ]

    def __str__(self):
        return f"{self.kind} -> {self.recipient_id}"
