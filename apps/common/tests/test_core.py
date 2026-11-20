"""Unit tests: soft-delete mixins, slug/upload helpers, response envelope,
pagination, permission classes and the central exception handler."""
from types import SimpleNamespace

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import (
    MethodNotAllowed, NotAuthenticated, PermissionDenied, Throttled, ValidationError,
)

from apps.common.exceptions import custom_exception_handler
from apps.common.pagination import StandardResultsPagination
from apps.common.permissions import IsVerifiedAdmin, IsVerifiedAdminOrReadOnly
from apps.common.responses import created_response, error_response, no_content_response, success_response
from apps.common.utils import generate_unique_slug, image_upload_path
from apps.clients.models import Client
from apps.common.factories import make_client_record, make_portfolio
from apps.portfolios.models import Category


class SoftDeleteTests(TestCase):
    def test_soft_delete_hides_from_default_manager_but_not_all_objects(self):
        c = make_client_record()
        c.soft_delete()
        self.assertEqual(Client.objects.count(), 0)
        self.assertEqual(Client.all_objects.count(), 1)
        self.assertTrue(Client.all_objects.get(pk=c.pk).is_deleted)

    def test_restore(self):
        c = make_client_record()
        c.soft_delete()
        c.restore()
        self.assertEqual(Client.objects.count(), 1)
        self.assertFalse(c.is_deleted)

    def test_queryset_bulk_soft_delete_and_dead(self):
        make_client_record()
        make_client_record()
        Client.objects.all().soft_delete()
        self.assertEqual(Client.objects.count(), 0)
        self.assertEqual(Client.all_objects.all().dead().count(), 2)
        self.assertEqual(Client.all_objects.all().alive().count(), 0)

    def test_soft_delete_twice_is_harmless(self):
        c = make_client_record()
        c.soft_delete()
        c.soft_delete()
        self.assertEqual(Client.all_objects.count(), 1)


class SlugHelperTests(TestCase):
    def setUp(self):
        self.portfolio = make_portfolio()
        self.qs = Category.objects.filter(portfolio=self.portfolio, kind="blog")

    def _cat(self, slug):
        return Category.objects.create(portfolio=self.portfolio, kind="blog", name=slug, slug=slug)

    def test_basic_slugify(self):
        self.assertEqual(generate_unique_slug(Category(), "Hello World!", queryset=self.qs), "hello-world")

    def test_collision_gets_counter(self):
        self._cat("ai")
        self.assertEqual(generate_unique_slug(Category(), "ai", queryset=self.qs), "ai-2")
        self._cat("ai-2")
        self.assertEqual(generate_unique_slug(Category(), "ai", queryset=self.qs), "ai-3")

    def test_empty_value_falls_back(self):
        self.assertEqual(generate_unique_slug(Category(), "", queryset=self.qs), "item")
        self.assertEqual(generate_unique_slug(Category(), "!!!", queryset=self.qs), "item")

    def test_long_values_truncated(self):
        self.assertLessEqual(len(generate_unique_slug(Category(), "a" * 500, queryset=self.qs)), 200)

    def test_updating_existing_row_keeps_its_own_slug(self):
        cat = self._cat("ai")
        self.assertEqual(generate_unique_slug(cat, "ai", queryset=self.qs), "ai")

    def test_instance_none_is_supported(self):
        """The serializers call this with self.instance == None on create."""
        self.assertEqual(generate_unique_slug(None, "New Post", queryset=self.qs), "new-post")


class UploadPathTests(SimpleTestCase):
    def test_extension_whitelist(self):
        self.assertTrue(image_upload_path(None, "a.PNG").endswith(".png"))
        self.assertTrue(image_upload_path(None, "a.jpeg").endswith(".jpeg"))
        self.assertTrue(image_upload_path(None, "evil.php").endswith(".jpg"))
        self.assertTrue(image_upload_path(None, "noext").endswith(".jpg"))

    def test_folder_and_uniqueness(self):
        a = image_upload_path(None, "a.png", folder="clients")
        b = image_upload_path(None, "a.png", folder="clients")
        self.assertTrue(a.startswith("clients/"))
        self.assertNotEqual(a, b)

    def test_original_filename_not_kept(self):
        self.assertNotIn("secret", image_upload_path(None, "../../secret.png"))


