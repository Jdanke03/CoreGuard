from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

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


class ExerciseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = [
            "id",
            "name",
            "description",
            "body_area",
            "difficulty",
            "image",
            "video_url",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if not is_physio(self.context["request"].user):
            raise serializers.ValidationError("Only physiotherapists can create exercises.")
        return attrs


class PlanExerciseSerializer(serializers.ModelSerializer):
    exercise = ExerciseSerializer(read_only=True)

    class Meta:
        model = PlanExercise
        fields = ["id", "plan", "exercise", "sets", "reps", "order"]


class PlanPrescriptionCreateSerializer(serializers.Serializer):
    exercise = serializers.PrimaryKeyRelatedField(queryset=Exercise.objects.all())
    sets = serializers.IntegerField(min_value=1, max_value=20, default=3)
    reps = serializers.IntegerField(min_value=1, max_value=100, default=10)


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


class PlanCreateSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    prescriptions = PlanPrescriptionCreateSerializer(many=True, write_only=True)

    class Meta:
        model = Plan
        fields = [
            "id",
            "user",
            "name",
            "description",
            "duration_weeks",
            "requires_analysis",
            "prescriptions",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        request_user = self.context["request"].user
        prescriptions = attrs.get("prescriptions", [])

        if not is_physio(request_user):
            raise serializers.ValidationError("Only physiotherapists can create plans.")

        if is_physio(attrs["user"]):
            raise serializers.ValidationError("Plans must be assigned to a client account.")

        if not 1 <= attrs.get("duration_weeks", 6) <= 12:
            raise serializers.ValidationError({"duration_weeks": "Duration must be between 1 and 12 weeks."})

        if not prescriptions:
            raise serializers.ValidationError({"prescriptions": "At least one exercise prescription is required."})

        exercise_ids = [item["exercise"].id for item in prescriptions]
        if len(exercise_ids) != len(set(exercise_ids)):
            raise serializers.ValidationError({"prescriptions": "Each exercise can only appear once per plan."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        prescriptions = validated_data.pop("prescriptions")
        plan = Plan.objects.create(
            created_by=self.context["request"].user,
            **validated_data,
        )
        exercises = [item["exercise"] for item in prescriptions]
        plan.exercises.set(exercises)

        PlanExercise.objects.bulk_create([
            PlanExercise(
                plan=plan,
                exercise=item["exercise"],
                sets=item["sets"],
                reps=item["reps"],
                order=index,
            )
            for index, item in enumerate(prescriptions)
        ])
        return plan


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

    def get_summary_metrics(self, obj):
        import json

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


class ClientSummarySerializer(serializers.ModelSerializer):
    active_plans = serializers.SerializerMethodField()
    awaiting_review = serializers.SerializerMethodField()
    feedback_sent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "active_plans", "awaiting_review", "feedback_sent"]

    def _plans_for_client(self, client):
        return Plan.objects.filter(created_by=self.context["request"].user, user=client)

    def get_active_plans(self, client):
        return self._plans_for_client(client).count()

    def get_awaiting_review(self, client):
        return AnalysisSession.objects.filter(
            plan__created_by=self.context["request"].user,
            client=client,
            feedback_shared=False,
        ).count()

    def get_feedback_sent(self, client):
        return AnalysisSession.objects.filter(
            plan__created_by=self.context["request"].user,
            client=client,
            feedback_shared=True,
        ).count()


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
