"""
Serializers for PlatformSettings and Template.
"""
from rest_framework import serializers
from .models import Template, PlatformSettings
from apps.common.validators import validate_image_file


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = "__all__"

    def validate_preview_image(self, value):
        if value: validate_image_file(value)
        return value

    def validate_key(self, value):
        return value.strip().lower()


class PlatformSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSettings
        fields = "__all__"

    def validate_logo(self, value):
        if value: validate_image_file(value)
        return value

    def validate(self, attrs):
        if attrs.get("email_notifications_enabled") and not attrs.get("notification_email"):
            attrs["notification_email"] = attrs.get("admin_contact_email")
        return attrs