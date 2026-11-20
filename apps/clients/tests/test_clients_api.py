"""Client CRUD, validation, soft delete, search/ordering/pagination, permissions."""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.clients.models import Client
from apps.common.factories import (
    api_client, make_client_record, make_image, make_portfolio, make_user, rows,
)

URL = "/api/clients/"


def detail(pk):
    return f"{URL}{pk}/"


def valid(**over):
    p = {"full_name": "Dr. Ayesha Khan", "email": "ayesha@example.com"}
    p.update(over)
    return p


class ClientPermissionTests(TestCase):
    def test_anonymous_gets_401_everywhere(self):
        c = api_client()
        k = make_client_record()
        for method, url in [("get", URL), ("post", URL), ("get", detail(k.pk)),
                            ("put", detail(k.pk)), ("patch", detail(k.pk)), ("delete", detail(k.pk))]:
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(c, method)(url).status_code, 401)

    def test_non_admin_and_unverified_get_403(self):
        for user in [make_user(staff=False), make_user(verified=False)]:
            with self.subTest(user=user.email):
                self.assertEqual(api_client(user).get(URL).status_code, 403)
                self.assertEqual(api_client(user).post(URL, valid(), format="json").status_code, 403)
        self.assertEqual(Client.objects.count(), 0)


class ClientCrudTests(TestCase):
    def setUp(self):
        self.c = api_client(make_user())

    def test_create_minimal(self):
        r = self.c.post(URL, valid(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["email"], "ayesha@example.com")
        self.assertEqual(d["data"]["portfolio_status"], "No Portfolio")
        self.assertEqual(Client.objects.count(), 1)

    def test_create_full(self):
        r = self.c.post(URL, valid(profession="Researcher", phone="+92 300 1234567",
                                   organization="LUMS", location="Lahore"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["data"]["organization"], "LUMS")

    def test_required_fields(self):
        for field in ["full_name", "email"]:
            with self.subTest(field=field):
                p = valid()
                p.pop(field)
                r = self.c.post(URL, p, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertIn(field, r.json()["errors"])

    def test_invalid_email_phone_and_lengths(self):
        self.assertEqual(self.c.post(URL, valid(email="nope"), format="json").status_code, 400)
        self.assertEqual(self.c.post(URL, valid(phone="abc"), format="json").status_code, 400)
        self.assertEqual(self.c.post(URL, valid(full_name="x" * 256), format="json").status_code, 400)
        self.assertEqual(self.c.post(URL, valid(profession="x" * 101), format="json").status_code, 400)
        self.assertEqual(Client.objects.count(), 0)

    def test_email_is_lowercased_and_trimmed(self):
        r = self.c.post(URL, valid(email="  MiXed@Example.COM  "), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["data"]["email"], "mixed@example.com")

    def test_duplicate_email_exact(self):
        make_client_record(email="dup@example.com")
        r = self.c.post(URL, valid(email="dup@example.com"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json()["errors"])

    def test_retrieve_update_patch(self):
        k = make_client_record(full_name="Old")
        self.assertEqual(self.c.get(detail(k.pk)).json()["full_name"], "Old")
        r = self.c.patch(detail(k.pk), {"full_name": "New"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        k.refresh_from_db()
        self.assertEqual(k.full_name, "New")
        r = self.c.put(detail(k.pk), valid(email=k.email), format="json")
        self.assertEqual(r.status_code, 200, r.content)

    def test_put_requires_all_required_fields(self):
        k = make_client_record()
        self.assertEqual(self.c.put(detail(k.pk), {"full_name": "x"}, format="json").status_code, 400)

    def test_cannot_change_read_only_fields(self):
        k = make_client_record()
        self.c.patch(detail(k.pk), {"id": 9999, "created_at": "2000-01-01T00:00:00Z"}, format="json")
        k.refresh_from_db()
        self.assertNotEqual(k.pk, 9999)
        self.assertGreater(k.created_at.year, 2000)

    def test_not_found(self):
        self.assertEqual(self.c.get(detail(99999)).status_code, 404)
        self.assertEqual(self.c.patch(detail(99999), {}, format="json").status_code, 404)
        self.assertEqual(self.c.delete(detail(99999)).status_code, 404)

    def test_non_numeric_id(self):
        self.assertEqual(self.c.get(f"{URL}abc/").status_code, 404)

    def test_unsupported_methods(self):
        self.assertEqual(self.c.put(URL, valid(), format="json").status_code, 405)
        self.assertEqual(self.c.delete(URL).status_code, 405)

    def test_injection_and_xss_payloads_are_stored_inertly(self):
        for payload in ["Robert'); DROP TABLE clients;--", "<script>alert(1)</script>", "{{7*7}}", "\x00null"]:
            with self.subTest(payload=payload):
                r = self.c.post(URL, valid(email=f"x{abs(hash(payload))}@example.com", full_name=payload), format="json")
                self.assertIn(r.status_code, (201, 400))
        self.assertEqual(self.c.get(URL).status_code, 200)

    def test_unicode_names(self):
        r = self.c.post(URL, valid(full_name="ڈاکٹر عائشہ خان 博士", email="u@example.com"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.c.get(detail(r.json()["data"]["id"])).json()["full_name"], "ڈاکٹر عائشہ خان 博士")


class ClientPhotoTests(TestCase):
    def setUp(self):
        self.c = api_client(make_user())

    def test_valid_photo(self):
        r = self.c.post(URL, {**valid(), "profile_photo": make_image()}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(Client.objects.get().profile_photo.name.startswith("clients/"))

    def test_rejects_fake_image_wrong_type_and_oversize(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        cases = {
            "text as png": SimpleUploadedFile("a.png", b"not an image", content_type="image/png"),
            "bmp": make_image("a.bmp", "BMP"),
            "too big": make_image(pad=5 * 1024 * 1024 + 1),
        }
        for name, f in cases.items():
            with self.subTest(name):
                r = self.c.post(URL, {**valid(email=f"{abs(hash(name))}@example.com"), "profile_photo": f}, format="multipart")
                self.assertEqual(r.status_code, 400)
        self.assertEqual(Client.objects.count(), 0)


class ClientSoftDeleteTests(TestCase):
    def setUp(self):
        self.c = api_client(make_user())
        self.k = make_client_record()

    def test_delete_is_soft(self):
        r = self.c.delete(detail(self.k.pk))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Client.objects.count(), 0)
        self.assertEqual(Client.all_objects.count(), 1)

    def test_deleted_client_hidden_everywhere(self):
        self.c.delete(detail(self.k.pk))
        self.assertEqual(self.c.get(detail(self.k.pk)).status_code, 404)
        self.assertEqual(rows(self.c.get(URL)), [])
        self.assertEqual(self.c.delete(detail(self.k.pk)).status_code, 404)

    def test_delete_does_not_touch_other_clients(self):
        other = make_client_record()
        self.c.delete(detail(self.k.pk))
        self.assertEqual(self.c.get(detail(other.pk)).status_code, 200)

    def test_portfolio_status_reflects_portfolio(self):
        make_portfolio(client=self.k, status="published")
        self.assertEqual(self.c.get(detail(self.k.pk)).json()["portfolio_status"], "published")


class ClientListTests(TestCase):
    def setUp(self):
        self.c = api_client(make_user())
        for i in range(25):
            make_client_record(full_name=f"Person {i:02d}", email=f"p{i}@example.com", organization="Alpha Lab" if i % 2 else "Beta Lab")

    def test_pagination_default(self):
        d = self.c.get(URL).json()
        self.assertEqual(d["count"], 25)
        self.assertEqual(len(d["results"]), 10)
        self.assertIsNotNone(d["next"])

    def test_pagination_pages_cover_everything_once(self):
        seen = []
        for page in (1, 2, 3):
            seen += [r["id"] for r in rows(self.c.get(URL, {"page": page}))]
        self.assertEqual(len(seen), 25)
        self.assertEqual(len(set(seen)), 25)

    def test_page_size_and_cap(self):
        self.assertEqual(len(rows(self.c.get(URL, {"page_size": 5}))), 5)
        self.assertEqual(len(rows(self.c.get(URL, {"page_size": 1000}))), 25)

    def test_invalid_page(self):
        self.assertEqual(self.c.get(URL, {"page": 99}).status_code, 404)
        self.assertEqual(self.c.get(URL, {"page": "abc"}).status_code, 404)

    def test_search(self):
        self.assertEqual(self.c.get(URL, {"search": "Person 07"}).json()["count"], 1)
        self.assertEqual(self.c.get(URL, {"search": "p7@example.com"}).json()["count"], 1)
        self.assertEqual(self.c.get(URL, {"search": "alpha"}).json()["count"], 12)
        self.assertEqual(self.c.get(URL, {"search": "zzz-nothing"}).json()["count"], 0)

    def test_search_with_hostile_input(self):
        for s in ["'; DROP TABLE clients; --", "%", "_", "\\", "a" * 5000]:
            with self.subTest(s=s[:20]):
                self.assertEqual(self.c.get(URL, {"search": s}).status_code, 200)
        self.assertEqual(Client.objects.count(), 25)

    def test_ordering(self):
        names = [r["full_name"] for r in rows(self.c.get(URL, {"ordering": "full_name", "page_size": 50}))]
        self.assertEqual(names, sorted(names))
        names = [r["full_name"] for r in rows(self.c.get(URL, {"ordering": "-full_name", "page_size": 50}))]
        self.assertEqual(names, sorted(names, reverse=True))

    def test_ordering_by_unlisted_field_is_ignored_not_error(self):
        self.assertEqual(self.c.get(URL, {"ordering": "email"}).status_code, 200)

    def test_default_order_is_newest_first(self):
        ids = [r["id"] for r in rows(self.c.get(URL, {"page_size": 50}))]
        self.assertEqual(ids, sorted(ids, reverse=True))


class ClientRiskTests(TestCase):
    """RISK tests: edge cases where the current code is likely to misbehave."""

    def setUp(self):
        self.c = api_client(make_user())

    def test_duplicate_email_different_case_is_400_not_500(self):
        make_client_record(email="case@example.com")
        r = self.c.post(URL, valid(email="CASE@example.com"), format="json")
        self.assertEqual(r.status_code, 400, f"got {r.status_code}: duplicate email with other case crashes")

    def test_email_of_soft_deleted_client_can_be_reused(self):
        k = make_client_record(email="gone@example.com")
        k.soft_delete()
        r = self.c.post(URL, valid(email="gone@example.com"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Client.objects.filter(email="gone@example.com").count(), 1)
        self.assertEqual(Client.all_objects.filter(email="gone@example.com").count(), 2)

    def test_reused_email_still_blocks_a_third_active_client(self):
        k = make_client_record(email="gone@example.com")
        k.soft_delete()
        self.assertEqual(self.c.post(URL, valid(email="gone@example.com"), format="json").status_code, 201)
        self.assertEqual(self.c.post(URL, valid(email="GONE@example.com"), format="json").status_code, 400)

    def test_update_to_email_of_active_client_rejected(self):
        make_client_record(email="taken@example.com")
        k = make_client_record(email="mine@example.com")
        r = self.c.patch(detail(k.pk), {"email": "Taken@Example.com"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_update_to_email_of_deleted_client_allowed(self):
        make_client_record(email="old@example.com").soft_delete()
        k = make_client_record(email="mine@example.com")
        r = self.c.patch(detail(k.pk), {"email": "old@example.com"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

    def test_portfolio_status_ignores_soft_deleted_portfolio(self):
        k = make_client_record()
        p = make_portfolio(client=k, status="published")
        p.soft_delete()
        self.assertEqual(self.c.get(detail(k.pk)).json()["portfolio_status"], "No Portfolio")

    def test_list_does_not_run_one_query_per_client(self):
        for i in range(15):
            make_portfolio(client=make_client_record())
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.c.get(URL, {"page_size": 15}).status_code, 200)
        self.assertLessEqual(len(ctx), 8, f"N+1 queries on client list: {len(ctx)} queries")


class ClientInviteUserConflictTests(TestCase):
    """Invite flow: orphan users reuse hote hain, admin/active users block hote hain."""

    def setUp(self):
        self.c = api_client(make_user())

    def _create(self, email="momna@example.com"):
        r = self.c.post(URL, {"full_name": "Momna", "email": email}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()["data"]["id"]

    def test_invite_works_and_user_stays_inactive_until_accept(self):
        from apps.accounts.models import User
        pk = self._create()
        self.assertFalse(User.objects.filter(email="momna@example.com").exists())
        r = self.c.post(f"{URL}{pk}/invite/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(User.objects.get(email="momna@example.com").is_active)

    def test_recreate_after_delete_reuses_orphan_user(self):
        from apps.accounts.models import User
        pk = self._create()
        self.c.post(f"{URL}{pk}/invite/")
        self.c.delete(detail(pk))
        pk2 = self._create()
        r = self.c.post(f"{URL}{pk2}/invite/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(User.objects.filter(email="momna@example.com").count(), 1)

    def test_email_of_existing_admin_rejected_at_create(self):
        admin = make_user()
        r = self.c.post(URL, {"full_name": "X", "email": admin.email}, format="json")
        self.assertEqual(r.status_code, 400)
