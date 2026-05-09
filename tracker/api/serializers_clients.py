from django.contrib.auth.models import User
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from tracker.models import AnalysisSession, Plan


class ClientSummarySerializer(serializers.ModelSerializer):
    active_plans = serializers.SerializerMethodField()
    awaiting_review = serializers.SerializerMethodField()
    feedback_sent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "active_plans", "awaiting_review", "feedback_sent"]

    def _plans_for_client(self, client):
        return Plan.objects.filter(created_by=self.context["request"].user, user=client)

    @extend_schema_field(OpenApiTypes.INT)
    def get_active_plans(self, client):
        return self._plans_for_client(client).count()

    @extend_schema_field(OpenApiTypes.INT)
    def get_awaiting_review(self, client):
        return AnalysisSession.objects.filter(
            plan__created_by=self.context["request"].user,
            client=client,
            feedback_shared=False,
        ).count()

    @extend_schema_field(OpenApiTypes.INT)
    def get_feedback_sent(self, client):
        return AnalysisSession.objects.filter(
            plan__created_by=self.context["request"].user,
            client=client,
            feedback_shared=True,
        ).count()
