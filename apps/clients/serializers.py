"""
Serializers for the Client model.
"""
from rest_framework import serializers
from .models import Client
from apps.common.validators import validate_image_file, validate_phone_number


def is_reusable_orphan_user(user):
    """
    True sirf us client-user ke liye jis ka koi LIVE (non-deleted) client nahi hai,
    jaise soft-deleted client ka bacha hua account. Admin/staff kabhi reuse nahi hota.
    """
    if user.is_staff or user.is_superuser:
        return False
    return not Client.objects.filter(user=user).exists()  # default manager = live clients only


class ClientSerializer(serializers.ModelSerializer):
    portfolio_status = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Client
        fields = [
            "id", "full_name", "email", "profile_photo",
            "profession", "phone", "organization", "location",
            "portfolio_status", "created_at", "portal_status","updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_portfolio_status(self, obj):
        """
        Derived portfolio status; soft-deleted portfolios are ignored.
        The list view annotates `portfolio_status_annot` (one subquery for all rows);
        for objects without it (e.g. a client just created) we do a single lookup.
        """
        if hasattr(obj, "portfolio_status_annot"):
            status = obj.portfolio_status_annot
        else:
            from apps.portfolios.models import Portfolio  # local import avoids circular import
            status = Portfolio.objects.filter(client=obj).values_list("status", flat=True).first()
        return status or "No Portfolio"

    def validate_profile_photo(self, value):
        if value:
            validate_image_file(value)
        return value

    def validate_phone(self, value):
        if value:
            validate_phone_number(value)
        return value

    def validate_email(self, value):
        """
        - Lowercase + trim.
        - Case-insensitive duplicate check among ACTIVE clients only;
          the email of a soft-deleted client can be used again.
        """
        value = value.strip().lower()
        existing = Client.objects.filter(email__iexact=value)  # default manager = active only
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("A client with this email already exists.")

        # Is email par pehle se koi User account to nahi? (admin / kisi aur client ka)
        # Sirf "orphan" client-user (purane deleted client ka) dobara use ho sakta hai.
        from django.contrib.auth import get_user_model
        User = get_user_model()
        users = User.objects.filter(email__iexact=value)
        msg = ("A user account with this email already exists in the system. "
               "Please use a different email.")
        if self.instance and self.instance.user_id:
            # Is client ka apna user hai: email badalne par user.email bhi badlegi,
            # is liye kisi DOOSRE user ke paas yeh email nahi honi chahiye.
            if users.exclude(pk=self.instance.user_id).exists():
                raise serializers.ValidationError(msg)
        else:
            for u in users:
                if not is_reusable_orphan_user(u):
                    raise serializers.ValidationError(msg)
        return value

    def update(self, instance, validated_data):
        """Client ki email badle to linked user ki email bhi sync ho."""
        from django.db import transaction
        new_email = validated_data.get("email")
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if new_email and instance.user_id and instance.user.email != new_email:
                user = instance.user
                user.email = new_email
                user.save(update_fields=["email"])
        return instance
