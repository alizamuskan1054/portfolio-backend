from django.urls import path
from .views import (
    SignupView, VerifyEmailView, LoginView, RefreshTokenView, 
    LogoutView, ForgotPasswordView, ResetPasswordView,  AcceptInviteView,
    ChangePasswordView, ProfileView, ResendVerificationView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="auth-signup"),
    path("verify-email/", VerifyEmailView.as_view(), name="auth-verify-email"),
    path("login/", LoginView.as_view(), name="auth-login"),
     path("resend-verification/", ResendVerificationView.as_view(), name="auth-resend-verification"),
    path("refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="auth-reset-password"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("profile/", ProfileView.as_view(), name="auth-profile"),
    path("accept-invite/", AcceptInviteView.as_view(), name="auth-accept-invite"),

]