"""Local development settings."""
from .base import *  # noqa: F401,F403

DEBUG = True

# Browsable API is handy while building; it is not enabled in production.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}
