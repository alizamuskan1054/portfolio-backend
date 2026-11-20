"""
Database models for global platform configuration.
"""
from django.db import models
from apps.common.models import BaseModel


class Template(BaseModel):
    """Frontend templates (React layouts) available for portfolios."""
    key = models.CharField(max_length=50, unique=True, help_text="Unique key for React, e.g., 'academic-modern'")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    preview_image = models.ImageField(upload_to="templates/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "templates"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.key})"


class PlatformSettings(BaseModel):
    """Global settings for the platform. Exactly one row should exist."""
    platform_name = models.CharField(max_length=150, default="Academic Researcher Portfolio")
    logo = models.ImageField(upload_to="platform/", null=True, blank=True)
    admin_contact_email = models.EmailField()
    default_template = models.ForeignKey(Template, on_delete=models.SET_NULL, null=True, blank=True)
    default_theme = models.CharField(max_length=50, default="light")
    default_typography = models.CharField(max_length=50, default="inter")
    notification_email = models.EmailField(help_text="Fallback for contact form emails", null=True, blank=True)
    email_notifications_enabled = models.BooleanField(default=True)
    default_success_message = models.TextField(default="Thank you for reaching out. I will get back to you soon.")

    class Meta:
        db_table = "platform_settings"
        verbose_name_plural = "Platform Settings"

    def __str__(self):
        return self.platform_name

    def save(self, *args, **kwargs):
        if not self.pk and PlatformSettings.objects.exists():
            raise ValueError("Only one instance of PlatformSettings is allowed.")
        return super().save(*args, **kwargs)