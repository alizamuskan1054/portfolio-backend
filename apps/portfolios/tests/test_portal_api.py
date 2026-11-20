"""Client-token (portal) rules: create, limit, status, slug, publish, messages."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.common.factories import api_client, make_client_record, make_portfolio, make_template, make_user
from apps.portfolios.models import ContactMessage, Portfolio

URL = "/api/portfolios/portfolios/"


def client_user():
    rec = make_client_record()
    user = get_user_model().objects.create_user(
        email=rec.email, full_name=rec.full_name, role="client", is_active=True, email_verified_at=timezone.now())
    rec.user = user
    rec.save()
    return user, rec


class PortalPortfolioTests(TestCase):
    def setUp(self):
        self.user, self.rec = client_user()
        self.c = api_client(self.user)
        self.t = make_template()

    def payload(self, **over):
        p = {"template": self.t.pk, "title": "My Site", "full_name": "Dr X", "designation": "Prof"}
        p.update(over)
        return p

    def test_client_field_not_required_and_status_draft(self):
        r = self.c.post(URL, self.payload(status="published"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["client"], self.rec.pk)
        self.assertEqual(r.json()["status"], "draft")

    def test_own_client_id_accepted_other_rejected(self):
        self.assertEqual(self.c.post(URL, self.payload(client=self.rec.pk), format="json").status_code, 201)
        other = make_client_record()
        r = self.c.post(URL, self.payload(title="Another", client=other.pk), format="json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Portfolio.objects.filter(client=other).exists())

    def test_limit_is_five_and_soft_deleted_do_not_count(self):
        for i in range(5):
            self.assertEqual(self.c.post(URL, self.payload(title=f"Site {i}"), format="json").status_code, 201)
        r = self.c.post(URL, self.payload(title="Site 6"), format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["message"], "You can create up to 5 portfolios.")
        Portfolio.objects.filter(client=self.rec).first().soft_delete()
        self.assertEqual(self.c.post(URL, self.payload(title="Site 6"), format="json").status_code, 201)

    def test_status_cannot_be_patched(self):
        p = make_portfolio(client=self.rec)
        for who in (self.c, api_client(make_user())):
            who.patch(f"{URL}{p.pk}/", {"status": "published"}, format="json")
            p.refresh_from_db()
            self.assertEqual(p.status, "draft")

    def test_other_clients_portfolio_is_404(self):
        other = make_portfolio()
        self.assertEqual(self.c.post(f"{URL}{other.pk}/publish/").status_code, 404)
        self.assertEqual(self.c.post(f"{URL}{other.pk}/unpublish/").status_code, 404)
        self.assertEqual(self.c.delete(f"{URL}{other.pk}/").status_code, 404)

    def test_publish_unpublish_delete_own(self):
        p = make_portfolio(client=self.rec)
        self.assertEqual(self.c.post(f"{URL}{p.pk}/publish/").status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "published")
        self.assertEqual(self.c.post(f"{URL}{p.pk}/unpublish/").status_code, 200)
        self.assertEqual(self.c.delete(f"{URL}{p.pk}/").status_code, 200)
        self.assertTrue(Portfolio.all_objects.get(pk=p.pk).deleted_at)

    def test_publish_without_title_is_400(self):
        p = make_portfolio(client=self.rec, title="  ")
        r = self.c.post(f"{URL}{p.pk}/publish/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("title", r.json()["errors"])

    def test_check_slug_for_client_case_insensitive_and_reserved(self):
        make_portfolio(slug="taken-slug")
        get = lambda s: self.c.get(URL + "check-slug/", {"slug": s}).json()["data"]["available"]
        self.assertFalse(get("TAKEN-slug"))
        self.assertFalse(get("portal"))
        self.assertTrue(get("fresh-slug"))

    def test_slug_patch_is_case_insensitively_unique(self):
        make_portfolio(slug="taken-slug")
        p = make_portfolio(client=self.rec)
        r = self.c.patch(f"{URL}{p.pk}/", {"slug": "Taken-Slug"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_options_and_templates_for_client(self):
        self.assertEqual(self.c.options(URL).status_code, 200)
        self.assertEqual(self.c.options("/api/portfolios/educations/").status_code, 200)
        self.assertEqual(self.c.get("/api/config/templates/").status_code, 200)


class PortalMessagesTests(TestCase):
    def setUp(self):
        self.user, self.rec = client_user()
        self.c = api_client(self.user)
        self.p = make_portfolio(client=self.rec)
        self.mine = ContactMessage.objects.create(
            portfolio=self.p, full_name="Vis", email="v@example.com", subject="s", message="m")
        ContactMessage.objects.create(
            portfolio=make_portfolio(), full_name="x", email="x@example.com", subject="s", message="m")

    def test_list_scoped_with_fields_and_portfolio_filter(self):
        r = self.c.get("/api/portfolios/messages/")
        rows = r.json()["results"]
        self.assertEqual(len(rows), 1)
        for f in ("id", "name", "email", "subject", "message", "is_read", "created_at", "portfolio"):
            self.assertIn(f, rows[0])
        self.assertEqual(rows[0]["name"], "Vis")
        r = self.c.get("/api/portfolios/messages/", {"portfolio": self.p.pk})
        self.assertEqual(len(r.json()["results"]), 1)

    def test_patch_changes_only_is_read(self):
        url = f"/api/portfolios/messages/{self.mine.pk}/"
        r = self.c.patch(url, {"is_read": True, "message": "tampered"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.mine.refresh_from_db()
        self.assertTrue(self.mine.is_read)
        self.assertEqual(self.mine.message, "m")
        self.c.patch(url, {"is_read": False}, format="json")
        self.mine.refresh_from_db()
        self.assertFalse(self.mine.is_read)
