"""One long scenario that mirrors real usage: first-time setup -> publish -> visitor -> inbox."""
import re

from django.core import mail
from django.test import TestCase

from apps.common.factories import PASSWORD, api_client


class EndToEndTests(TestCase):
    def test_full_lifecycle(self):
        anon = api_client()

        # 1. Signup + email verification
        r = anon.post("/api/auth/signup/", {"full_name": "Dr Admin", "email": "boss@example.com",
                                            "password": PASSWORD, "confirm_password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        uid, token = re.search(r"uid=([^&\s]+)&token=(\S+)", mail.outbox[0].body).groups()

        # login before verifying must fail
        self.assertEqual(anon.post("/api/auth/login/", {"email": "boss@example.com", "password": PASSWORD}, format="json").status_code, 400)
        self.assertEqual(anon.post("/api/auth/verify-email/", {"uid": uid, "token": token}, format="json").status_code, 200)

        # 2. Login with JWT
        tokens = anon.post("/api/auth/login/", {"email": "boss@example.com", "password": PASSWORD}, format="json").json()
        admin = api_client()
        admin.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(admin.get("/api/auth/profile/").json()["email"], "boss@example.com")

        # 3. Template, client, portfolio
        tpl = admin.post("/api/config/templates/", {"key": "academic-modern", "name": "Academic Modern"}, format="json").json()["data"]
        cl = admin.post("/api/clients/", {"full_name": "Dr Ayesha Khan", "email": "ayesha@example.com"}, format="json").json()["data"]
        self.assertEqual(cl["portfolio_status"], "No Portfolio")
        pf = admin.post("/api/portfolios/portfolios/", {"client": cl["id"], "template": tpl["id"], "title": "Ayesha Khan",
                                                       "full_name": "Dr Ayesha Khan", "designation": "Professor"}, format="json")
        self.assertEqual(pf.status_code, 201, pf.content)
        pid, slug = pf.json()["id"], pf.json()["slug"]
        self.assertEqual(admin.get(f"/api/clients/{cl['id']}/").json()["portfolio_status"], "draft")

        # 4. Content
        base = "/api/portfolios/"
        self.assertEqual(admin.post(f"{base}contacts/", {"portfolio": pid, "email": "ayesha@lab.edu", "form_success_message": "Thanks, Ayesha will reply!"}, format="json").status_code, 201)
        self.assertEqual(admin.post(f"{base}educations/", {"portfolio": pid, "degree": "PhD", "institution": "MIT", "field_of_study": "CS", "start_year": 2010}, format="json").status_code, 201)
        self.assertEqual(admin.post(f"{base}services/", {"portfolio": pid, "title": "Consulting", "short_description": "s", "detailed_description": "d"}, format="json").status_code, 201)
        self.assertEqual(admin.post(f"{base}projects/", {"portfolio": pid, "title": "Proj", "short_description": "s", "full_description": "f", "year": 2024}, format="json").status_code, 201)
        self.assertEqual(admin.post(f"{base}publications/", {"portfolio": pid, "title": "Paper", "authors": "A", "venue": "V", "year": 2022, "type": "journal_article"}, format="json").status_code, 201)

        # 5. Not public until published
        self.assertEqual(anon.get(f"/api/public/{slug}/").status_code, 404)
        self.assertEqual(admin.post(f"{base}portfolios/{pid}/publish/").status_code, 200)

        # 6. Visitor browses
        self.assertEqual(anon.get(f"/api/public/{slug}/").json()["data"]["portfolio"]["full_name"], "Dr Ayesha Khan")
        self.assertEqual(len(anon.get(f"/api/public/{slug}/academic/").json()["data"]["educations"]), 1)
        self.assertEqual(len(anon.get(f"/api/public/{slug}/services/").json()["data"]), 1)
        self.assertEqual(len(anon.get(f"/api/public/{slug}/projects/").json()["data"]), 1)
        self.assertEqual(len(anon.get(f"/api/public/{slug}/publications/").json()["data"]), 1)

        # 7. Visitor sends a message, admin sees it
        r = anon.post(f"/api/public/{slug}/contact/", {"full_name": "Visitor", "email": "v@example.com", "subject": "Hi", "message": "Hello"}, format="json")
        self.assertEqual(r.json()["message"], "Thanks, Ayesha will reply!")
        inbox = admin.get(f"{base}messages/").json()
        self.assertEqual(inbox["count"], 1)

        # 8. Dashboard reflects everything
        stats = admin.get("/api/dashboard/stats/").json()["data"]
        self.assertEqual((stats["total_clients"], stats["published_portfolios"]), (1, 1))
        self.assertEqual(admin.get("/api/dashboard/recent-activity/").json()["data"][0]["action"], "portfolio_published")

        # 9. Unpublish hides the site again
        admin.post(f"{base}portfolios/{pid}/unpublish/")
        self.assertEqual(anon.get(f"/api/public/{slug}/").status_code, 404)

        # 10. Soft delete client; logout; token no longer refreshes
        self.assertEqual(admin.delete(f"/api/clients/{cl['id']}/").status_code, 200)
        self.assertEqual(admin.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json").status_code, 200)
        self.assertEqual(anon.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code, 401)

    def test_deleting_client_hides_published_site_RISK(self):
        """When a client is soft-deleted, their still-published public site should go offline."""
        p = make_portfolio_published()
        c = api_client()
        self.assertEqual(c.get(f"/api/public/{p.slug}/").status_code, 200)
        p.client.soft_delete()
        self.assertEqual(c.get(f"/api/public/{p.slug}/").status_code, 404, "site of a deleted client is still public")


def make_portfolio_published():
    from apps.common.factories import make_portfolio
    return make_portfolio(status="published")
