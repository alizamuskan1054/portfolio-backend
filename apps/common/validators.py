"""
Reusable validators for the platform.
Handles phone numbers, images, CV files (PDF), reserved slugs, and date ranges.
"""
import re
from django.core.exceptions import ValidationError

# Reserved slugs are blocked at validation (spec: security rules).
RESERVED_SLUGS = {"admin", "api", "login", "static", "media", "portal"}

# Permissive international phone pattern
PHONE_REGEX = re.compile(r"^\+?[0-9\s\-().]{7,20}$")

# Allowed image MIME types for uploads
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Allowed CV file types and size
ALLOWED_CV_CONTENT_TYPES = {"application/pdf"}
MAX_CV_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_phone_number(value: str) -> None:
    """Validate phone number format."""
    if value and not PHONE_REGEX.match(value):
        raise ValidationError("Enter a valid phone number.")


def validate_reserved_slug(value: str) -> None:
    """Block slugs that collide with platform routes."""
    if value and value.lower() in RESERVED_SLUGS:
        raise ValidationError(f"'{value}' is a reserved slug.")


def validate_image_file(file) -> None:
    """Validate file type and size for any image upload."""
    if file is None:
        return
    content_type = getattr(file, "content_type", None)
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError("Unsupported image format. Allowed: JPEG, PNG, WEBP, GIF.")
    if file.size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError("Image size must not exceed 5 MB.")


def validate_cv_file(file) -> None:
    """
    Validate CV file type (only PDF) and size.
    CVs are documents, not images, so they have separate rules.
    """
    if file is None:
        return
    content_type = getattr(file, "content_type", None)
    if content_type != "application/pdf":
        raise ValidationError("Only PDF format is allowed for CV.")
    if file.size > MAX_CV_SIZE_BYTES:
        raise ValidationError("CV size must not exceed 10 MB.")


def validate_date_range(start_date, end_date, *, allow_equal=True, label="end date"):
    """Generic date-range validation."""
    if start_date is None or end_date is None:
        return
    if end_date < start_date or (not allow_equal and end_date == start_date):
        raise ValidationError({label: "End date must be after start date."})