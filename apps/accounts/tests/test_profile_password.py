"""Profile and change-password endpoints, plus JWT/token security."""
from datetime import timedelta

from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.common.factories import PASSWORD, api_client, jwt_client, make_image, make_user
from django.core.files.uploadedfile import SimpleUploadedFile

PROFILE = "/api/auth/profile/"
CHANGE = "/api/auth/change-password/"
LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/refresh/"
NEW_PW = "Fresh#Pass-2025-x"


class ProfileTests(TestCase):
    def setUp(self):
        self.user = make_user("me@example.com", full_name="Original Name")
        self.c = jwt_client(self.user)

    def test_get_profile(self):
        r = self.c.get(PROFILE)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["email"], "me@example.com")
        self.assertEqual(r.json()["full_name"], "Original Name")

    def test_profile_never_exposes_sensitive_fields(self):
        keys = set(self.c.get(PROFILE).json())
        for forbidden in ["password", "is_staff", "is_superuser", "locked_until", "failed_login_attempts"]:
            self.assertNotIn(forbidden, keys)

    def test_requires_auth(self):
        self.assertEqual(api_client().get(PROFILE).status_code, 401)
        self.assertEqual(api_client().patch(PROFILE, {"full_name": "x"}, format="json").status_code, 401)

    def test_patch_full_name(self):
        r = self.c.patch(PROFILE, {"full_name": "New Name"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "New Name")

    def test_put_requires_full_name(self):
        self.assertEqual(self.c.put(PROFILE, {}, format="json").status_code, 400)

    def test_blank_full_name_rejected(self):
        self.assertEqual(self.c.patch(PROFILE, {"full_name": ""}, format="json").status_code, 400)

    def test_read_only_and_privileged_fields_ignored(self):
        self.c.patch(PROFILE, {"email": "hacker@example.com", "is_staff": False,
                               "is_superuser": True, "is_active": False}, format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "me@example.com")
        self.assertTrue(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.is_active)

    def test_upload_valid_photo(self):
        r = self.c.patch(PROFILE, {"profile_photo": make_image()}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile_photo.name.startswith("profiles/"))

    def test_upload_rejects_non_image(self):
        fake = SimpleUploadedFile("evil.png", b"<script>alert(1)</script>", content_type="image/png")
        self.assertEqual(self.c.patch(PROFILE, {"profile_photo": fake}, format="multipart").status_code, 400)

    def test_upload_rejects_unsupported_format(self):
        self.assertEqual(
            self.c.patch(PROFILE, {"profile_photo": make_image("a.bmp", "BMP")}, format="multipart").status_code, 400)

    def test_upload_rejects_oversized(self):
        big = make_image(pad=5 * 1024 * 1024 + 1)
        self.assertEqual(self.c.patch(PROFILE, {"profile_photo": big}, format="multipart").status_code, 400)

    def test_xss_in_name_is_stored_verbatim_and_returned_as_json(self):
        payload = "<img src=x onerror=alert(1)>"
        r = self.c.patch(PROFILE, {"full_name": payload}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("application/json"))


class ChangePasswordTests(TestCase):
    def setUp(self):
        self.user = make_user("me@example.com")
        self.c = jwt_client(self.user)

    def payload(self, **over):
        p = {"old_password": PASSWORD, "new_password": NEW_PW, "confirm_password": NEW_PW}
        p.update(over)
        return p

    def test_success(self):
        r = self.c.post(CHANGE, self.payload(), format="json")
        self.assertEqual(r.status_code, 200, r.content)
        ok = api_client().post(LOGIN, {"email": "me@example.com", "password": NEW_PW}, format="json")
        self.assertEqual(ok.status_code, 200)
        old = api_client().post(LOGIN, {"email": "me@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(old.status_code, 400)

    def test_wrong_old_password(self):
        r = self.c.post(CHANGE, self.payload(old_password="Wrong#Pass-123"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("old_password", r.json()["errors"])

    def test_mismatch_and_weak(self):
        self.assertEqual(self.c.post(CHANGE, self.payload(confirm_password="Other#Pass-1234"), format="json").status_code, 400)
        self.assertEqual(self.c.post(CHANGE, self.payload(new_password="12345678", confirm_password="12345678"), format="json").status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_missing_fields(self):
        self.assertEqual(self.c.post(CHANGE, {}, format="json").status_code, 400)

    def test_requires_auth(self):
        self.assertEqual(api_client().post(CHANGE, self.payload(), format="json").status_code, 401)

    def test_old_refresh_token_dies_after_password_change_RISK(self):
        """RISK: 'Please log in again' - old refresh tokens should be revoked."""
        refresh = str(RefreshToken.for_user(self.user))
        self.c.post(CHANGE, self.payload(), format="json")
        r = api_client().post(REFRESH, {"refresh": refresh}, format="json")
        self.assertEqual(r.status_code, 401, "old refresh token still works after password change")


class JwtSecurityTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def bearer(self, token):
        c = api_client()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return c

    def test_expired_access_token_rejected(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=-timedelta(seconds=5))
        self.assertEqual(self.bearer(str(token)).get(PROFILE).status_code, 401)

    def test_tampered_token_rejected(self):
        token = str(AccessToken.for_user(self.user))
        head, payload, sig = token.split(".")
        self.assertEqual(self.bearer(f"{head}.{payload}.{sig[:-3]}abc").get(PROFILE).status_code, 401)

    def test_refresh_token_cannot_be_used_as_access(self):
        self.assertEqual(self.bearer(str(RefreshToken.for_user(self.user))).get(PROFILE).status_code, 401)

    def test_garbage_and_wrong_scheme(self):
        self.assertEqual(self.bearer("garbage").get(PROFILE).status_code, 401)
        c = api_client()
        c.credentials(HTTP_AUTHORIZATION=f"Token {AccessToken.for_user(self.user)}")
        self.assertEqual(c.get(PROFILE).status_code, 401)
        c.credentials(HTTP_AUTHORIZATION="Bearer")
        self.assertEqual(c.get(PROFILE).status_code, 401)

    def test_deactivated_user_token_rejected(self):
        token = str(AccessToken.for_user(self.user))
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.bearer(token).get(PROFILE).status_code, 401)

    def test_deleted_user_token_rejected(self):
        token = str(AccessToken.for_user(self.user))
        self.user.delete()
        self.assertEqual(self.bearer(token).get(PROFILE).status_code, 401)

    def test_unsigned_alg_none_token_rejected(self):
        import base64, json
        b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
        forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'user_id': self.user.pk, 'token_type': 'access', 'exp': 9999999999, 'jti': 'x'})}."
        self.assertEqual(self.bearer(forged).get(PROFILE).status_code, 401)

    def test_access_token_lifetime_is_short(self):
        from django.conf import settings
        self.assertLessEqual(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"], timedelta(minutes=30))
