"""Portfolio CRUD, publish/unpublish, slug rules, filters and core child tables."""
from django.test import TestCase

from apps.common.factories import (
    api_client, make_client_record, make_image, make_pdf, make_portfolio, make_template, make_user, rows,
)
from apps.portfolios.models import ActivityLog, PageIntro, Portfolio, ProcessStep

URL = "/api/portfolios/portfolios/"
CHECK = f"{URL}check-slug/"


def detail(pk):
    return f"{URL}{pk}/"


class Base(TestCase):
    def setUp(self):
        self.admin = make_user()
        self.c = api_client(self.admin)
        self.client_rec = make_client_record()
        self.template = make_template()

    def payload(self, **over):
        p = {"client": self.client_rec.pk, "template": self.template.pk, "title": "Dr Ahmad Research",
             "full_name": "Dr Ahmad", "designation": "Professor"}
        p.update(over)
        return p


class PortfolioPermissionTests(Base):
    def test_anonymous_401_and_non_admin_403(self):
        p = make_portfolio()
        for method, url in [("get", URL), ("post", URL), ("get", detail(p.pk)), ("delete", detail(p.pk)),
                            ("post", f"{detail(p.pk)}publish/"), ("post", f"{detail(p.pk)}unpublish/"), ("get", CHECK)]:
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(api_client(), method)(url).status_code, 401)
                self.assertEqual(getattr(api_client(make_user(staff=False)), method)(url).status_code, 403)


