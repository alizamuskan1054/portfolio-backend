"""Signup, email verification, login (+lockout), refresh, logout, password reset."""
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.common.factories import PASSWORD, api_client, jwt_client, make_user

User = get_user_model()

SIGNUP = "/api/auth/signup/"
VERIFY = "/api/auth/verify-email/"
LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/refresh/"
LOGOUT = "/api/auth/logout/"
FORGOT = "/api/auth/forgot-password/"
RESET = "/api/auth/reset-password/"


def uid_token(user):
    return urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user)


def signup_payload(**over):
    p = {"full_name": "Dr Admin", "email": "admin@example.com",
         "password": PASSWORD, "confirm_password": PASSWORD}
    p.update(over)
    return p


class SignupTests(TestCase):
    def setUp(self):
        self.c = api_client()

    def test_signup_success_creates_inactive_staff_and_sends_email(self):
        r = self.c.post(SIGNUP, signup_payload(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()["success"])
        u = User.objects.get(email="admin@example.com")
        self.assertFalse(u.is_active)
        self.assertTrue(u.is_staff)
        self.assertIsNone(u.email_verified_at)
        self.assertTrue(u.check_password(PASSWORD))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
        self.assertIn("uid=", mail.outbox[0].body)
        self.assertIn("token=", mail.outbox[0].body)

    def test_response_never_leaks_password(self):
        r = self.c.post(SIGNUP, signup_payload(), format="json")
        self.assertNotIn(PASSWORD, r.content.decode())

   

    def test_password_mismatch(self):
        r = self.c.post(SIGNUP, signup_payload(confirm_password="Different#123"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("confirm_password", r.json()["errors"])

    def test_weak_passwords_rejected(self):
        for pw in ["short1!", "12345678", "password", "11111111111"]:
            with self.subTest(pw=pw):
                r = self.c.post(SIGNUP, signup_payload(password=pw, confirm_password=pw), format="json")
                self.assertEqual(r.status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    def test_missing_fields(self):
        for field in ["full_name", "email", "password", "confirm_password"]:
            with self.subTest(field=field):
                p = signup_payload()
                p.pop(field)
                r = self.c.post(SIGNUP, p, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertIn(field, r.json()["errors"])

    def test_invalid_email(self):
        for bad in ["not-an-email", "a@", "@b.com", "a b@c.com"]:
            with self.subTest(bad=bad):
                r = self.c.post(SIGNUP, signup_payload(email=bad), format="json")
                self.assertEqual(r.status_code, 400)

    def test_mass_assignment_ignored(self):
        self.c.post(SIGNUP, signup_payload(is_superuser=True, is_active=True,
                                           email_verified_at="2020-01-01T00:00:00Z"), format="json")
        u = User.objects.get()
        self.assertFalse(u.is_superuser)
        self.assertFalse(u.is_active)
        self.assertIsNone(u.email_verified_at)

    def test_empty_body_and_wrong_method(self):
        self.assertEqual(self.c.post(SIGNUP, {}, format="json").status_code, 400)
        self.assertEqual(self.c.get(SIGNUP).status_code, 405)


class VerifyEmailTests(TestCase):
    def setUp(self):
        self.c = api_client()
        self.user = make_user(active=False, verified=False)

    def test_verify_success(self):
        uid, token = uid_token(self.user)
        r = self.c.post(VERIFY, {"uid": uid, "token": token}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIsNotNone(self.user.email_verified_at)

    def test_verify_twice_rejected(self):
        uid, token = uid_token(self.user)
        self.c.post(VERIFY, {"uid": uid, "token": token}, format="json")
        r = self.c.post(VERIFY, {"uid": uid, "token": token}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_bad_token(self):
        uid, _ = uid_token(self.user)
        r = self.c.post(VERIFY, {"uid": uid, "token": "bad-token"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_bad_uid(self):
        _, token = uid_token(self.user)
        for uid in ["!!!", "", "MTIzNDU2Nzg5MA", urlsafe_base64_encode(force_bytes(99999))]:
            with self.subTest(uid=uid):
                r = self.c.post(VERIFY, {"uid": uid, "token": token}, format="json")
                self.assertEqual(r.status_code, 400)

    def test_token_of_another_user_rejected(self):
        other = make_user(active=False, verified=False)
        uid, _ = uid_token(self.user)
        _, other_token = uid_token(other)
        r = self.c.post(VERIFY, {"uid": uid, "token": other_token}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_missing_fields(self):
        self.assertEqual(self.c.post(VERIFY, {}, format="json").status_code, 400)


class LoginTests(TestCase):
    def setUp(self):
        self.c = api_client()
        self.user = make_user("admin@example.com")

    def login(self, email="admin@example.com", password=PASSWORD):
        return self.c.post(LOGIN, {"email": email, "password": password}, format="json")

    def test_login_success_returns_tokens_with_claims(self):
        r = self.login()
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        claims = AccessToken(data["access"])
        self.assertEqual(claims["email"], "admin@example.com")
        self.assertEqual(claims["full_name"], self.user.full_name)
        self.assertNotIn("password", claims.payload)

    def test_login_updates_last_login(self):
        self.login()
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)

    def test_wrong_password_and_unknown_email_same_error(self):
        a = self.login(password="Wrong#Pass123")
        b = self.login(email="nobody@example.com")
        self.assertEqual(a.status_code, 400)
        self.assertEqual(b.status_code, 400)
        self.assertEqual(a.json()["errors"], b.json()["errors"])

    def test_missing_fields(self):
        self.assertEqual(self.c.post(LOGIN, {"email": "admin@example.com"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(LOGIN, {"password": PASSWORD}, format="json").status_code, 400)
        self.assertEqual(self.c.post(LOGIN, {}, format="json").status_code, 400)

    def test_inactive_unverified_and_non_staff_cannot_login(self):
        make_user("inactive@example.com", active=False)
        make_user("unverified@example.com", verified=False)
        make_user("nonstaff@example.com", staff=False)
        for email in ["inactive@example.com", "unverified@example.com", "nonstaff@example.com"]:
            with self.subTest(email=email):
                r = self.login(email=email)
                self.assertEqual(r.status_code, 400)
                self.assertNotIn("access", r.json())

    def test_email_lookup_is_case_sensitive_documented_behavior(self):
        """Currently 'ADMIN@example.com' != 'admin@example.com'. Locks the behavior in."""
        r = self.login(email="ADMIN@example.com")
        self.assertEqual(r.status_code, 400)

    def test_sql_injection_attempts_fail_cleanly(self):
        for payload in ["' OR '1'='1", "admin@example.com' --", "x'; DROP TABLE users; --"]:
            with self.subTest(payload=payload):
                self.assertEqual(self.login(email=payload, password=payload).status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_failed_attempts_counter_and_lockout(self):
        for i in range(1, 5):
            self.assertEqual(self.login(password="bad").status_code, 400)
            self.user.refresh_from_db()
            self.assertEqual(self.user.failed_login_attempts, i)
            self.assertFalse(self.user.is_locked())
        self.login(password="bad")  # 5th
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_locked())

    def test_correct_password_rejected_while_locked(self):
        self.user.locked_until = timezone.now() + timedelta(minutes=10)
        self.user.failed_login_attempts = 5
        self.user.save()
        r = self.login()
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("access", r.json())
        self.assertIn("locked", str(r.json()["errors"]).lower())

    def test_lock_expires_and_success_resets_counters(self):
        self.user.locked_until = timezone.now() - timedelta(minutes=1)
        self.user.failed_login_attempts = 5
        self.user.save()
        self.assertEqual(self.login().status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)
        self.assertIsNone(self.user.locked_until)

    def test_success_resets_partial_failures(self):
        self.login(password="bad")
        self.login(password="bad")
        self.assertEqual(self.login().status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)

    def test_wrong_method(self):
        self.assertEqual(self.c.get(LOGIN).status_code, 405)


class RefreshAndLogoutTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.refresh = str(RefreshToken.for_user(self.user))

    def test_refresh_success(self):
        r = api_client().post(REFRESH, {"refresh": self.refresh}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        access = r.json()["data"]["access"]
        self.assertEqual(jwt_client_with(access).get("/api/auth/profile/").status_code, 200)

    def test_refresh_requires_token(self):
        self.assertEqual(api_client().post(REFRESH, {}, format="json").status_code, 400)

    def test_refresh_rejects_garbage_and_access_tokens(self):
        access = str(RefreshToken(self.refresh).access_token)
        for bad in ["garbage", "a.b.c", access]:
            with self.subTest(bad=bad[:15]):
                r = api_client().post(REFRESH, {"refresh": bad}, format="json")
                self.assertEqual(r.status_code, 401)

    def test_logout_blacklists_refresh_token(self):
        r = jwt_client(self.user).post(LOGOUT, {"refresh": self.refresh}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        again = api_client().post(REFRESH, {"refresh": self.refresh}, format="json")
        self.assertEqual(again.status_code, 401)

    def test_logout_twice_fails(self):
        c = jwt_client(self.user)
        c.post(LOGOUT, {"refresh": self.refresh}, format="json")
        self.assertEqual(c.post(LOGOUT, {"refresh": self.refresh}, format="json").status_code, 400)

    def test_logout_requires_auth_and_body(self):
        self.assertEqual(api_client().post(LOGOUT, {"refresh": self.refresh}, format="json").status_code, 401)
        self.assertEqual(jwt_client(self.user).post(LOGOUT, {}, format="json").status_code, 400)
        self.assertEqual(jwt_client(self.user).post(LOGOUT, {"refresh": "junk"}, format="json").status_code, 400)


def jwt_client_with(access):
    c = api_client()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return c


class ForgotPasswordTests(TestCase):
    def setUp(self):
        self.c = api_client()
        self.user = make_user("admin@example.com")

    def test_existing_user_gets_email(self):
        r = self.c.post(FORGOT, {"email": "admin@example.com"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset-password?uid=", mail.outbox[0].body)

    def test_unknown_email_same_response_no_email(self):
        known = self.c.post(FORGOT, {"email": "admin@example.com"}, format="json")
        mail.outbox.clear()
        unknown = self.c.post(FORGOT, {"email": "ghost@example.com"}, format="json")
        self.assertEqual(unknown.status_code, known.status_code)
        self.assertEqual(unknown.json(), known.json())
        self.assertEqual(len(mail.outbox), 0)

    def test_inactive_user_gets_no_email(self):
        make_user("off@example.com", active=False)
        self.c.post(FORGOT, {"email": "off@example.com"}, format="json")
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_or_missing_email(self):
        self.assertEqual(self.c.post(FORGOT, {"email": "nope"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(FORGOT, {}, format="json").status_code, 400)


class ResetPasswordTests(TestCase):
    NEW = "Brand#New-Pass-77"

    def setUp(self):
        self.c = api_client()
        self.user = make_user("admin@example.com")

    def payload(self, **over):
        uid, token = uid_token(self.user)
        p = {"uid": uid, "token": token, "new_password": self.NEW, "confirm_password": self.NEW}
        p.update(over)
        return p

    def test_reset_success_and_can_login(self):
        r = self.c.post(RESET, self.payload(), format="json")
        self.assertEqual(r.status_code, 200, r.content)
        login = self.c.post(LOGIN, {"email": "admin@example.com", "password": self.NEW}, format="json")
        self.assertEqual(login.status_code, 200)
        old = self.c.post(LOGIN, {"email": "admin@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(old.status_code, 400)

    def test_reset_clears_lockout(self):
        self.user.failed_login_attempts = 5
        self.user.locked_until = timezone.now() + timedelta(minutes=10)
        self.user.save()
        self.c.post(RESET, self.payload(), format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)
        self.assertIsNone(self.user.locked_until)

    def test_token_is_single_use(self):
        p = self.payload()
        self.assertEqual(self.c.post(RESET, p, format="json").status_code, 200)
        self.assertEqual(self.c.post(RESET, {**p, "new_password": "Another#Pass-99",
                                             "confirm_password": "Another#Pass-99"}, format="json").status_code, 400)

    def test_invalid_inputs(self):
        cases = {
            "mismatch": self.payload(confirm_password="Nope#12345678"),
            "weak": self.payload(new_password="12345678", confirm_password="12345678"),
            "bad token": self.payload(token="bad"),
            "bad uid": self.payload(uid="zzz"),
        }
        for name, p in cases.items():
            with self.subTest(name):
                self.assertEqual(self.c.post(RESET, p, format="json").status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_missing_fields(self):
        self.assertEqual(self.c.post(RESET, {}, format="json").status_code, 400)


class RefreshTokenRevocationRiskTests(TestCase):
    """RISK: after a password reset, tokens issued before it should stop working."""

    def test_old_refresh_token_dies_after_password_reset(self):
        user = make_user("admin@example.com")
        old_refresh = str(RefreshToken.for_user(user))
        uid, token = uid_token(user)
        api_client().post(RESET, {"uid": uid, "token": token, "new_password": "Brand#New-Pass-77",
                                  "confirm_password": "Brand#New-Pass-77"}, format="json")
        r = api_client().post(REFRESH, {"refresh": old_refresh}, format="json")
        self.assertEqual(r.status_code, 401, "old refresh token still works after password reset")
