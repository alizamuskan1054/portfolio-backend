"""Unit tests for apps.common.validators (no DB needed)."""
from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.common.validators import (
    MAX_CV_SIZE_BYTES, MAX_IMAGE_SIZE_BYTES, validate_cv_file, validate_date_range,
    validate_image_file, validate_phone_number, validate_reserved_slug,
)


class FakeFile:
    def __init__(self, content_type, size):
        self.content_type = content_type
        self.size = size


class PhoneValidatorTests(SimpleTestCase):
    def test_valid_numbers(self):
        for v in ["+923001234567", "0300 1234567", "(021) 123-4567", "+1 (555) 123-4567", "1234567"]:
            with self.subTest(v=v):
                validate_phone_number(v)

    def test_invalid_numbers(self):
        for v in ["abc", "12", "+", "12345!@#", "+" + "1" * 30, "phone: 12345678", "1234567; DROP TABLE"]:
            with self.subTest(v=v):
                with self.assertRaises(ValidationError):
                    validate_phone_number(v)

    def test_empty_values_are_allowed(self):
        validate_phone_number("")
        validate_phone_number(None)


class ReservedSlugTests(SimpleTestCase):
    def test_reserved_slugs_rejected_case_insensitively(self):
        for v in ["admin", "ADMIN", "Api", "login", "static", "media"]:
            with self.subTest(v=v):
                with self.assertRaises(ValidationError):
                    validate_reserved_slug(v)

    def test_normal_slug_ok(self):
        validate_reserved_slug("dr-ahmad")
        validate_reserved_slug("administrator")  # only exact matches are reserved
        validate_reserved_slug("")


class ImageValidatorTests(SimpleTestCase):
    def test_allowed_types(self):
        for ct in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
            with self.subTest(ct=ct):
                validate_image_file(FakeFile(ct, 100))

    def test_rejected_types(self):
        for ct in ["image/svg+xml", "application/pdf", "text/html", "image/bmp", "", None]:
            with self.subTest(ct=ct):
                with self.assertRaises(ValidationError):
                    validate_image_file(FakeFile(ct, 100))

    def test_file_without_content_type_rejected(self):
        with self.assertRaises(ValidationError):
            validate_image_file(object())

    def test_size_boundary(self):
        validate_image_file(FakeFile("image/png", MAX_IMAGE_SIZE_BYTES))
        with self.assertRaises(ValidationError):
            validate_image_file(FakeFile("image/png", MAX_IMAGE_SIZE_BYTES + 1))

    def test_none_is_ok(self):
        validate_image_file(None)


class CvValidatorTests(SimpleTestCase):
    def test_pdf_ok(self):
        validate_cv_file(FakeFile("application/pdf", 1000))

    def test_non_pdf_rejected(self):
        for ct in ["application/msword", "image/png", "text/plain", None]:
            with self.subTest(ct=ct):
                with self.assertRaises(ValidationError):
                    validate_cv_file(FakeFile(ct, 10))

    def test_size_boundary(self):
        validate_cv_file(FakeFile("application/pdf", MAX_CV_SIZE_BYTES))
        with self.assertRaises(ValidationError):
            validate_cv_file(FakeFile("application/pdf", MAX_CV_SIZE_BYTES + 1))

    def test_none_ok(self):
        validate_cv_file(None)


class DateRangeTests(SimpleTestCase):
    def test_valid_range(self):
        validate_date_range(date(2020, 1, 1), date(2021, 1, 1))

    def test_equal_dates(self):
        validate_date_range(date(2020, 1, 1), date(2020, 1, 1))
        with self.assertRaises(ValidationError):
            validate_date_range(date(2020, 1, 1), date(2020, 1, 1), allow_equal=False)

    def test_end_before_start(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_date_range(date(2021, 1, 1), date(2020, 1, 1))
        self.assertIn("end date", ctx.exception.message_dict)

    def test_custom_label(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_date_range(date(2021, 1, 1), date(2020, 1, 1), label="end_year")
        self.assertIn("end_year", ctx.exception.message_dict)

    def test_missing_side_is_ignored(self):
        validate_date_range(None, date(2020, 1, 1))
        validate_date_range(date(2020, 1, 1), None)
