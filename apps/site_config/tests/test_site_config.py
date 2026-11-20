"""Platform settings + templates."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.common.factories import api_client, make_image, make_portfolio, make_template, make_user, rows
from apps.site_config.models import PlatformSettings, Template

SETTINGS = "/api/config/settings/"
PUBLIC = "/api/config/public/settings/"
TEMPLATES = "/api/config/templates/"


class ModelTests(TestCase):
    def test_only_one_platform_settings_instance(self):
        PlatformSettings.objects.create(admin_contact_email="a@example.com")
        with self.assertRaises(ValueError):
            PlatformSettings.objects.create(admin_contact_email="b@example.com")

    def test_template_key_unique(self):
        make_template(key="modern")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_template(key="modern")

    def test_defaults_and_str(self):
        t = make_template(key="k", name="N")
        self.assertTrue(t.is_active)
        self.assertEqual(str(t), "N (k)")
        self.assertEqual(PlatformSettings.objects.create(admin_contact_email="a@example.com").default_theme, "light")


class PlatformSettingsApiTests(TestCase):
    def setUp(self):
        self.c = api_client(make_user())

    def test_get_creates_singleton_with_defaults(self):
        r = self.c.get(SETTINGS)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(PlatformSettings.objects.count(), 1)
        self.assertEqual(r.json()["data"]["admin_contact_email"], "admin@example.com")
        self.c.get(SETTINGS)
        self.assertEqual(PlatformSettings.objects.count(), 1)

    def test_patch_updates(self):
        r = self.c.patch(SETTINGS, {"platform_name": "My Platform", "default_theme": "dark"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.c.get(SETTINGS).json()["data"]["platform_name"], "My Platform")

    def test_put_requires_admin_contact_email(self):
        self.assertEqual(self.c.put(SETTINGS, {"platform_name": "x"}, format="json").status_code, 400)

    def test_invalid_email_rejected(self):
        self.assertEqual(self.c.patch(SETTINGS, {"admin_contact_email": "nope"}, format="json").status_code, 400)

    def test_notification_email_falls_back_to_admin_email(self):
        r = self.c.put(SETTINGS, {"admin_contact_email": "boss@example.com",
                                  "email_notifications_enabled": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["data"]["notification_email"], "boss@example.com")

    def test_logo_validation(self):
        self.assertEqual(self.c.patch(SETTINGS, {"logo": make_image()}, format="multipart").status_code, 200)
        self.assertEqual(self.c.patch(SETTINGS, {"logo": make_image("a.bmp", "BMP")}, format="multipart").status_code, 400)

    def test_default_template_must_exist(self):
        self.assertEqual(self.c.patch(SETTINGS, {"default_template": 9999}, format="json").status_code, 400)
        t = make_template()
        self.assertEqual(self.c.patch(SETTINGS, {"default_template": t.pk}, format="json").status_code, 200)

    def test_requires_admin(self):
        self.assertEqual(api_client().get(SETTINGS).status_code, 401)
        self.assertEqual(api_client().patch(SETTINGS, {}, format="json").status_code, 401)
        self.assertEqual(api_client(make_user(staff=False)).get(SETTINGS).status_code, 403)


class PublicSettingsTests(TestCase):
    def test_public_no_auth_needed(self):
        r = api_client().get(PUBLIC)
        self.assertEqual(r.status_code, 200, r.content)

    def test_public_exposes_only_safe_fields(self):
        PlatformSettings.objects.create(id=1, admin_contact_email="secret-admin@example.com",
                                        notification_email="secret-notify@example.com")
        d = api_client().get(PUBLIC).json()["data"]
        self.assertEqual(set(d), {"platform_name", "logo", "default_theme", "default_typography"})
        self.assertNotIn("secret", str(d))

    def test_public_ignores_bad_auth_header(self):
        c = api_client()
        c.credentials(HTTP_AUTHORIZATION="Bearer garbage")
        self.assertEqual(c.get(PUBLIC).status_code, 200)

    def test_public_is_read_only(self):
        self.assertEqual(api_client().post(PUBLIC, {}, format="json").status_code, 405)
        self.assertEqual(api_client().patch(PUBLIC, {}, format="json").status_code, 405)


class TemplateApiTests(TestCase):
    def setUp(self):
        self.c = api_client(make_user())

    def test_crud(self):
        r = self.c.post(TEMPLATES, {"key": "Academic-Modern", "name": "Academic Modern"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        tid = r.json()["data"]["id"]
        self.assertEqual(r.json()["data"]["key"], "academic-modern")  # lowercased
        self.assertEqual(self.c.get(f"{TEMPLATES}{tid}/").status_code, 200)
        self.assertEqual(self.c.patch(f"{TEMPLATES}{tid}/", {"name": "Renamed"}, format="json").status_code, 200)
        self.assertEqual(self.c.delete(f"{TEMPLATES}{tid}/").status_code, 204)
        self.assertEqual(self.c.get(f"{TEMPLATES}{tid}/").status_code, 404)

    def test_required_fields_and_unique_key(self):
        self.assertEqual(self.c.post(TEMPLATES, {}, format="json").status_code, 400)
        make_template(key="dup")
        self.assertEqual(self.c.post(TEMPLATES, {"key": "dup", "name": "x"}, format="json").status_code, 400)

    def test_key_max_length(self):
        self.assertEqual(self.c.post(TEMPLATES, {"key": "k" * 51, "name": "x"}, format="json").status_code, 400)

    def test_list_is_paginated_and_sorted_by_name(self):
        for name in ["Zeta", "Alpha", "Mid"]:
            make_template(name=name)
        names = [t["name"] for t in rows(self.c.get(TEMPLATES))]
        self.assertEqual(names, sorted(names))

    def test_preview_image_validation(self):
        r = self.c.post(TEMPLATES, {"key": "img", "name": "Img", "preview_image": make_image("a.bmp", "BMP")}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_requires_admin(self):
        self.assertEqual(api_client().get(TEMPLATES).status_code, 401)
        self.assertEqual(api_client(make_user(verified=False)).get(TEMPLATES).status_code, 403)

    def test_delete_template_in_use_is_not_500(self):
        """RISK: Portfolio.template is PROTECT; deleting a used template must be a clean 4xx."""
        t = make_template()
        make_portfolio(template=t)
        r = self.c.delete(f"{TEMPLATES}{t.pk}/")
        self.assertIn(r.status_code, (400, 409), f"got {r.status_code}")
        self.assertTrue(Template.objects.filter(pk=t.pk).exists())
