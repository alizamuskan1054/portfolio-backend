"""Education, Experience, Interests, Expertise, Awards, Memberships."""
from django.test import TestCase

from apps.common.factories import api_client, make_portfolio, make_user, rows

BASE = "/api/portfolios/"

SIMPLE = {
    "educations": {"degree": "PhD", "institution": "MIT", "field_of_study": "CS", "start_year": 2010, "end_year": 2014},
    "research-interests": {"title": "NLP"},
    "expertise": {"name": "Machine Learning"},
    "awards": {"title": "Best Paper", "issuing_organization": "ACM", "year": 2020},
    "memberships": {"organization_name": "IEEE", "role": "Member"},
    "experiences": {"job_title": "Lecturer", "organization": "LUMS", "start_date": "2015-01-01", "end_date": "2018-01-01"},
}
REQUIRED = {
    "educations": ["degree", "institution", "field_of_study", "start_year"],
    "research-interests": ["title"],
    "expertise": ["name"],
    "awards": ["title", "issuing_organization", "year"],
    "memberships": ["organization_name", "role"],
    "experiences": ["job_title", "organization", "start_date"],
}


class AcademicCrudTests(TestCase):
    def setUp(self):
        self.c = api_client(make_user())
        self.p = make_portfolio()

    def data(self, key, **over):
        return {"portfolio": self.p.pk, **SIMPLE[key], **over}

    def test_full_crud_for_every_table(self):
        for key in SIMPLE:
            with self.subTest(table=key):
                url = f"{BASE}{key}/"
                r = self.c.post(url, self.data(key), format="json")
                self.assertEqual(r.status_code, 201, r.content)
                pk = r.json()["id"]
                self.assertEqual(self.c.get(f"{url}{pk}/").status_code, 200)
                self.assertEqual(self.c.patch(f"{url}{pk}/", {"display_order": 5}, format="json").status_code, 200)
                self.assertEqual(self.c.get(f"{url}{pk}/").json()["display_order"], 5)
                self.assertEqual(self.c.delete(f"{url}{pk}/").status_code, 204)
                self.assertEqual(self.c.get(f"{url}{pk}/").status_code, 404)

    def test_required_fields_for_every_table(self):
        for key, fields in REQUIRED.items():
            for field in fields:
                with self.subTest(table=key, field=field):
                    d = self.data(key)
                    d.pop(field)
                    r = self.c.post(f"{BASE}{key}/", d, format="json")
                    self.assertEqual(r.status_code, 400)

    def test_portfolio_required_and_must_exist(self):
        for key in SIMPLE:
            with self.subTest(table=key):
                d = self.data(key)
                d.pop("portfolio")
                self.assertEqual(self.c.post(f"{BASE}{key}/", d, format="json").status_code, 400)
                self.assertEqual(self.c.post(f"{BASE}{key}/", {**d, "portfolio": 99999}, format="json").status_code, 400)

    def test_permissions_for_every_table(self):
        for key in SIMPLE:
            with self.subTest(table=key):
                self.assertEqual(api_client().get(f"{BASE}{key}/").status_code, 401)
                self.assertEqual(api_client(make_user(staff=False)).get(f"{BASE}{key}/").status_code, 403)

    def test_filter_by_portfolio(self):
        other = make_portfolio()
        self.c.post(f"{BASE}awards/", self.data("awards"), format="json")
        self.c.post(f"{BASE}awards/", {**self.data("awards"), "portfolio": other.pk}, format="json")
        self.assertEqual(len(rows(self.c.get(f"{BASE}awards/"))), 2)
        self.assertEqual(len(rows(self.c.get(f"{BASE}awards/", {"portfolio": self.p.pk}))), 1)

    def test_negative_and_non_numeric_years(self):
        self.assertEqual(self.c.post(f"{BASE}awards/", self.data("awards", year=-5), format="json").status_code, 400)
        self.assertEqual(self.c.post(f"{BASE}awards/", self.data("awards", year="abc"), format="json").status_code, 400)

    def test_items_returned_in_display_order(self):
        for order in (3, 1, 2):
            self.c.post(f"{BASE}expertise/", self.data("expertise", display_order=order), format="json")
        orders = [r["display_order"] for r in rows(self.c.get(f"{BASE}expertise/"))]
        self.assertEqual(orders, [1, 2, 3])


class ExperienceRuleTests(TestCase):
    def setUp(self):
        self.c = api_client(make_user())
        self.p = make_portfolio()
        self.url = f"{BASE}experiences/"

    def data(self, **over):
        d = {"portfolio": self.p.pk, **SIMPLE["experiences"]}
        d.update(over)
        return d

    def test_current_job_without_end_date(self):
        d = self.data(is_current=True)
        d.pop("end_date")
        self.assertEqual(self.c.post(self.url, d, format="json").status_code, 201)

    def test_current_job_with_end_date_rejected(self):
        self.assertEqual(self.c.post(self.url, self.data(is_current=True), format="json").status_code, 400)

    def test_past_job_without_end_date_rejected(self):
        d = self.data()
        d.pop("end_date")
        self.assertEqual(self.c.post(self.url, d, format="json").status_code, 400)

    def test_invalid_date_format(self):
        self.assertEqual(self.c.post(self.url, self.data(start_date="31/12/2020"), format="json").status_code, 400)
        self.assertEqual(self.c.post(self.url, self.data(start_date="2020-02-31"), format="json").status_code, 400)

    def test_end_date_before_start_date_rejected_RISK(self):
        r = self.c.post(self.url, self.data(start_date="2020-01-01", end_date="2019-01-01"), format="json")
        self.assertEqual(r.status_code, 400, "end date before start date was accepted")


class EducationRuleTests(TestCase):
    def test_end_year_before_start_year_rejected_RISK(self):
        c = api_client(make_user())
        p = make_portfolio()
        r = c.post(f"{BASE}educations/", {"portfolio": p.pk, **SIMPLE["educations"], "start_year": 2015, "end_year": 2010}, format="json")
        self.assertEqual(r.status_code, 400, "end_year < start_year was accepted")

    def test_end_year_optional(self):
        c = api_client(make_user())
        d = {"portfolio": make_portfolio().pk, **SIMPLE["educations"]}
        d.pop("end_year")
        self.assertEqual(c.post(f"{BASE}educations/", d, format="json").status_code, 201)
