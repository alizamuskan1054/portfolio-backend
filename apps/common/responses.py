"""
Consistent API response envelope.
"""
from rest_framework.response import Response
from rest_framework import status


def success_response(data=None, message="OK", status_code=status.HTTP_200_OK):
    return Response(
        {"success": True, "message": message, "data": data, "errors": None},
        status=status_code,
    )


def created_response(data=None, message="Created successfully."):
    return success_response(data=data, message=message, status_code=status.HTTP_201_CREATED)


def no_content_response(message="Deleted successfully."):
    return success_response(data=None, message=message, status_code=status.HTTP_200_OK)


def error_response(errors=None, message="Request failed.", status_code=status.HTTP_400_BAD_REQUEST):
    return Response(
        {"success": False, "message": message, "data": None, "errors": errors},
        status=status_code,
    )