"""
Test settings. Run the suite with:

    python manage.py test --settings=config.settings.test

Everything is isolated from real services: in-memory SQLite (never your Neon DB),
local file storage in a temp folder (never Cloudinary), in-memory email, fast hashers.
"""
import os
import tempfile

# Force-isolate BEFORE base.py reads the environment (os.environ wins over .env).
os.environ["SECRET_KEY"] = "test-secret-key-only-for-tests-0123456789-abcdefghijklmnop"
os.environ["DATABASE_URL"] = "sqlite://:memory:"
os.environ["FRONTEND_URL"] = "http://frontend.test"

from .base import *  # noqa: E402,F401,F403

DEBUG = False

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@test.local"

# Never talk to Cloudinary from tests.
CLOUDINARY_STORAGE = {"CLOUD_NAME": "test", "API_KEY": "test", "API_SECRET": "test"}
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
MEDIA_ROOT = tempfile.mkdtemp(prefix="portfolio_test_media_")

# Rate limits would make unrelated tests flaky; throttle config is asserted separately.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100000/hour",
        "user": "100000/hour",
        "contact_form": "100000/hour",
        "auth": "100000/hour",
        "pdf_download": "100000/hour",
    },
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}