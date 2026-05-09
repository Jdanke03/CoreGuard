from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from tracker.api.base import AuthenticatedReadOnlyViewSet
from tracker.api.serializers import PlanCreateSerializer, PlanExerciseSerializer, PlanSerializer
from tracker.models import Plan, PlanExercise
from tracker.services.roles import is_physio


class PlanViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return PlanCreateSerializer
        return PlanSerializer

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
