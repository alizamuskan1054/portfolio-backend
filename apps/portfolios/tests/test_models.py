"""DB-level constraints and cascades for portfolio models."""
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.common.factories import make_client_record, make_portfolio, make_template, make_user
from apps.portfolios.models import (
    ActivityLog, Blog, Category, ContactMessage, Education, PageIntro, Portfolio,
    PortfolioContact, ProcessStep, Project, ProjectImage, Service, SocialLink,
)


class PortfolioModelTests(TestCase):
    def setUp(self):
        self.p = make_portfolio()

    def test_defaults(self):
        self.assertEqual(self.p.status, "draft")
        self.assertIsNone(self.p.published_at)
        self.assertEqual((self.p.citations, self.p.h_index, self.p.total_publications), (0, 0, 0))

    def test_str(self):
        self.assertIn(self.p.title, str(self.p))

    def test_slug_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_portfolio(slug=self.p.slug)

    def test_client_can_have_several_portfolios(self):
        make_portfolio(client=self.p.client)  # limit API level par hai, DB par nahi

    def test_slug_unique_case_insensitive(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_portfolio(slug=self.p.slug.upper())

    def test_template_is_protected(self):
        with self.assertRaises(ProtectedError):
            self.p.template.delete()

    def test_deleting_client_cascades_to_portfolio(self):
        self.p.client.delete()
        self.assertFalse(Portfolio.all_objects.filter(pk=self.p.pk).exists())

    def test_hard_delete_cascades_to_all_children(self):
        Education.objects.create(portfolio=self.p, degree="PhD", institution="MIT", field_of_study="CS", start_year=2010)
        Service.objects.create(portfolio=self.p, title="s", short_description="s", detailed_description="d")
        cat = Category.objects.create(portfolio=self.p, kind="blog", name="n", slug="n")
        Blog.objects.create(portfolio=self.p, category=cat, title="b", slug="b", excerpt="e", content="c")
        PortfolioContact.objects.create(portfolio=self.p, email="c@example.com")
        SocialLink.objects.create(portfolio=self.p, platform="github", url="https://github.com/x")
        ContactMessage.objects.create(portfolio=self.p, full_name="n", email="e@example.com", subject="s", message="m")
        self.p.delete()
        for model in (Education, Service, Category, Blog, PortfolioContact, SocialLink, ContactMessage):
            self.assertEqual(model.objects.count(), 0, model.__name__)

    def test_social_link_unique_per_platform(self):
        SocialLink.objects.create(portfolio=self.p, platform="github", url="https://github.com/a")
        with self.assertRaises(IntegrityError), transaction.atomic():
            SocialLink.objects.create(portfolio=self.p, platform="github", url="https://github.com/b")
        other = make_portfolio()
        SocialLink.objects.create(portfolio=other, platform="github", url="https://github.com/b")

    def test_page_intro_unique_per_page(self):
        PageIntro.objects.create(portfolio=self.p, page="home")
        with self.assertRaises(IntegrityError), transaction.atomic():
            PageIntro.objects.create(portfolio=self.p, page="home")

    def test_one_featured_service_per_portfolio_at_db_level(self):
        mk = lambda **kw: Service.objects.create(portfolio=self.p, title="t", short_description="s", detailed_description="d", **kw)
        mk(is_featured=True)
        mk(is_featured=False)
        mk(is_featured=False)
        with self.assertRaises(IntegrityError), transaction.atomic():
            mk(is_featured=True)
        other = make_portfolio()
        Service.objects.create(portfolio=other, title="t", short_description="s", detailed_description="d", is_featured=True)

    def test_blog_slug_unique_per_portfolio_only(self):
        mk = lambda p: Blog.objects.create(portfolio=p, title="t", slug="same", excerpt="e", content="c")
        mk(self.p)
        with self.assertRaises(IntegrityError), transaction.atomic():
            mk(self.p)
        mk(make_portfolio())

    def test_category_slug_unique_per_portfolio_and_kind(self):
        Category.objects.create(portfolio=self.p, kind="blog", name="a", slug="a")
        Category.objects.create(portfolio=self.p, kind="project", name="a", slug="a")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(portfolio=self.p, kind="blog", name="a", slug="a")

    def test_deleting_category_keeps_blog_and_project(self):
        cat = Category.objects.create(portfolio=self.p, kind="blog", name="a", slug="a")
        b = Blog.objects.create(portfolio=self.p, category=cat, title="t", slug="t", excerpt="e", content="c")
        pr = Project.objects.create(portfolio=self.p, category=cat, title="t", short_description="s", full_description="f", year=2020)
        cat.delete()
        b.refresh_from_db(); pr.refresh_from_db()
        self.assertIsNone(b.category)
        self.assertIsNone(pr.category)

    def test_project_images_cascade(self):
        pr = Project.objects.create(portfolio=self.p, title="t", short_description="s", full_description="f", year=2020)
        ProjectImage.objects.create(project=pr, image="x.png")
        pr.delete()
        self.assertEqual(ProjectImage.objects.count(), 0)

    def test_activity_log_survives_deletion_of_actor_client_and_portfolio(self):
        user = make_user()
        log = ActivityLog.objects.create(actor=user, action="portfolio_published", client=self.p.client,
                                         portfolio=self.p, description="d")
        user.delete()
        self.p.delete()
        log.refresh_from_db()
        self.assertIsNone(log.actor)
        self.assertIsNone(log.portfolio)

    def test_ordering_of_children_by_display_order(self):
        for i, order in enumerate([3, 1, 2]):
            ProcessStep.objects.create(portfolio=self.p, title=f"s{i}", display_order=order)
        self.assertEqual([s.display_order for s in ProcessStep.objects.filter(portfolio=self.p)], [1, 2, 3])
