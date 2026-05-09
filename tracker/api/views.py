from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from tracker.api.serializers import (
    AnalysisSessionSerializer,
    ExerciseSerializer,
    PlanExerciseSerializer,
    PlanSerializer,
    SessionLogSerializer,
)
from tracker.models import AnalysisSession, Exercise, Plan, PlanExercise, SessionLog
from tracker.services.roles import is_physio


class AuthenticatedReadOnlyViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]


class ExerciseViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = ExerciseSerializer
    queryset = Exercise.objects.order_by("name")


class PlanViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = PlanSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Plan.objects.prefetch_related("plan_exercises__exercise").select_related("user", "created_by")
        if is_physio(user):
            return queryset.filter(created_by=user).order_by("-created_at")
        return queryset.filter(user=user).order_by("-created_at")


class PlanExerciseViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = PlanExerciseSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = PlanExercise.objects.select_related("plan", "exercise", "plan__user", "plan__created_by")
        if is_physio(user):
            return queryset.filter(plan__created_by=user)
        return queryset.filter(plan__user=user)


class SessionLogViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = SessionLogSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = SessionLog.objects.select_related("user", "plan", "plan__created_by")
        if is_physio(user):
            return queryset.filter(plan__created_by=user).order_by("-date")
        return queryset.filter(user=user).order_by("-date")


class AnalysisSessionViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = AnalysisSessionSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = AnalysisSession.objects.select_related("client", "plan", "plan__created_by")
        if is_physio(user):
            return queryset.filter(plan__created_by=user).order_by("-started_at")
        return queryset.filter(client=user).order_by("-started_at")
