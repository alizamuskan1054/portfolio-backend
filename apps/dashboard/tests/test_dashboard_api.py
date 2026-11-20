"""Dashboard stats and recent activity tests."""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.common.factories import api_client, make_client_record, make_portfolio, make_user
from apps.portfolios.models import ActivityLog

STATS = "/api/dashboard/stats/"
RECENT = "/api/dashboard/recent-activity/"


class DashboardPermissionTests(TestCase):
    def test_auth_required(self):
        for u in (STATS, RECENT):
            self.assertEqual(api_client().get(u).status_code, 401)
            self.assertEqual(api_client(make_user(staff=False)).get(u).status_code, 403)
            self.assertEqual(api_client(make_user(verified=False)).get(u).status_code, 403)

    def test_read_only(self):
        c = api_client(make_user())
        for u in (STATS, RECENT):
            self.assertEqual(c.post(u, {}, format="json").status_code, 405)
            self.assertEqual(c.delete(u).status_code, 405)


class StatsTests(TestCase):
    def setUp(self):
        self.admin = make_user()
        self.c = api_client(self.admin)

    def stats(self):
        r = self.c.get(STATS)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["data"]

    def test_empty_database_is_all_zeros(self):
        # Planning ke mutabiq sirf 4 cards check ho rahe hain
        self.assertEqual(self.stats(), {
            "total_clients": 0, 
            "total_portfolios": 0, 
            "published_portfolios": 0, 
            "draft_portfolios": 0,
        })

    def test_counts(self):
        make_portfolio(status="published")
        make_portfolio(status="published")
        make_portfolio(status="draft")
        make_portfolio(status="unpublished")
        make_client_record()  # client without portfolio
        
        s = self.stats()
        self.assertEqual(s["total_clients"], 5)
        self.assertEqual(s["total_portfolios"], 4)
        self.assertEqual(s["published_portfolios"], 2)
        self.assertEqual(s["draft_portfolios"], 1)
        # total_projects aur total_publications ka check hata diya gaya hai

    def test_soft_deleted_records_not_counted(self):
        p = make_portfolio(status="published")
        p.soft_delete()
        p.client.soft_delete()
        s = self.stats()
        self.assertEqual((s["total_clients"], s["total_portfolios"], s["published_portfolios"]), (0, 0, 0))

    def test_stats_query_count_is_small(self):
        with CaptureQueriesContext(connection) as ctx:
            self.c.get(STATS)
        self.assertLessEqual(len(ctx), 12)


class RecentActivityTests(TestCase):
    def setUp(self):
        self.admin = make_user(full_name="Admin Person")
        self.c = api_client(self.admin)
        self.p = make_portfolio()

    def log(self, i):
        return ActivityLog.objects.create(actor=self.admin, action="portfolio_published", client=self.p.client,
                                          portfolio=self.p, description=f"log {i}")

    def data(self, **params):
        r = self.c.get(RECENT, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["data"]

    def test_empty(self):
        self.assertEqual(self.data(), [])

    def test_limited_to_ten_newest_first(self):
        for i in range(15):
            self.log(i)
        d = self.data()
        self.assertEqual(len(d), 10)
        self.assertEqual(d[0]["description"], "log 14")
        self.assertEqual(d[-1]["description"], "log 5")

    def test_fields_and_actor_name(self):
        self.log(1)
        item = self.data()[0]
        self.assertEqual(set(item), {"id", "action", "actor_name", "client", "portfolio", "description", "created_at"})
        self.assertEqual(item["actor_name"], "Admin Person")

    def test_log_survives_deleted_actor(self):
        self.log(1)
        self.admin.delete()
        # use another admin to read
        r = api_client(make_user()).get(RECENT)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()["data"][0].get("actor_name"))

    def test_query_count_does_not_grow_with_rows_RISK(self):
        for i in range(10):
            self.log(i)
        with CaptureQueriesContext(connection) as ctx:
            self.c.get(RECENT)
        self.assertLessEqual(len(ctx), 5, f"N+1 on actor lookup: {len(ctx)} queries")

    def test_ordering_query_param_does_not_crash_RISK(self):
        self.log(1)
        r = self.c.get(RECENT, {"ordering": "-id"})
        self.assertEqual(r.status_code, 200, f"got {r.status_code}: filtering a sliced queryset")

    def test_search_param_is_harmless(self):
        self.log(1)
        self.assertEqual(self.c.get(RECENT, {"search": "x"}).status_code, 200)