"""Notifications API + jin events se notifications bante hain."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.common.factories import api_client, make_client_record, make_portfolio, make_template, make_user
from apps.notifications.models import Notification

URL = "/api/notifications/"


def make_client_user(rec=None):
    rec = rec or make_client_record()
    user = get_user_model().objects.create_user(
        email=rec.email, full_name=rec.full_name, role="client",
        is_active=True, email_verified_at=timezone.now(),
    )
    rec.user = user
    rec.portal_status = "active"
    rec.save()
    return user, rec


def make_note(user, **kw):
    kw.setdefault("kind", "contact_message")
    kw.setdefault("title", "t")
    return Notification.objects.create(recipient=user, **kw)


class NotificationApiTests(TestCase):
    def setUp(self):
        self.me = make_user()
        self.other = make_user()
        self.c = api_client(self.me)

    def test_requires_login(self):
        self.assertEqual(api_client().get(URL).status_code, 401)
        self.assertEqual(api_client().get(URL + "unread-count/").status_code, 401)

    def test_list_only_mine_latest_first_with_fields(self):
        first = make_note(self.me, title="first")
        second = make_note(self.me, title="second")
        make_note(self.other, title="not mine")
        r = self.c.get(URL)
        self.assertEqual(r.status_code, 200)
        results = r.json()["results"]
        self.assertEqual([x["title"] for x in results], ["second", "first"])
        self.assertEqual(
            set(results[0]), {"id", "kind", "title", "body", "message", "is_read", "created_at", "portfolio", "portfolio_title"})
        self.assertEqual(results[0]["id"], second.pk)

    def test_unread_count(self):
        make_note(self.me)
        make_note(self.me, is_read=True)
        make_note(self.other)
        r = self.c.get(URL + "unread-count/")
        self.assertEqual(r.json()["data"]["count"], 1)

    def test_mark_read(self):
        n = make_note(self.me)
        r = self.c.post(f"{URL}{n.pk}/read/")
        self.assertEqual(r.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_cannot_read_someone_elses(self):
        n = make_note(self.other)
        self.assertEqual(self.c.post(f"{URL}{n.pk}/read/").status_code, 404)
        n.refresh_from_db()
        self.assertFalse(n.is_read)

    def test_read_all_only_touches_mine(self):
        make_note(self.me)
        make_note(self.me)
        theirs = make_note(self.other)
        r = self.c.post(URL + "read-all/")
        self.assertEqual(r.json()["data"]["updated"], 2)
        self.assertEqual(Notification.objects.filter(recipient=self.me, is_read=False).count(), 0)
        theirs.refresh_from_db()
        self.assertFalse(theirs.is_read)


class NotificationEventTests(TestCase):
    def setUp(self):
        self.admin = make_user()
        self.admin2 = make_user()
        self.user, self.rec = make_client_user()
        self.template = make_template()
        self.client_api = api_client(self.user)
        self.admin_api = api_client(self.admin)

    def _create_as_client(self, title="My Site"):
        return self.client_api.post(
            "/api/portfolios/portfolios/",
            {"template": self.template.pk, "title": title, "full_name": "Dr X", "designation": "Prof"},
            format="json",
        )

    def kinds(self, user):
        return list(Notification.objects.filter(recipient=user).values_list("kind", flat=True))

    def test_client_creates_portfolio_admins_notified_not_client(self):
        r = self._create_as_client()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.kinds(self.admin), ["portfolio_created"])
        self.assertEqual(self.kinds(self.admin2), ["portfolio_created"])
        self.assertEqual(self.kinds(self.user), [])

    def test_admin_creating_portfolio_notifies_nobody(self):
        r = self.admin_api.post(
            "/api/portfolios/portfolios/",
            {"client": self.rec.pk, "template": self.template.pk, "title": "T", "full_name": "n", "designation": "d"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Notification.objects.count(), 0)

    def test_publish_by_client_notifies_admins_only(self):
        pid = self._create_as_client().json()["id"]
        Notification.objects.all().delete()
        self.assertEqual(self.client_api.post(f"/api/portfolios/portfolios/{pid}/publish/").status_code, 200)
        self.assertEqual(self.kinds(self.admin), ["portfolio_published"])
        self.assertEqual(self.kinds(self.user), [])

    def test_publish_and_unpublish_by_admin_notify_the_client(self):
        p = make_portfolio(client=self.rec)
        self.admin_api.post(f"/api/portfolios/portfolios/{p.pk}/publish/")
        self.admin_api.post(f"/api/portfolios/portfolios/{p.pk}/unpublish/")
        self.assertEqual(sorted(self.kinds(self.user)), ["portfolio_published", "portfolio_unpublished"])
        self.assertEqual(self.kinds(self.admin), [])
        self.assertEqual(Notification.objects.filter(recipient=self.user).first().portfolio_title, p.title)

    def test_client_delete_notifies_admins(self):
        pid = self._create_as_client().json()["id"]
        Notification.objects.all().delete()
        self.assertEqual(self.client_api.delete(f"/api/portfolios/portfolios/{pid}/").status_code, 200)
        self.assertEqual(self.kinds(self.admin), ["portfolio_deleted"])

    def test_contact_form_notifies_the_portfolios_client(self):
        make_portfolio(client=self.rec, slug="dr-notify", status="published")
        r = api_client().post("/api/public/dr-notify/contact/",
                              {"full_name": "Visitor", "email": "v@example.com", "subject": "Hello", "message": "Hi"},
                              format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.kinds(self.user), ["contact_message"])
        self.assertEqual(self.kinds(self.admin), [])

    def test_accept_invite_notifies_admins(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        rec = make_client_record()
        u = get_user_model().objects.create_user(email=rec.email, full_name=rec.full_name, role="client", is_active=False)
        rec.user = u
        rec.portal_status = "invited"
        rec.save()
        r = api_client().post("/api/auth/accept-invite/", {
            "uid": urlsafe_base64_encode(force_bytes(u.pk)), "token": default_token_generator.make_token(u),
            "password": "Str0ng!Pass#2024", "confirm_password": "Str0ng!Pass#2024"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.kinds(self.admin), ["portal_activated"])
        self.assertEqual(self.kinds(u), ["portal_welcome"])  # client ko welcome
        # password save hua: login chalna chahiye
        login = api_client().post("/api/auth/login/", {"email": rec.email, "password": "Str0ng!Pass#2024"}, format="json")
        self.assertEqual(login.status_code, 200, login.content)
