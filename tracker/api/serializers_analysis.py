import json

from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from tracker.models import AnalysisSession


class AnalysisSessionSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source="client.username", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    summary_metrics = serializers.SerializerMethodField()

    class Meta:
        model = AnalysisSession
        fields = [
            "id",
            "client_username",
            "plan",
            "plan_name",
            "exercise_name",
            "started_at",
            "ended_at",
            "total_frames",
            "flagged_frames",
            "summary_json",
            "summary_metrics",
            "physio_feedback_draft",
            "physio_feedback",
            "feedback_shared",
            "feedback_at",
        ]

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_summary_metrics(self, obj):
        if not obj.summary_json:
            return {
                "rules": {},
                "angles": {},
                "total_frames": obj.total_frames,
                "flagged_frames": obj.flagged_frames,
            }

        try:
            summary = json.loads(obj.summary_json)
        except (TypeError, ValueError):
            return {
                "rules": {},
                "angles": {},
                "total_frames": obj.total_frames,
                "flagged_frames": obj.flagged_frames,
            }

        return {
            "rules": summary.get("rules", {}),
            "angles": summary.get("angles", {}),
            "total_frames": summary.get("total_frames", obj.total_frames),
            "flagged_frames": summary.get("flagged_frames", obj.flagged_frames),
        }


class FeedbackSendSerializer(serializers.Serializer):
    physio_feedback = serializers.CharField(trim_whitespace=True)

    def validate_physio_feedback(self, value):
        if not value.strip():
            raise serializers.ValidationError("Feedback cannot be empty.")
        return value
