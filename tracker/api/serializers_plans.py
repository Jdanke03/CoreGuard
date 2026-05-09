from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from tracker.api.serializers_exercises import ExerciseSerializer
from tracker.models import Exercise, Plan, PlanExercise
from tracker.services.roles import is_physio


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
        prescriptions = attrs.get("prescriptions", [])

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
