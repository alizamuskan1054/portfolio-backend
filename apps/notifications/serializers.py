from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    # Sirf id (portfolio soft-delete ho to bhi koi extra query / error nahi)
    portfolio = serializers.IntegerField(source="portfolio_id", read_only=True)
    # `message` aur `body` dono same text hain (frontend jo bhi parhe)
    message = serializers.CharField(source="body", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "message", "is_read", "created_at",
                  "portfolio", "portfolio_title"]
        read_only_fields = fields
