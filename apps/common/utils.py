"""
Shared helpers.
"""
import os
import uuid
from django.utils.text import slugify


def generate_unique_slug(instance, value: str, *, field_name="slug", slug_field="slug", queryset=None) -> str:
    """
    Build a unique slug for `instance` within the appropriate scope.
    """
    base = slugify(value)[:200] or "item"
    slug = base
    if queryset is None and instance is None:
        raise ValueError("Provide a queryset when instance is None.")
    manager = queryset if queryset is not None else instance.__class__.objects
    counter = 2

    # Exclude self when updating an existing row.
    qs = manager
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)

    while qs.filter(**{slug_field: slug}).exists():
        slug = f"{base}-{counter}"
        counter += 1

    return slug


def image_upload_path(instance, filename: str, folder: str = "uploads") -> str:
    """
    Produce a storage path for an image (used for Cloudinary/S3).
    """
    ext = os.path.splitext(filename)[1].lower()
    safe_ext = ext if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"
    return f"{folder}/{uuid.uuid4().hex}{safe_ext}"