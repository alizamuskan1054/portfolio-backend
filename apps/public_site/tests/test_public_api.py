"""Public (no-login) API: visibility rules, data exposure, contact form, PDF."""
import os
import tempfile
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from apps.common.factories import api_client, make_client_record, make_portfolio, make_user
from apps.portfolios.models import (
    Award, Blog, ContactMessage, Education, Experience, PageIntro, PortfolioContact, ProcessStep,
    Project, ProjectImage, Publication, ResearchInterest, Service, SocialLink, Testimonial,
)

P = "/api/public/"


def url(slug, suffix=""):
    return f"{P}{slug}/{suffix}"


class PublicBase(TestCase):
    def setUp(self):
        self.c = api_client()
        self.p = make_portfolio(slug="dr-test", status="published", published_at=timezone.now(),
                                short_intro="intro", biography="bio")


class VisibilityTests(PublicBase):
    SUFFIXES = ["", "academic/", "services/", "projects/", "publications/", "blogs/", "testimonials/", "pdf/"]

    def test_published_portfolio_is_visible_without_login(self):
        for s in self.SUFFIXES[:-1]:
            with self.subTest(s=s):
                self.assertEqual(self.c.get(url("dr-test", s)).status_code, 200)

    def test_non_published_states_are_404_on_every_endpoint(self):
        draft = make_portfolio(slug="draft-one", status="draft")
        unpub = make_portfolio(slug="unpub-one", status="unpublished")
        gone = make_portfolio(slug="gone-one", status="published")
        gone.soft_delete()
        for slug in ["draft-one", "unpub-one", "gone-one", "does-not-exist"]:
            for s in self.SUFFIXES:
                with self.subTest(slug=slug, s=s):
                    r = self.c.get(url(slug, s))
                    self.assertEqual(r.status_code, 404)
                    self.assertFalse(r.json()["success"])

    def test_contact_form_blocked_for_unpublished(self):
        make_portfolio(slug="draft-two", status="draft")
        r = self.c.post(url("draft-two", "contact/"), {"full_name": "a", "email": "a@b.co", "subject": "s", "message": "m"}, format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_unpublishing_hides_immediately(self):
        self.p.status = "unpublished"
        self.p.save()
        self.assertEqual(self.c.get(url("dr-test")).status_code, 404)

    def test_weird_slugs_never_500(self):
        for slug in ["..%2f..%2fetc%2fpasswd", "%00", "a" * 400, "ADMIN", "' OR 1=1 --"]:
            with self.subTest(slug=slug[:20]):
                self.assertIn(self.c.get(f"{P}{slug}/").status_code, (404, 400))

    def test_write_methods_not_allowed_on_read_endpoints(self):
        for s in ["", "academic/", "services/", "projects/", "blogs/"]:
            for m in ["post", "put", "patch", "delete"]:
                with self.subTest(s=s, m=m):
                    self.assertEqual(getattr(self.c, m)(url("dr-test", s)).status_code, 405)

    def test_stale_or_invalid_admin_token_does_not_break_public_pages_RISK(self):
        """The React app may still send an expired Bearer token from the admin area."""
        admin = make_user()
        expired = AccessToken.for_user(admin)
        expired.set_exp(lifetime=-timedelta(minutes=1))
        for token in [str(expired), "garbage"]:
            with self.subTest(token=token[:10]):
                c = api_client()
                c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
                self.assertEqual(c.get(url("dr-test")).status_code, 200,
                                 "public endpoint fails when an invalid token header is present")


class PortfolioDetailTests(PublicBase):
    def test_payload_shape(self):
        PortfolioContact.objects.create(portfolio=self.p, email="c@example.com", phone="+92300", city="Lahore",
                                        country="PK", notification_email="private@example.com",
                                        form_success_message="Thanks!")
        SocialLink.objects.create(portfolio=self.p, platform="github", url="https://github.com/x")
        PageIntro.objects.create(portfolio=self.p, page="home", title="Welcome")
        ProcessStep.objects.create(portfolio=self.p, title="Plan", display_order=1)
        d = self.c.get(url("dr-test")).json()["data"]
        self.assertEqual(set(d), {"portfolio", "contact", "page_intros", "process_steps"})
        self.assertEqual(d["portfolio"]["slug"], "dr-test")
        self.assertEqual(d["portfolio"]["social_links"], [{"platform": "github", "url": "https://github.com/x"}])
        self.assertEqual(d["contact"]["email"], "c@example.com")
        self.assertEqual(len(d["page_intros"]), 1)
        self.assertEqual(len(d["process_steps"]), 1)

    def test_no_private_fields_leak(self):
        PortfolioContact.objects.create(portfolio=self.p, email="c@example.com", notification_email="private@example.com",
                                        form_success_message="x")
        raw = self.c.get(url("dr-test")).content.decode()
        for secret in ["private@example.com", "notification_email", "form_success_message", "deleted_at",
                       "cv_file", '"client"', '"template"', '"status"']:
            self.assertNotIn(secret, raw, secret)

    def test_contact_is_null_when_missing(self):
        self.assertIsNone(self.c.get(url("dr-test")).json()["data"]["contact"])

    def test_empty_lists_not_errors(self):
        d = self.c.get(url("dr-test")).json()["data"]
        self.assertEqual((d["page_intros"], d["process_steps"]), ([], []))


class AcademicTests(PublicBase):
    def test_returns_all_sections_even_when_empty(self):
        d = self.c.get(url("dr-test", "academic/")).json()["data"]
        self.assertEqual(set(d), {"educations", "experiences", "research_interests", "expertise", "awards", "memberships"})
        self.assertTrue(all(v == [] for v in d.values()))

    def test_returns_only_this_portfolios_rows(self):
        other = make_portfolio(status="published")
        Education.objects.create(portfolio=self.p, degree="PhD", institution="MIT", field_of_study="CS", start_year=2010)
        Education.objects.create(portfolio=other, degree="MSc", institution="X", field_of_study="Y", start_year=2010)
        Award.objects.create(portfolio=self.p, title="A", issuing_organization="O", year=2020)
        ResearchInterest.objects.create(portfolio=self.p, title="NLP")
        Experience.objects.create(portfolio=self.p, job_title="J", organization="O", start_date="2020-01-01", is_current=True)
        d = self.c.get(url("dr-test", "academic/")).json()["data"]
        self.assertEqual([e["degree"] for e in d["educations"]], ["PhD"])
        self.assertEqual(len(d["awards"]), 1)
        self.assertEqual(len(d["research_interests"]), 1)
        self.assertTrue(d["experiences"][0]["is_current"])
        self.assertNotIn("portfolio", d["educations"][0])

    def test_query_count_is_bounded(self):
        with CaptureQueriesContext(connection) as ctx:
            self.c.get(url("dr-test", "academic/"))
        self.assertLessEqual(len(ctx), 8)


class ServiceProjectTests(PublicBase):
    def test_services_visible_only_and_ordered(self):
        mk = lambda t, **kw: Service.objects.create(portfolio=self.p, title=t, short_description="s", detailed_description="d", **kw)
        mk("Second", display_order=2)
        mk("First", display_order=1)
        mk("Hidden", is_visible=False)
        titles = [s["title"] for s in self.c.get(url("dr-test", "services/")).json()["data"]]
        self.assertEqual(titles, ["First", "Second"])

    def test_service_detail_rules(self):
        s = Service.objects.create(portfolio=self.p, title="t", short_description="s", detailed_description="d")
        hidden = Service.objects.create(portfolio=self.p, title="h", short_description="s", detailed_description="d", is_visible=False)
        other = Service.objects.create(portfolio=make_portfolio(status="published"), title="o", short_description="s", detailed_description="d")
        self.assertEqual(self.c.get(url("dr-test", f"services/{s.pk}/")).status_code, 200)
        self.assertEqual(self.c.get(url("dr-test", f"services/{hidden.pk}/")).status_code, 404)
        self.assertEqual(self.c.get(url("dr-test", f"services/{other.pk}/")).status_code, 404)
        self.assertEqual(self.c.get(url("dr-test", "services/999999/")).status_code, 404)

    def test_projects_visible_only_with_gallery(self):
        mk = lambda t, **kw: Project.objects.create(portfolio=self.p, title=t, short_description="s", full_description="f", year=2020, **kw)
        shown = mk("Shown")
        mk("Hidden", is_visible=False)
        ProjectImage.objects.create(project=shown, image="x.png", caption="cap")
        data = self.c.get(url("dr-test", "projects/")).json()["data"]
        self.assertEqual([p["title"] for p in data], ["Shown"])
        self.assertEqual(len(data[0]["gallery_images"]), 1)

    def test_project_detail_rules(self):
        shown = Project.objects.create(portfolio=self.p, title="t", short_description="s", full_description="f", year=2020)
        hidden = Project.objects.create(portfolio=self.p, title="h", short_description="s", full_description="f", year=2020, is_visible=False)
        other = Project.objects.create(portfolio=make_portfolio(status="published"), title="o", short_description="s", full_description="f", year=2020)
        self.assertEqual(self.c.get(url("dr-test", f"projects/{shown.pk}/")).status_code, 200)
        self.assertEqual(self.c.get(url("dr-test", f"projects/{hidden.pk}/")).status_code, 404)
        self.assertEqual(self.c.get(url("dr-test", f"projects/{other.pk}/")).status_code, 404)
        self.assertEqual(self.c.get(url("dr-test", "projects/abc/")).status_code, 404)

    def test_project_list_query_count_RISK(self):
        for i in range(10):
            pr = Project.objects.create(portfolio=self.p, title=f"p{i}", short_description="s", full_description="f", year=2020)
            ProjectImage.objects.create(project=pr, image="x.png")
        with CaptureQueriesContext(connection) as ctx:
            self.c.get(url("dr-test", "projects/"))
        self.assertLessEqual(len(ctx), 6, f"N+1 on project gallery: {len(ctx)} queries")


class BlogPublicationTestimonialTests(PublicBase):
    def blog(self, slug, **kw):
        # FIX: default dictionary use karein taake 'content' duplicate na ho
        defaults = {
            "portfolio": self.p, 
            "title": slug, 
            "slug": slug, 
            "excerpt": "e", 
            "content": "c"
        }
        defaults.update(kw)
        return Blog.objects.create(**defaults)

    def test_only_published_blogs_newest_first(self):
        now = timezone.now()
        self.blog("old", status="published", published_at=now - timedelta(days=5))
        self.blog("new", status="published", published_at=now)
        self.blog("draft", status="draft")
        slugs = [b["slug"] for b in self.c.get(url("dr-test", "blogs/")).json()["data"]]
        self.assertEqual(slugs, ["new", "old"])

    def test_blog_detail(self):
        self.blog("live", status="published", published_at=timezone.now())
        self.blog("secret", status="draft")
        other_portfolio = make_portfolio(status="published")
        Blog.objects.create(portfolio=other_portfolio, title="x", slug="foreign", excerpt="e", content="c", status="published")
        self.assertEqual(self.c.get(url("dr-test", "blogs/live/")).status_code, 200)
        self.assertEqual(self.c.get(url("dr-test", "blogs/secret/")).status_code, 404)
        self.assertEqual(self.c.get(url("dr-test", "blogs/foreign/")).status_code, 404)

    def test_html_in_blog_content_is_returned_inert_as_json(self):
        self.blog("xss", status="published", published_at=timezone.now(), content="<script>alert(1)</script>")
        r = self.c.get(url("dr-test", "blogs/xss/"))
        self.assertTrue(r["Content-Type"].startswith("application/json"))
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")

    def test_publications(self):
        Publication.objects.create(portfolio=self.p, title="P1", authors="a", venue="v", year=2020, type="book", display_order=2)
        Publication.objects.create(portfolio=self.p, title="P2", authors="a", venue="v", year=2021, type="book", display_order=1)
        titles = [x["title"] for x in self.c.get(url("dr-test", "publications/")).json()["data"]]
        self.assertEqual(titles, ["P2", "P1"])

    def test_testimonials_visible_only(self):
        Testimonial.objects.create(portfolio=self.p, author_name="Shown", quote="q")
        Testimonial.objects.create(portfolio=self.p, author_name="Hidden", quote="q", is_visible=False)
        names = [t["author_name"] for t in self.c.get(url("dr-test", "testimonials/")).json()["data"]]
        self.assertEqual(names, ["Shown"])


class ContactFormTests(PublicBase):
    URL = url("dr-test", "contact/")

    def data(self, **over):
        d = {"full_name": "Visitor", "email": "v@example.com", "subject": "Hello", "message": "Nice work"}
        d.update(over)
        return d

    def test_submit_success_saves_message(self):
        r = self.c.post(self.URL, self.data(), format="json")
        self.assertEqual(r.status_code, 200, r.content)
        m = ContactMessage.objects.get()
        self.assertEqual((m.portfolio, m.inquiry_type, m.is_read), (self.p, "general", False))

    def test_custom_and_default_success_message(self):
        self.assertEqual(self.c.post(self.URL, self.data(), format="json").json()["message"], "Thank you for your message.")
        PortfolioContact.objects.create(portfolio=self.p, email="c@example.com", form_success_message="Custom thanks")
        self.assertEqual(self.c.post(self.URL, self.data(), format="json").json()["message"], "Custom thanks")

    def test_each_required_field(self):
        for f in ["full_name", "email", "subject", "message"]:
            with self.subTest(f=f):
                d = self.data()
                d.pop(f)
                self.assertEqual(self.c.post(self.URL, d, format="json").status_code, 400)
                self.assertEqual(self.c.post(self.URL, self.data(**{f: ""}), format="json").status_code, 400)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_inquiry_type_accepted(self):
        self.c.post(self.URL, self.data(inquiry_type="collaboration"), format="json")
        self.assertEqual(ContactMessage.objects.get().inquiry_type, "collaboration")

    def test_hostile_content_stored_inertly(self):
        for payload in ["<script>alert(1)</script>", "'; DROP TABLE contact_messages;--", "{{7*7}}"]:
            self.c.post(self.URL, self.data(message=payload), format="json")
        self.assertEqual(ContactMessage.objects.count(), 3)

    def test_get_not_allowed(self):
        self.assertEqual(self.c.get(self.URL).status_code, 405)

    def test_invalid_email_rejected_RISK(self):
        r = self.c.post(self.URL, self.data(email="not-an-email"), format="json")
        self.assertEqual(r.status_code, 400, "invalid email accepted by public contact form")
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_invalid_inquiry_type_rejected_RISK(self):
        r = self.c.post(self.URL, self.data(inquiry_type="hax"), format="json")
        self.assertEqual(r.status_code, 400, "arbitrary inquiry_type accepted")

    def test_overlong_fields_rejected_RISK(self):
        r = self.c.post(self.URL, self.data(subject="s" * 300), format="json")
        self.assertEqual(r.status_code, 400, "300-char subject accepted (DB column is 255; Postgres would 500)")

    def test_non_string_payloads_do_not_crash_RISK(self):
        for bad in [{"full_name": ["a"]}, {"email": {"x": 1}}, {"message": 123}]:
            with self.subTest(bad=bad):
                r = self.c.post(self.URL, self.data(**bad), format="json")
                self.assertLess(r.status_code, 500, f"got {r.status_code}")

    def test_non_json_body_does_not_crash(self):
        r = self.c.post(self.URL, "not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)


class PdfTests(PublicBase):
    URL = url("dr-test", "pdf/")

    def test_download_success(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test")
        self.addCleanup(os.unlink, f.name)
        with mock.patch("apps.public_site.views.generate_portfolio_pdf", return_value=f.name) as gen:
            r = self.c.get(self.URL)
            body = b"".join(r.streaming_content)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("dr-test_portfolio.pdf", r["Content-Disposition"])
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertTrue(body.startswith(b"%PDF"))
        gen.assert_called_once()

    def test_generation_failure_returns_clean_500(self):
        with mock.patch("apps.public_site.views.generate_portfolio_pdf", side_effect=RuntimeError("chromium missing")):
            r = self.c.get(self.URL)
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.json()["message"], "PDF generation failed.")
        self.assertNotIn("chromium", r.content.decode())

    def test_generator_builds_print_url_and_saves_pdf(self):
        from apps.public_site.pdf import generate_portfolio_pdf
        page = mock.MagicMock()
        browser = mock.MagicMock()
        browser.new_page.return_value = page
        pw = mock.MagicMock()
        pw.chromium.launch.return_value = browser
        with tempfile.TemporaryDirectory() as tmp, override_settings(BASE_DIR=tmp, FRONTEND_URL="http://front.test/"):
            with mock.patch("apps.public_site.pdf.sync_playwright") as sp:
                sp.return_value.__enter__.return_value = pw
                path = generate_portfolio_pdf(self.p)
            self.assertEqual(os.path.dirname(path), os.path.join(tmp, "tmp_pdfs"))
            self.assertTrue(path.endswith("dr-test_portfolio.pdf"))
        page.goto.assert_called_once_with("http://front.test/portfolio/dr-test/print", wait_until="networkidle")
        self.assertEqual(page.pdf.call_args.kwargs["format"], "A4")
        browser.close.assert_called_once()

    def test_browser_is_closed_even_if_navigation_fails_RISK(self):
        from apps.public_site.pdf import generate_portfolio_pdf
        
        page = mock.MagicMock()
        page.goto.side_effect = TimeoutError("boom")
        
        # Browser mock banayein
        browser = mock.MagicMock()
        browser.new_page.return_value = page
        
        # Playwright context mock banayein
        pw = mock.MagicMock()
        pw.chromium.launch.return_value = browser
        
        with tempfile.TemporaryDirectory() as tmp, override_settings(BASE_DIR=tmp):
            with mock.patch("apps.public_site.pdf.sync_playwright") as sp:
                sp.return_value.__enter__.return_value = pw
                
                with self.assertRaises(TimeoutError):
                    generate_portfolio_pdf(self.p)
        
        # Assertion: browser.close() call hona chahiye
        browser.close.assert_called_once()