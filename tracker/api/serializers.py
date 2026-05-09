from rest_framework import serializers
from django.contrib.auth.models import User

from tracker.models import AnalysisSession, Exercise, Plan, PlanExercise, SessionLog
from tracker.services.roles import is_physio


class ExerciseSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Exercise
        fields = [
            "id",
            "name",
            "description",
            "body_area",
            "difficulty",
            "image_url",
            "video_url",
        ]

    def get_image_url(self, obj):
        request = self.context.get("request")
        if not obj.image:
            return None
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class PlanExerciseSerializer(serializers.ModelSerializer):
    exercise = ExerciseSerializer(read_only=True)

    class Meta:
        model = PlanExercise
        fields = ["id", "plan", "exercise", "sets", "reps", "order"]


class PlanSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source="user.username", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    prescriptions = PlanExerciseSerializer(source="plan_exercises", many=True, read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "description",
            "duration_weeks",
            "requires_analysis",
            "created_at",
            "client_username",
            "created_by_username",
            "prescriptions",
        ]


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

        if is_physio(user):
            raise serializers.ValidationError("Physiotherapists cannot create client progress logs.")

        if plan.user_id != user.id:
            raise serializers.ValidationError("You can only log progress against your own plan.")

        return plan

    def validate_pain_level(self, value):
        if value < 1 or value > 10:
            raise serializers.ValidationError("Pain level must be between 1 and 10.")
        return value

    def create(self, validated_data):
        return SessionLog.objects.create(user=self.context["request"].user, **validated_data)


class AnalysisSessionSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source="client.username", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

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
            "physio_feedback_draft",
            "physio_feedback",
            "feedback_shared",
            "feedback_at",
        ]


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    role = serializers.SerializerMethodField()

    def get_role(self, user):
        from tracker.services.roles import is_physio

        return "physio" if is_physio(user) else "client"


class UserUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        user = self.context["request"].user
        email_exists = User.objects.exclude(pk=user.pk).filter(email__iexact=value).exists()

        if email_exists:
            raise serializers.ValidationError("This email address is already in use.")

        return value

    def update(self, instance, validated_data):
        instance.email = validated_data["email"]
        instance.save(update_fields=["email"])
        return instance