class ResponseEnvelopeTests(SimpleTestCase):
    def test_success(self):
        r = success_response(data={"a": 1}, message="yo")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {"success": True, "message": "yo", "data": {"a": 1}, "errors": None})

    def test_created(self):
        self.assertEqual(created_response().status_code, 201)

    def test_no_content_returns_200_with_message(self):
        r = no_content_response()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["success"])

    def test_error(self):
        r = error_response(errors={"f": ["bad"]}, message="nope")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.data["success"])
        self.assertEqual(r.data["errors"], {"f": ["bad"]})
        self.assertIsNone(r.data["data"])

    def test_error_custom_status(self):
        self.assertEqual(error_response(status_code=418).status_code, 418)


class PaginationConfigTests(SimpleTestCase):
    def test_limits(self):
        p = StandardResultsPagination
        self.assertEqual((p.page_size, p.max_page_size), (10, 50))
        self.assertEqual(p.page_size_query_param, "page_size")


def _req(method="GET", **user_kw):
    defaults = dict(is_authenticated=True, is_active=True, is_staff=True, email_verified_at="x")
    defaults.update(user_kw)
    return SimpleNamespace(method=method, user=SimpleNamespace(**defaults))


class PermissionTests(SimpleTestCase):
    def test_verified_admin_matrix(self):
        perm = IsVerifiedAdmin()
        self.assertTrue(perm.has_permission(_req(), None))
        for override in [
            {"is_authenticated": False}, {"is_active": False},
            {"is_staff": False}, {"email_verified_at": None},
        ]:
            with self.subTest(override=override):
                self.assertFalse(perm.has_permission(_req(**override), None))

    def test_no_user_denied(self):
        self.assertFalse(IsVerifiedAdmin().has_permission(SimpleNamespace(user=None), None))

    def test_read_only_variant(self):
        perm = IsVerifiedAdminOrReadOnly()
        anon = _req(is_authenticated=False)
        for m in ["GET", "HEAD", "OPTIONS"]:
            anon.method = m
            self.assertTrue(perm.has_permission(anon, None), m)
        for m in ["POST", "PUT", "PATCH", "DELETE"]:
            self.assertFalse(perm.has_permission(_req(m, is_authenticated=False), None), m)
            self.assertFalse(perm.has_permission(_req(m, email_verified_at=None), None), m)
            self.assertTrue(perm.has_permission(_req(m), None), m)


class ExceptionHandlerTests(SimpleTestCase):
    def assertEnvelope(self, resp, status, message=None):
        self.assertEqual(resp.status_code, status)
        self.assertEqual(set(resp.data), {"success", "message", "data", "errors"})
        self.assertFalse(resp.data["success"])
        if message:
            self.assertEqual(resp.data["message"], message)

    def test_drf_validation_error(self):
        r = custom_exception_handler(ValidationError({"f": ["bad"]}), {})
        self.assertEnvelope(r, 400, "Validation failed.")
        self.assertIn("f", r.data["errors"])

    def test_django_validation_error_dict(self):
        r = custom_exception_handler(DjangoValidationError({"f": "bad"}), {})
        self.assertEnvelope(r, 400, "Validation failed.")
        self.assertEqual(r.data["errors"], {"f": ["bad"]})

    def test_django_validation_error_message(self):
        r = custom_exception_handler(DjangoValidationError("bad"), {})
        self.assertEnvelope(r, 400)
        self.assertEqual(r.data["errors"], ["bad"])

    def test_http404(self):
        self.assertEnvelope(custom_exception_handler(Http404(), {}), 404, "Not found.")

    def test_not_authenticated(self):
        self.assertEnvelope(custom_exception_handler(NotAuthenticated(), {}), 401, "Authentication required.")

    def test_permission_denied(self):
        self.assertEnvelope(custom_exception_handler(PermissionDenied(), {}), 403)

    def test_method_not_allowed(self):
        self.assertEnvelope(custom_exception_handler(MethodNotAllowed("POST"), {}), 405, "Method not allowed.")

    def test_throttled(self):
        self.assertEnvelope(custom_exception_handler(Throttled(wait=3), {}), 429)

    def test_unhandled_exception_is_500_and_hides_details(self):
        with self.assertLogs("apps.common.exceptions", level="ERROR"):
            r = custom_exception_handler(RuntimeError("secret internals"), {})
        self.assertEnvelope(r, 500)
        self.assertNotIn("secret internals", str(r.data))
