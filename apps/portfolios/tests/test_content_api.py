"""Services, categories, projects, gallery, publications, blogs, testimonials, inbox."""
from django.test import TestCase

from apps.common.factories import api_client, make_image, make_portfolio, make_user, rows
from apps.portfolios.models import Blog, Category, ContactMessage, Project, Service

B = "/api/portfolios/"


class Base(TestCase):
    def setUp(self):
        self.c = api_client(make_user())
        self.p = make_portfolio()


class ServiceTests(Base):
    url = B + "services/"

    def data(self, **over):
        d = {"portfolio": self.p.pk, "title": "Consulting", "short_description": "s", "detailed_description": "d"}
        d.update(over)
        return d

    def test_create_and_validation(self):
        self.assertEqual(self.c.post(self.url, self.data(), format="json").status_code, 201)
        for field in ["title", "short_description", "detailed_description", "portfolio"]:
            d = self.data()
            d.pop(field)
            self.assertEqual(self.c.post(self.url, d, format="json").status_code, 400, field)
        self.assertEqual(self.c.post(self.url, self.data(external_link="not a url"), format="json").status_code, 400)

    def test_only_one_featured_per_portfolio(self):
        self.assertEqual(self.c.post(self.url, self.data(is_featured=True), format="json").status_code, 201)
        r = self.c.post(self.url, self.data(title="Second", is_featured=True), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("is_featured", r.json()["errors"])
        # other portfolio is unaffected
        r = self.c.post(self.url, self.data(portfolio=make_portfolio().pk, is_featured=True), format="json")
        self.assertEqual(r.status_code, 201)

    def test_updating_the_featured_service_itself_is_allowed(self):
        pk = self.c.post(self.url, self.data(is_featured=True), format="json").json()["id"]
        r = self.c.patch(f"{self.url}{pk}/", {"title": "Renamed", "is_featured": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

    def test_moving_featured_flag_to_second_service_blocked(self):
        self.c.post(self.url, self.data(is_featured=True), format="json")
        pk2 = self.c.post(self.url, self.data(title="B"), format="json").json()["id"]
        self.assertEqual(self.c.patch(f"{self.url}{pk2}/", {"is_featured": True}, format="json").status_code, 400)

    def test_filters_and_search(self):
        Service.objects.create(portfolio=self.p, title="Alpha", short_description="x", detailed_description="d", is_visible=False)
        Service.objects.create(portfolio=self.p, title="Beta", short_description="x", detailed_description="d")
        self.assertEqual(len(rows(self.c.get(self.url, {"is_visible": "false"}))), 1)
        self.assertEqual(len(rows(self.c.get(self.url, {"search": "alpha"}))), 1)

    def test_image_validation(self):
        self.assertEqual(self.c.post(self.url, {**self.data(), "image": make_image()}, format="multipart").status_code, 201)
        self.assertEqual(self.c.post(self.url, {**self.data(), "image": make_image("a.bmp", "BMP")}, format="multipart").status_code, 400)

    def test_reorder_RISK(self):
        a = Service.objects.create(portfolio=self.p, title="A", short_description="x", detailed_description="d", display_order=0)
        b = Service.objects.create(portfolio=self.p, title="B", short_description="x", detailed_description="d", display_order=1)
        r = self.c.post(f"{self.url}reorder/", [{"id": a.pk, "display_order": 1}, {"id": b.pk, "display_order": 0}], format="json")
        self.assertEqual(r.status_code, 200, f"reorder crashed with {r.status_code}")
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.display_order, b.display_order), (1, 0))

    def test_reorder_rejects_non_list_RISK(self):
        r = self.c.post(f"{self.url}reorder/", {"id": 1}, format="json")
        self.assertEqual(r.status_code, 400, f"got {r.status_code}")


class CategoryTests(Base):
    url = B + "categories/"

    def test_create_generates_slug_RISK(self):
        r = self.c.post(self.url, {"portfolio": self.p.pk, "kind": "blog", "name": "Machine Learning"}, format="json")
        self.assertEqual(r.status_code, 201, f"got {r.status_code}: {r.content[:200]}")
        self.assertEqual(r.json()["slug"], "machine-learning")

    def test_duplicate_names_get_distinct_slugs_RISK(self):
        for _ in range(2):
            r = self.c.post(self.url, {"portfolio": self.p.pk, "kind": "blog", "name": "AI"}, format="json")
            self.assertEqual(r.status_code, 201, f"got {r.status_code}")
        self.assertEqual(Category.objects.values("slug").distinct().count(), 2)

    def test_validation(self):
        self.assertEqual(self.c.post(self.url, {"portfolio": self.p.pk, "kind": "nope", "name": "x"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(self.url, {"portfolio": self.p.pk, "kind": "blog"}, format="json").status_code, 400)

    def test_filter_by_kind(self):
        Category.objects.create(portfolio=self.p, kind="blog", name="b", slug="b")
        Category.objects.create(portfolio=self.p, kind="project", name="p", slug="p")
        self.assertEqual(len(rows(self.c.get(self.url, {"kind": "blog"}))), 1)


class ProjectTests(Base):
    url = B + "projects/"

    def data(self, **over):
        d = {"portfolio": self.p.pk, "title": "Proj", "short_description": "s", "full_description": "f", "year": 2023}
        d.update(over)
        return d

    def test_create_and_defaults(self):
        r = self.c.post(self.url, self.data(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["status"], "ongoing")
        self.assertEqual(r.json()["gallery_images"], [])

    def test_validation(self):
        self.assertEqual(self.c.post(self.url, self.data(status="weird"), format="json").status_code, 400)
        self.assertEqual(self.c.post(self.url, self.data(year=-1), format="json").status_code, 400)
        self.assertEqual(self.c.post(self.url, self.data(category=99999), format="json").status_code, 400)
        for f in ["title", "short_description", "full_description", "year"]:
            d = self.data()
            d.pop(f)
            self.assertEqual(self.c.post(self.url, d, format="json").status_code, 400, f)

    def test_filters_search_ordering(self):
        Project.objects.create(portfolio=self.p, title="Old", short_description="s", full_description="f", year=2010, status="completed")
        Project.objects.create(portfolio=self.p, title="New", short_description="s", full_description="f", year=2024, is_featured=True)
        self.assertEqual(len(rows(self.c.get(self.url, {"status": "completed"}))), 1)
        self.assertEqual(len(rows(self.c.get(self.url, {"is_featured": "true"}))), 1)
        self.assertEqual(len(rows(self.c.get(self.url, {"search": "new"}))), 1)
        years = [r["year"] for r in rows(self.c.get(self.url, {"ordering": "-year"}))]
        self.assertEqual(years, [2024, 2010])

    def test_gallery_images(self):
        proj = Project.objects.create(portfolio=self.p, title="t", short_description="s", full_description="f", year=2020)
        g = B + "project-images/"
        r = self.c.post(g, {"project": proj.pk, "image": make_image(), "caption": "c"}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.c.post(g, {"project": proj.pk, "image": make_image("a.bmp", "BMP")}, format="multipart").status_code, 400)
        self.assertEqual(self.c.post(g, {"image": make_image()}, format="multipart").status_code, 400)
        listed = self.c.get(g, {"project": proj.pk}).json()
        listed = listed["results"] if isinstance(listed, dict) else listed
        self.assertEqual(len(listed), 1)
        detail = self.c.get(f"{self.url}{proj.pk}/").json()
        self.assertEqual(len(detail["gallery_images"]), 1)


class PublicationTests(Base):
    url = B + "publications/"

    def data(self, **over):
        d = {"portfolio": self.p.pk, "title": "Paper", "authors": "A, B", "venue": "Nature", "year": 2022, "type": "journal_article"}
        d.update(over)
        return d

    def test_create_and_validation(self):
        self.assertEqual(self.c.post(self.url, self.data(), format="json").status_code, 201)
        self.assertEqual(self.c.post(self.url, self.data(type="blog_post"), format="json").status_code, 400)
        self.assertEqual(self.c.post(self.url, self.data(external_url="nope"), format="json").status_code, 400)
        self.assertEqual(self.c.post(self.url, self.data(doi="x" * 101), format="json").status_code, 400)
        for f in ["title", "authors", "venue", "year", "type"]:
            d = self.data()
            d.pop(f)
            self.assertEqual(self.c.post(self.url, d, format="json").status_code, 400, f)

    def test_filters(self):
        self.c.post(self.url, self.data(year=2020), format="json")
        self.c.post(self.url, self.data(year=2021, type="book"), format="json")
        self.assertEqual(len(rows(self.c.get(self.url, {"year": 2021}))), 1)
        self.assertEqual(len(rows(self.c.get(self.url, {"type": "book"}))), 1)
        self.assertEqual(len(rows(self.c.get(self.url, {"search": "nature"}))), 2)


class BlogTests(Base):
    url = B + "blogs/"

    def data(self, **over):
        d = {"portfolio": self.p.pk, "title": "My First Post", "excerpt": "e", "content": "c"}
        d.update(over)
        return d

    def test_create_generates_slug_RISK(self):
        r = self.c.post(self.url, self.data(), format="json")
        self.assertEqual(r.status_code, 201, f"got {r.status_code}: {r.content[:200]}")
        self.assertEqual(r.json()["slug"], "my-first-post")

    def test_duplicate_titles_get_unique_slugs_RISK(self):
        for _ in range(2):
            self.assertEqual(self.c.post(self.url, self.data(), format="json").status_code, 201)
        self.assertEqual(Blog.objects.values("slug").distinct().count(), 2)

    def test_published_on_create_sets_timestamp_RISK(self):
        r = self.c.post(self.url, self.data(status="published"), format="json")
        self.assertEqual(r.status_code, 201, f"got {r.status_code}")
        self.assertIsNotNone(r.json()["published_at"])

    def test_publish_via_patch_sets_timestamp(self):
        b = Blog.objects.create(portfolio=self.p, title="t", slug="t", excerpt="e", content="c")
        r = self.c.patch(f"{self.url}{b.pk}/", {"status": "published"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNotNone(r.json()["published_at"])

    def test_slug_is_read_only(self):
        b = Blog.objects.create(portfolio=self.p, title="t", slug="orig", excerpt="e", content="c")
        self.c.patch(f"{self.url}{b.pk}/", {"slug": "changed"}, format="json")
        b.refresh_from_db()
        self.assertEqual(b.slug, "orig")

    def test_validation(self):
        self.assertEqual(self.c.post(self.url, self.data(status="archived"), format="json").status_code, 400)
        self.assertEqual(self.c.post(self.url, self.data(reading_time=-1), format="json").status_code, 400)
        for f in ["title", "excerpt", "content", "portfolio"]:
            d = self.data()
            d.pop(f)
            self.assertEqual(self.c.post(self.url, d, format="json").status_code, 400, f)


class TestimonialTests(Base):
    url = B + "testimonials/"

    def test_crud_and_validation(self):
        r = self.c.post(self.url, {"portfolio": self.p.pk, "author_name": "Jane", "quote": "Great"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()["is_visible"])
        self.assertEqual(self.c.post(self.url, {"portfolio": self.p.pk, "author_name": "Jane"}, format="json").status_code, 400)
        self.assertEqual(self.c.patch(f"{self.url}{r.json()['id']}/", {"is_visible": False}, format="json").status_code, 200)
        self.assertEqual(len(rows(self.c.get(self.url, {"is_visible": "true"}))), 0)

    def test_photo_validation(self):
        d = {"portfolio": self.p.pk, "author_name": "J", "quote": "q", "author_photo": make_image("a.bmp", "BMP")}
        self.assertEqual(self.c.post(self.url, d, format="multipart").status_code, 400)


class InboxTests(Base):
    url = B + "messages/"

    def setUp(self):
        super().setUp()
        self.msg = ContactMessage.objects.create(portfolio=self.p, full_name="n", email="e@example.com", subject="s", message="m")

    def test_list_and_retrieve(self):
        self.assertEqual(len(rows(self.c.get(self.url))), 1)
        self.assertEqual(self.c.get(f"{self.url}{self.msg.pk}/").status_code, 200)

    def test_filter_by_portfolio(self):
        ContactMessage.objects.create(portfolio=make_portfolio(), full_name="n", email="e@example.com", subject="s", message="m")
        self.assertEqual(len(rows(self.c.get(self.url, {"portfolio": self.p.pk}))), 1)

    def test_only_is_read_can_change(self):
        self.assertEqual(self.c.post(self.url, {}, format="json").status_code, 405)
        self.assertEqual(self.c.put(f"{self.url}{self.msg.pk}/", {}, format="json").status_code, 405)
        self.assertEqual(self.c.delete(f"{self.url}{self.msg.pk}/").status_code, 405)
        self.assertEqual(self.c.patch(f"{self.url}{self.msg.pk}/", {"is_read": True}, format="json").status_code, 200)

    def test_requires_admin(self):
        self.assertEqual(api_client().get(self.url).status_code, 401)
        self.assertEqual(api_client(make_user(staff=False)).get(self.url).status_code, 403)
