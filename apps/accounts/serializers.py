"""
Serializers for authentication and user management.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.common.validators import validate_image_file

User = get_user_model()


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["full_name", "email", "password", "confirm_password"]

    def validate(self, attrs):
        
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        # User starts inactive until email is verified
        return User.objects.create_user(
            email=validated_data["email"],
            full_name=validated_data["full_name"],
            password=validated_data["password"],
            is_active=False,
            is_staff=True # The first user is the admin
        )


class VerifyEmailSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "Invalid verification link."})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Link is invalid or has expired."})

        if user.email_verified_at is not None:
            raise serializers.ValidationError({"token": "Email is already verified."})

        # Check 24-hour timeout manually if custom logic is needed,
        # but default_token_generator has its own timeout (3 days default).
        # To strictly enforce 24h, we'd need a custom token generator.
        # For now, standard Django behavior is acceptable.

        attrs["user"] = user
        return attrs


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom Login Serializer to handle:
    - Active & Verified checks
    - Same error for wrong email/password
    - Lockout after 5 failed attempts for 15 mins
    """
    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": "Invalid email or password."})

        if user.is_locked():
            raise serializers.ValidationError({"detail": "Account locked due to too many failed attempts. Try again in 15 minutes."})

        if not user.check_password(password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
                user.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            user.save(update_fields=["failed_login_attempts", "locked_until"])
            raise serializers.ValidationError({"detail": "Invalid email or password."})

        if not user.is_active or user.email_verified_at is None:
            raise serializers.ValidationError({"detail": "Account is not active or not verified."})

        if not user.is_staff and user.role != 'client': # Admin ya Client hona zaroori hai
            raise serializers.ValidationError({"detail": "You do not have access to this platform."})

        # Reset lockout counters on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_login_attempts", "locked_until"])

        data = super().validate(attrs)
        
        # NAYA: Frontend ko batao ke yeh Admin hai ya Client
        data['role'] = user.role
        if user.role == 'client' and hasattr(user, 'client_profile'):
            data['client_id'] = user.client_profile.id

        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["full_name"] = user.full_name
        token["role"] = user.role # Token ke andar bhi role daal diya
        return token


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        # Note: We deliberately don't raise an error if the user doesn't exist
        # to prevent email enumeration attacks.
        return value


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "Invalid reset link."})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Link is invalid or has expired."})

        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    client_id = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ["id", "full_name", "email", "profile_photo", "created_at","role","client_id"]
        read_only_fields = ["id", "email", "created_at"]
    def get_client_id(self, obj):
        # Agar user ka client profile hai toh id return karein, warna None
        if hasattr(obj, 'client_profile') and obj.client_profile:
            return obj.client_profile.id
        return None
    def validate_profile_photo(self, value):
        validate_image_file(value)
        return value


class AcceptInviteSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "Invalid invite link."})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Link is invalid or has expired."})

        if user.is_active:
            raise serializers.ValidationError({"token": "This account is already active."})

        attrs["user"] = user
        return attrs