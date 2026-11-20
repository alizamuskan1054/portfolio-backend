"""
API Views for Authentication using DRF Generic Views & ViewSets.
"""
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from rest_framework import status, generics, mixins, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from apps.common.responses import success_response, created_response, error_response
from .serializers import (
    SignupSerializer, VerifyEmailSerializer, CustomTokenObtainPairSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer, ChangePasswordSerializer,
    UserProfileSerializer
)
from .emails import send_verification_email, send_password_reset_email

User = get_user_model()

# ==========================================
# 1. SIGNUP & VERIFICATION (Custom logic needed)
# ==========================================
class SignupView(generics.CreateAPIView):
    """
    Standard CreateAPIView for Signup. 
    Handles validation and creation automatically.
    """
    permission_classes = [AllowAny]
    serializer_class = SignupSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email(user)
        return created_response(message="Signup successful. Please check your email to verify your account.")


class VerifyEmailView(APIView):
    """Custom logic, so APIView is appropriate here."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            user.email_verified_at = timezone.now()
            user.is_active = True
            user.save(update_fields=["email_verified_at", "is_active"])
            return success_response(message="Email verified successfully. You can now log in.")
        return error_response(errors=serializer.errors)


# ==========================================
# 2. AUTHENTICATION (JWT)
# ==========================================
class LoginView(TokenObtainPairView):
    """Inherits from SimpleJWT's built-in view."""
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return error_response(message="Refresh token is required.")
        
        try:
            token = RefreshToken(refresh_token)
            return success_response(data={"access": str(token.access_token)})
        except TokenError:
            return error_response(message="Invalid or expired refresh token.", status_code=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return error_response(message="Refresh token is required.")
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            return success_response(message="Logged out successfully.")
        except TokenError:
            return error_response(message="Invalid token.", status_code=status.HTTP_400_BAD_REQUEST)


# ==========================================
# 3. PASSWORD MANAGEMENT (Custom logic needed)
# ==========================================
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            user = User.objects.filter(email=email).first()
            
            if user and user.is_active:
                send_password_reset_email(user)
            
            return success_response(message="If the email exists, a password reset link has been sent.")
        return error_response(errors=serializer.errors)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            new_password = serializer.validated_data["new_password"]
            
            user.set_password(new_password)
            user.failed_login_attempts = 0
            user.locked_until = None
            user.save()
            
            return success_response(message="Password reset successful. You can now log in.")
        return error_response(errors=serializer.errors)


# ==========================================
# 4. PROFILE & CHANGE PASSWORD (ViewSets & Generic Views)
# ==========================================
class ProfileView(generics.RetrieveUpdateAPIView):
    """
    Uses RetrieveUpdateAPIView. 
    Handles GET (retrieve) and PATCH/PUT (update) automatically.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        # Always return the currently logged-in user
        return self.request.user

    def update(self, request, *args, **kwargs):
        # Override to use our custom response wrapper
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(data=serializer.data, message="Profile updated successfully.")


class ChangePasswordView(generics.GenericAPIView):
    """
    Uses GenericAPIView. 
    Serializers handle all validation, view just saves the password.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        
        return success_response(message="Password changed successfully. Please log in again.")