class PortfolioCreateTests(Base):
    def test_create_success_generates_slug(self):
        r = self.c.post(URL, self.payload(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["slug"], "dr-ahmad-research")
        self.assertEqual(r.json()["status"], "draft")

    def test_slug_in_body_is_ignored(self):
        r = self.c.post(URL, self.payload(slug="hacked-slug"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["slug"], "dr-ahmad-research")

    def test_required_fields(self):
        for field in ["client", "template", "title", "full_name", "designation"]:
            with self.subTest(field=field):
                p = self.payload()
                p.pop(field)
                r = self.c.post(URL, p, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertIn(field, r.json()["errors"])

    def test_unknown_client_or_template(self):
        self.assertEqual(self.c.post(URL, self.payload(client=99999), format="json").status_code, 400)
        self.assertEqual(self.c.post(URL, self.payload(template=99999), format="json").status_code, 400)

    def test_admin_can_create_second_portfolio_for_same_client(self):
        self.assertEqual(self.c.post(URL, self.payload(), format="json").status_code, 201)
        r = self.c.post(URL, self.payload(title="Another"), format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def test_invalid_status_and_negative_numbers(self):
        self.assertEqual(self.c.post(URL, self.payload(status="weird"), format="json").status_code, 400)
        self.assertEqual(self.c.post(URL, self.payload(citations=-1), format="json").status_code, 400)
        self.assertEqual(self.c.post(URL, self.payload(h_index="abc"), format="json").status_code, 400)

    def test_file_uploads(self):
        r = self.c.post(URL, {**self.payload(), "profile_photo": make_image(), "cv_file": make_pdf()}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)

    def test_bad_cv_and_images_rejected(self):
        for field, f in [("cv_file", make_pdf("cv.docx", content_type="application/msword")),
                         ("hero_image", make_image("a.bmp", "BMP")),
                         ("logo", make_image(pad=5 * 1024 * 1024 + 1))]:
            with self.subTest(field=field):
                self.assertEqual(self.c.post(URL, {**self.payload(), field: f}, format="multipart").status_code, 400)
        self.assertEqual(Portfolio.objects.count(), 0)

    def test_oversized_cv_rejected(self):
        big = make_pdf(size=10 * 1024 * 1024 + 1)
        self.assertEqual(self.c.post(URL, {**self.payload(), "cv_file": big}, format="multipart").status_code, 400)


class PortfolioRiskTests(Base):
    """RISK: slug generation and publish-timestamp edge cases."""

    def test_two_portfolios_with_same_title_do_not_crash(self):
        self.assertEqual(self.c.post(URL, self.payload(), format="json").status_code, 201)
        other = make_client_record()
        r = self.c.post(URL, self.payload(client=other.pk), format="json")
        self.assertEqual(r.status_code, 201, f"got {r.status_code}: duplicate title -> slug collision")
        slugs = set(Portfolio.objects.values_list("slug", flat=True))
        self.assertEqual(len(slugs), 2)

    def test_reserved_slug_via_title_is_blocked(self):
        for title in ["admin", "API", "Login", "static", "media"]:
            with self.subTest(title=title):
                r = self.c.post(URL, self.payload(title=title, client=make_client_record().pk), format="json")
                self.assertNotEqual(r.json().get("slug"), title.lower(), "reserved slug accepted")

    def test_non_latin_title_still_gets_a_slug(self):
        r = self.c.post(URL, self.payload(title="ڈاکٹر احمد"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()["slug"], "empty slug generated from non-latin title")

    def test_create_as_published_sets_published_at(self):
        r = self.c.post(URL, self.payload(status="published"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNotNone(r.json()["published_at"])

    def test_new_portfolio_after_soft_deleting_old_one_for_same_client(self):
        old = make_portfolio(client=self.client_rec, template=self.template)
        old.soft_delete()
        r = self.c.post(URL, self.payload(title="Fresh Start"), format="json")
        self.assertIn(r.status_code, (201, 400), f"got {r.status_code}: OneToOne collides with soft-deleted row")

    def test_check_slug_reports_soft_deleted_slug_as_available(self):
        """Soft-deleted portfolio ki slug dobara available honi chahiye (client's decision)."""
        p = make_portfolio(slug="taken-slug")
        p.soft_delete()
        # Ab test check karega ke slug AVAILABLE hai (True)
        self.assertTrue(self.c.get(CHECK, {"slug": "taken-slug"}).json()["data"]["available"])

    def test_deleted_at_cannot_be_set_through_api(self):
        p = make_portfolio()
        self.c.patch(detail(p.pk), {"deleted_at": "2020-01-01T00:00:00Z"}, format="json")
        self.assertTrue(Portfolio.objects.filter(pk=p.pk).exists(), "client can soft-delete via PATCH deleted_at")


class PortfolioReadUpdateTests(Base):
    def test_list_retrieve_update(self):
        p = make_portfolio(title="Old Title")
        self.assertEqual(rows(self.c.get(URL))[0]["id"], p.pk)
        self.assertEqual(self.c.get(detail(p.pk)).json()["title"], "Old Title")
        r = self.c.patch(detail(p.pk), {"title": "New Title"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["slug"], p.slug)  # slug is stable on edit

    def test_slug_cannot_be_changed(self):
        p = make_portfolio(slug="stable")
        self.c.patch(detail(p.pk), {"slug": "changed"}, format="json")
        p.refresh_from_db()
        self.assertEqual(p.slug, "stable")

    def test_status_change_via_patch_manages_published_at(self):
        p = make_portfolio()
        r = self.c.patch(detail(p.pk), {"status": "published"}, format="json")
        self.assertIsNotNone(r.json()["published_at"])
        r = self.c.patch(detail(p.pk), {"status": "unpublished"}, format="json")
        self.assertIsNone(r.json()["published_at"])

    def test_published_at_is_read_only(self):
        p = make_portfolio()
        self.c.patch(detail(p.pk), {"published_at": "2001-01-01T00:00:00Z"}, format="json")
        p.refresh_from_db()
        self.assertIsNone(p.published_at)

    def test_republishing_via_patch_keeps_original_published_at(self):
        p = make_portfolio()
        first = self.c.patch(detail(p.pk), {"status": "published"}, format="json").json()["published_at"]
        again = self.c.patch(detail(p.pk), {"status": "published", "title": "x"}, format="json").json()["published_at"]
        self.assertEqual(first, again)

    def test_filters_search_ordering(self):
        t2 = make_template()
        a = make_portfolio(title="Alpha Study", status="published")
        b = make_portfolio(title="Beta Study", template=t2)
        ids = lambda r: {x["id"] for x in rows(r)}
        self.assertEqual(ids(self.c.get(URL, {"status": "published"})), {a.pk})
        self.assertEqual(ids(self.c.get(URL, {"template": t2.pk})), {b.pk})
        self.assertEqual(ids(self.c.get(URL, {"client": a.client_id})), {a.pk})
        self.assertEqual(ids(self.c.get(URL, {"search": "beta"})), {b.pk})
        titles = [x["title"] for x in rows(self.c.get(URL, {"ordering": "title"}))]
        self.assertEqual(titles, sorted(titles))
        self.assertEqual(self.c.get(URL, {"status": "bogus"}).status_code, 400)

    def test_soft_delete(self):
        p = make_portfolio()
        self.assertEqual(self.c.delete(detail(p.pk)).status_code, 200)
        self.assertEqual(self.c.get(detail(p.pk)).status_code, 404)
        self.assertTrue(Portfolio.all_objects.filter(pk=p.pk).exists())

    def test_404s(self):
        self.assertEqual(self.c.get(detail(99999)).status_code, 404)
        self.assertEqual(self.c.post(f"{detail(99999)}publish/").status_code, 404)


class PublishTests(Base):
    def test_publish_sets_status_timestamp_and_logs(self):
        p = make_portfolio()
        r = self.c.post(f"{detail(p.pk)}publish/")
        self.assertEqual(r.status_code, 200, r.content)
        p.refresh_from_db()
        self.assertEqual(p.status, "published")
        self.assertIsNotNone(p.published_at)
        log = ActivityLog.objects.get()
        self.assertEqual((log.action, log.actor, log.portfolio, log.client), ("portfolio_published", self.admin, p, p.client))

    def test_unpublish_and_log(self):
        p = make_portfolio(status="published")
        self.assertEqual(self.c.post(f"{detail(p.pk)}unpublish/").status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "unpublished")
        self.assertEqual(ActivityLog.objects.get().action, "portfolio_unpublished")

    def test_publish_only_accepts_post(self):
        p = make_portfolio()
        self.assertEqual(self.c.get(f"{detail(p.pk)}publish/").status_code, 405)

    def test_cannot_publish_soft_deleted(self):
        p = make_portfolio()
        p.soft_delete()
        self.assertEqual(self.c.post(f"{detail(p.pk)}publish/").status_code, 404)


class CheckSlugTests(Base):
    def slug(self, s):
        return self.c.get(CHECK, {"slug": s}).json()["data"]

    def test_available_taken_reserved_empty(self):
        make_portfolio(slug="taken")
        self.assertTrue(self.slug("free-slug")["available"])
        self.assertFalse(self.slug("taken")["available"])
        self.assertFalse(self.slug("TAKEN")["available"])
        for reserved in ["admin", "api", "login", "static", "media", "ADMIN"]:
            self.assertFalse(self.slug(reserved)["available"], reserved)
        self.assertFalse(self.slug("")["available"])
        self.assertFalse(self.c.get(CHECK).json()["data"]["available"])

    def test_hostile_slug_input(self):
        self.assertEqual(self.c.get(CHECK, {"slug": "'; DROP TABLE portfolios;--"}).status_code, 200)


class CoreChildTablesTests(Base):
    def setUp(self):
        super().setUp()
        self.p = make_portfolio()

    def test_contact_one_per_portfolio(self):
        url = "/api/portfolios/contacts/"
        r = self.c.post(url, {"portfolio": self.p.pk, "email": "c@example.com", "city": "Lahore"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.c.post(url, {"portfolio": self.p.pk, "email": "d@example.com"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(url, {"portfolio": make_portfolio().pk, "email": "bad"}, format="json").status_code, 400)

    def test_social_links(self):
        url = "/api/portfolios/social-links/"
        good = {"portfolio": self.p.pk, "platform": "github", "url": "https://github.com/x"}
        self.assertEqual(self.c.post(url, good, format="json").status_code, 201)
        self.assertEqual(self.c.post(url, good, format="json").status_code, 400)  # duplicate platform
        self.assertEqual(self.c.post(url, {**good, "platform": "myspace"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(url, {**good, "platform": "orcid", "url": "not a url"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(url, {**good, "platform": "orcid", "url": "javascript:alert(1)"}, format="json").status_code, 400)

    def test_process_steps_max_four(self):
        url = "/api/portfolios/process-steps/"
        for i in range(4):
            r = self.c.post(url, {"portfolio": self.p.pk, "title": f"Step {i}", "display_order": i}, format="json")
            self.assertEqual(r.status_code, 201, r.content)
        r = self.c.post(url, {"portfolio": self.p.pk, "title": "Step 5"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(ProcessStep.objects.filter(portfolio=self.p).count(), 4)
        # a different portfolio still has its own quota
        self.assertEqual(self.c.post(url, {"portfolio": make_portfolio().pk, "title": "ok"}, format="json").status_code, 201)

    def test_process_step_edit_allowed_at_max(self):
        for i in range(4):
            ProcessStep.objects.create(portfolio=self.p, title=f"s{i}", display_order=i)
        step = ProcessStep.objects.first()
        r = self.c.patch(f"/api/portfolios/process-steps/{step.pk}/", {"title": "renamed"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

    def test_page_intros_unique_per_page(self):
        url = "/api/portfolios/page-intros/"
        self.assertEqual(self.c.post(url, {"portfolio": self.p.pk, "page": "home", "title": "Hi"}, format="json").status_code, 201)
        self.assertEqual(self.c.post(url, {"portfolio": self.p.pk, "page": "home"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(url, {"portfolio": self.p.pk, "page": "nope"}, format="json").status_code, 400)
        other = PageIntro.objects.create(portfolio=self.p, page="blogs")
        r = self.c.patch(f"{url}{other.pk}/", {"page": "home"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_filter_by_portfolio_query_param(self):
        other = make_portfolio()
        PageIntro.objects.create(portfolio=self.p, page="home")
        PageIntro.objects.create(portfolio=other, page="home")
        r = self.c.get("/api/portfolios/page-intros/", {"portfolio": self.p.pk})
        self.assertEqual(len(rows(r)) if "results" in r.json() else len(r.json()), 1)

    def test_cannot_attach_child_to_soft_deleted_portfolio(self):
        self.p.soft_delete()
        r = self.c.post("/api/portfolios/process-steps/", {"portfolio": self.p.pk, "title": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
