"""
Custom User model for the platform.
Only the admin logs in. The account is created inactive until the
email is verified. We also track failed login attempts for lockouts.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        # Superuser ko manually verify maan lete hain taake CLI se create karte hi login ho sake
        extra_fields.setdefault("email_verified_at", timezone.now())

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, full_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, db_index=True)
    profile_photo = models.ImageField(upload_to="profiles/", null=True, blank=True)
    
    is_active = models.BooleanField(default=False) # Inactive until email verified
    is_staff = models.BooleanField(default=False)
    
    email_verified_at = models.DateTimeField(null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True) # Django handles this, but explicitly defining
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("client", "Client"),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="admin")
    # Lockout fields
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.email

    def is_locked(self):
        """Returns True if the account is currently locked out."""
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False