"""User model / manager tests."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.common.factories import PASSWORD, make_user

User = get_user_model()


class UserManagerTests(TestCase):
    def test_create_user_normalizes_domain_and_hashes_password(self):
        u = User.objects.create_user("Bob@EXAMPLE.COM", "Bob", PASSWORD)
        self.assertEqual(u.email, "Bob@example.com")
        self.assertNotEqual(u.password, PASSWORD)
        self.assertTrue(u.check_password(PASSWORD))

    def test_create_user_defaults_inactive_non_staff(self):
        u = User.objects.create_user("a@example.com", "A", PASSWORD)
        self.assertFalse(u.is_active)
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)
        self.assertIsNone(u.email_verified_at)

    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("", "A", PASSWORD)

    def test_create_superuser_flags(self):
        u = User.objects.create_superuser("root@example.com", "Root", PASSWORD)
        self.assertTrue(u.is_staff and u.is_superuser and u.is_active)
        self.assertIsNotNone(u.email_verified_at)

    def test_create_superuser_rejects_bad_flags(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser("r@example.com", "R", PASSWORD, is_staff=False)
        with self.assertRaises(ValueError):
            User.objects.create_superuser("r2@example.com", "R", PASSWORD, is_superuser=False)

    def test_email_is_unique(self):
        make_user("dup@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_user("dup@example.com")

    def test_str_and_table(self):
        u = make_user("s@example.com")
        self.assertEqual(str(u), "s@example.com")
        self.assertEqual(User._meta.db_table, "users")
        self.assertEqual(User.USERNAME_FIELD, "email")


class LockoutTests(TestCase):
    def test_is_locked_variants(self):
        u = make_user()
        self.assertFalse(u.is_locked())
        u.locked_until = timezone.now() + timedelta(minutes=5)
        self.assertTrue(u.is_locked())
        u.locked_until = timezone.now() - timedelta(seconds=1)
        self.assertFalse(u.is_locked())
