"""Whole-project checks: Django system check, migrations, settings, throttling config,
security headers, CORS, auth wall over every admin endpoint, robustness."""
import importlib
import os
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.common.factories import api_client, make_portfolio, make_user

ADMIN_ENDPOINTS = [
    "/api/config/settings/", "/api/config/templates/",
    "/api/clients/",
    "/api/portfolios/portfolios/", "/api/portfolios/portfolios/check-slug/", "/api/portfolios/contacts/",
    "/api/portfolios/social-links/", "/api/portfolios/process-steps/", "/api/portfolios/page-intros/",
    "/api/portfolios/educations/", "/api/portfolios/experiences/", "/api/portfolios/research-interests/",
    "/api/portfolios/expertise/", "/api/portfolios/awards/", "/api/portfolios/memberships/",
    "/api/portfolios/services/", "/api/portfolios/categories/", "/api/portfolios/projects/",
    "/api/portfolios/project-images/", "/api/portfolios/publications/", "/api/portfolios/blogs/",
    "/api/portfolios/testimonials/", "/api/portfolios/messages/",
    "/api/dashboard/stats/", "/api/dashboard/recent-activity/", "/api/auth/profile/",
]


class DjangoHealthTests(TestCase):
    def test_system_check_passes(self):
        call_command("check")

    def test_no_missing_migrations(self):
        try:
            call_command("makemigrations", check=True, dry_run=True, verbosity=0)
        except SystemExit:
            self.fail("Models changed without a migration. Run: python manage.py makemigrations")

    def test_custom_user_model_in_use(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")


class SettingsSanityTests(TestCase):
    def test_production_settings_are_hardened(self):
        prod = importlib.import_module("config.settings.prod")
        self.assertFalse(prod.DEBUG)
        self.assertTrue(prod.SESSION_COOKIE_SECURE and prod.CSRF_COOKIE_SECURE)
        self.assertTrue(prod.SECURE_SSL_REDIRECT)
        self.assertGreater(prod.SECURE_HSTS_SECONDS, 0)
        self.assertEqual(prod.X_FRAME_OPTIONS, "DENY")
        self.assertEqual(prod.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"], ("rest_framework.renderers.JSONRenderer",))

    def test_secret_key_is_not_the_placeholder(self):
        self.assertNotIn("change-me", settings.SECRET_KEY)
        self.assertGreaterEqual(len(settings.SECRET_KEY), 32)

    def test_real_env_file_is_gitignored(self):
        ignore = (Path(settings.BASE_DIR) / ".gitignore").read_text()
        self.assertIn(".env", ignore.splitlines())

    def test_password_validators_configured(self):
        names = [v["NAME"].rsplit(".", 1)[-1] for v in settings.AUTH_PASSWORD_VALIDATORS]
        for expected in ["MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator"]:
            self.assertIn(expected, names)

    def test_default_permission_is_authenticated(self):
        self.assertEqual(settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"], ("rest_framework.permissions.IsAuthenticated",))

    def test_jwt_rotation_and_blacklist_enabled(self):
        self.assertTrue(settings.SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"])
        self.assertIn("rest_framework_simplejwt.token_blacklist", settings.INSTALLED_APPS)

    def test_lockout_config(self):
        self.assertEqual(settings.LOGIN_MAX_FAILED_ATTEMPTS, 5)
        self.assertEqual(settings.LOGIN_LOCKOUT_MINUTES, 15)

    def test_all_declared_throttle_scopes_are_actually_used_RISK(self):
        """Rates exist for 'auth', 'contact_form', 'pdf_download' but a rate only applies
        if a view sets throttle_scope (with ScopedRateThrottle active)."""
        from apps.accounts.views import LoginView, ForgotPasswordView, SignupView
        from apps.public_site.views import PortfolioPDFDownloadView, PublicContactFormView
        from rest_framework.throttling import ScopedRateThrottle
        expectations = [
            (LoginView, "auth"), (ForgotPasswordView, "auth"), (SignupView, "auth"),
            (PublicContactFormView, "contact_form"), (PortfolioPDFDownloadView, "pdf_download"),
        ]
        for view, scope in expectations:
            with self.subTest(view=view.__name__):
                self.assertEqual(getattr(view, "throttle_scope", None), scope,
                                 f"{view.__name__} has no throttle_scope='{scope}', so that limit is never enforced")
        self.assertTrue(any(issubclass(t, ScopedRateThrottle) for t in PortfolioPDFDownloadView.throttle_classes),
                        "PDF view overrides throttle_classes without ScopedRateThrottle")


class AuthWallTests(TestCase):
    def test_every_admin_endpoint_rejects_anonymous(self):
        c = api_client()
        for u in ADMIN_ENDPOINTS:
            with self.subTest(url=u):
                self.assertEqual(c.get(u).status_code, 401)

    def test_every_admin_endpoint_rejects_non_admin(self):
        for u in ADMIN_ENDPOINTS:
            if u == "/api/auth/profile/":
                continue  # any authenticated user may read their own profile
            with self.subTest(url=u):
                self.assertEqual(api_client(make_user(staff=False)).get(u).status_code, 403)

    def test_every_admin_endpoint_works_for_admin(self):
        c = api_client(make_user())
        for u in ADMIN_ENDPOINTS:
            with self.subTest(url=u):
                self.assertEqual(c.get(u).status_code, 200)

    def test_unauthenticated_responses_use_envelope(self):
        d = api_client().get("/api/clients/").json()
        self.assertEqual((d["success"], d["data"]), (False, None))


class HeadersAndCorsTests(TestCase):
    def test_security_headers(self):
        r = api_client().get("/api/config/public/settings/")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r["X-Frame-Options"], "DENY")

    def test_cors_allows_configured_origin_only(self):
        origin = settings.CORS_ALLOWED_ORIGINS[0]
        ok = api_client().get("/api/config/public/settings/", HTTP_ORIGIN=origin)
        self.assertEqual(ok.get("Access-Control-Allow-Origin"), origin)
        bad = api_client().get("/api/config/public/settings/", HTTP_ORIGIN="https://evil.example")
        self.assertIsNone(bad.get("Access-Control-Allow-Origin"))

    def test_cors_preflight(self):
        origin = settings.CORS_ALLOWED_ORIGINS[0]
        r = api_client().options("/api/clients/", HTTP_ORIGIN=origin,
                                 HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
                                 HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Access-Control-Allow-Origin"], origin)
        self.assertIn("authorization", r["Access-Control-Allow-Headers"].lower())

    def test_wildcard_cors_not_enabled(self):
        self.assertFalse(getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False))


class RobustnessTests(TestCase):
    def setUp(self):
        self.c = api_client(make_user())

    def test_malformed_json_is_400(self):
        r = self.c.post("/api/clients/", "{bad json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_unsupported_media_type_is_415(self):
        r = self.c.post("/api/clients/", "<x/>", content_type="application/xml")
        self.assertEqual(r.status_code, 415)

    def test_json_array_instead_of_object_is_not_500(self):
        r = self.c.post("/api/clients/", [1, 2, 3], format="json")
        self.assertEqual(r.status_code, 400)

    def test_null_and_empty_bodies(self):
        for body in [None, {}, ""]:
            with self.subTest(body=body):
                self.assertEqual(self.c.post("/api/clients/", body, format="json").status_code, 400)

    def test_wrong_types_for_fields(self):
        for payload in [{"full_name": ["a"], "email": "a@b.co"}, {"full_name": {"x": 1}, "email": "a@b.co"},
                        {"full_name": "n", "email": 12345}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.c.post("/api/clients/", payload, format="json").status_code, 400)

    def test_huge_string_field_rejected_cleanly(self):
        self.assertEqual(self.c.post("/api/clients/", {"full_name": "x" * 1_000_000, "email": "a@b.co"}, format="json").status_code, 400)

    def test_missing_trailing_slash_redirects(self):
        self.assertEqual(api_client().get("/api/config/public/settings").status_code, 301)

    def test_unknown_route_is_404(self):
        self.assertEqual(api_client().get("/api/nope/").status_code, 404)

    def test_admin_site_login_page_loads(self):
        self.assertEqual(api_client().get("/admin/login/").status_code, 200)

    def test_options_request(self):
        self.assertEqual(self.c.options("/api/clients/").status_code, 200)
