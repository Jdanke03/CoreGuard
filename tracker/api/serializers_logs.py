from rest_framework import serializers

from tracker.models import SessionLog


class SessionLogSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source="user.username", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = SessionLog
        fields = [
            "id",
            "plan",
            "plan_name",
            "client_username",
            "date",
            "pain_level",
            "notes",
        ]


class SessionLogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionLog
        fields = ["id", "plan", "date", "pain_level", "notes"]
        read_only_fields = ["id", "date"]

    def validate_plan(self, plan):
        user = self.context["request"].user

        if plan.user_id != user.id:
            raise serializers.ValidationError("You can only log progress against your own plan.")

        return plan

    def validate_pain_level(self, value):
        if value < 1 or value > 10:
            raise serializers.ValidationError("Pain level must be between 1 and 10.")
        return value

    def create(self, validated_data):
        return SessionLog.objects.create(user=self.context["request"].user, **validated_data)
