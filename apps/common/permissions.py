"""
Custom DRF permission classes.
Platform rule: only the admin logs in. Clients are data records, not users.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsVerifiedAdmin(BasePermission):
    """
    Grants access only to an authenticated user that is:
      - active
      - staff (this platform has a single admin role)
      - email-verified
    """
    message = "Admin access required. Your account must be verified."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_staff
            and getattr(user, "email_verified_at", None) is not None
        )


class IsVerifiedAdminOrReadOnly(BasePermission):
    """
    Read access for anyone (used by public endpoints),
    write access only for a verified admin.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_staff
            and getattr(user, "email_verified_at", None) is not None
        )