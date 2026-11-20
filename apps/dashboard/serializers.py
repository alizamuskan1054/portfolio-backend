"""
Serializers for Dashboard endpoints.
"""
from rest_framework import serializers
from apps.portfolios.models import ActivityLog


class RecentActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True)
    
    class Meta:
        model = ActivityLog
        fields = [
            "id", "action", "actor_name", "client", 
            "portfolio", "description", "created_at"
        ]