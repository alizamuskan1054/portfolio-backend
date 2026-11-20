"""
Centralized DRF exception handler.
Handles DRF errors, Django validation errors, database protection errors,
and unhandled exceptions, returning a consistent response envelope.
"""
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError  # Import for database protection
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def _flatten_django_errors(detail):
    """Convert Django ValidationError to a plain dict/list."""
    if isinstance(detail, dict):
        return {k: [str(x) for x in v] if isinstance(v, list) else [str(v)]
                for k, v in detail.items()}
    if isinstance(detail, list):
        return [str(x) for x in detail]
    return [str(detail)]


def custom_exception_handler(exc, context):
    """
    Custom exception handler for all API responses.
    """
    # 1. Handle Database Protection Errors (e.g., deleting a template in use)
    # This must be checked before calling DRF's handler because it's a DB-level error.
    if isinstance(exc, ProtectedError):
        return Response(
            {
                "success": False,
                "message": "Cannot delete this record because it is referenced by other records.",
                "data": None,
                "errors": None,
            },
            status=status.HTTP_409_CONFLICT,
        )

    # 2. Let DRF handle its own exceptions
    response = drf_exception_handler(exc, context)

    if response is None:
        # 3. Handle Django ValidationError (raised in business logic)
        if isinstance(exc, DjangoValidationError):
            return Response(
                {
                    "success": False,
                    "message": "Validation failed.",
                    "data": None,
                    "errors": _flatten_django_errors(exc.message_dict
                                                     if hasattr(exc, "message_dict")
                                                     else exc.messages),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Handle 404 Not Found
        if isinstance(exc, Http404):
            return Response(
                {"success": False, "message": "Not found.",
                 "data": None, "errors": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 5. Unhandled exception (500 errors)
        # Log the full traceback internally, but return a generic message to the client.
        logger.exception("Unhandled server error: %s", exc)
        return Response(
            {
                "success": False,
                "message": "An unexpected error occurred. Please try again.",
                "data": None,
                "errors": None,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # 6. Normalize DRF errors into our response envelope
    detail = response.data
    message = "Request failed."
    errors = detail

    if isinstance(exc, ValidationError):
        message = "Validation failed."
    elif isinstance(exc, AuthenticationFailed):
        message = "Authentication failed."
        response.status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, NotAuthenticated):
        message = "Authentication required."
    elif isinstance(exc, PermissionDenied):
        message = "You do not have permission to perform this action."
        response.status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, NotFound):
        message = "Not found."
    elif isinstance(exc, MethodNotAllowed):
        message = "Method not allowed."
    elif isinstance(exc, Throttled):
        message = "Too many requests. Please slow down."
    elif isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        # For single-message errors (like custom auth errors)
        message = str(detail["detail"])
        errors = None

    response.data = {
        "success": False,
        "message": message,
        "data": None,
        "errors": errors if isinstance(errors, (dict, list)) else None,
    }
    return response