"""Small helpers shared by every test module (not a test file itself)."""
import io
import itertools

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

PASSWORD = "Str0ng!Pass#2024"
_counter = itertools.count(1)


def n():
    return next(_counter)


def make_user(email=None, password=PASSWORD, *, active=True, staff=True,
              verified=True, full_name="Test Admin"):
    User = get_user_model()
    return User.objects.create_user(
        email=email or f"admin{n()}@example.com",
        full_name=full_name,
        password=password,
        is_active=active,
        is_staff=staff,
        email_verified_at=timezone.now() if verified else None,
    )


def api_client(user=None):
    """APIClient; when a user is given it is force-authenticated (no JWT involved)."""
    c = APIClient()
    if user is not None:
        c.force_authenticate(user)
    return c


def jwt_client(user):
    """APIClient authenticated with a real JWT access token."""
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return c


def make_template(**kw):
    from apps.site_config.models import Template
    i = n()
    kw.setdefault("key", f"template-{i}")
    kw.setdefault("name", f"Template {i}")
    return Template.objects.create(**kw)


def make_client_record(**kw):
    from apps.clients.models import Client
    i = n()
    kw.setdefault("full_name", f"Dr. Client {i}")
    kw.setdefault("email", f"client{i}@example.com")
    return Client.objects.create(**kw)


def make_portfolio(client=None, template=None, **kw):
    from apps.portfolios.models import Portfolio
    i = n()
    kw.setdefault("title", f"Portfolio {i}")
    kw.setdefault("slug", f"portfolio-{i}")
    kw.setdefault("full_name", "Dr. Test Person")
    kw.setdefault("designation", "Professor")
    return Portfolio.objects.create(
        client=client or make_client_record(),
        template=template or make_template(),
        **kw,
    )


def make_image(name="photo.png", fmt="PNG", size=(10, 10), pad=0):
    """A real, decodable image upload. `pad` appends junk bytes to inflate the size."""
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, format=fmt)
    data = buf.getvalue() + (b"\0" * pad)
    return SimpleUploadedFile(name, data, content_type=f"image/{fmt.lower()}")


def make_pdf(name="cv.pdf", size=1024, content_type="application/pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n" + b"0" * size, content_type=content_type)


def body(resp):
    return resp.json()


def rows(resp):
    """Rows of a paginated DRF list response."""
    return resp.json()["results"]
