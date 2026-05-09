from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from tracker.api.base import AuthenticatedReadOnlyViewSet
from tracker.api.permissions import IsPhysio
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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["requires_analysis", "duration_weeks", "user"]
    search_fields = ["name", "description", "user__username"]
    ordering_fields = ["created_at", "duration_weeks", "name"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action == "create":
            return [IsPhysio()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return PlanCreateSerializer
        return PlanSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Plan.objects.none()

        user = self.request.user
        queryset = Plan.objects.prefetch_related("plan_exercises__exercise").select_related("user", "created_by")
        if is_physio(user):
            return queryset.filter(created_by=user)
        return queryset.filter(user=user)


class PlanExerciseViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = PlanExerciseSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["plan", "exercise"]
    ordering_fields = ["order", "sets", "reps"]
    ordering = ["order"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PlanExercise.objects.none()

        user = self.request.user
        queryset = PlanExercise.objects.select_related("plan", "exercise", "plan__user", "plan__created_by")
        if is_physio(user):
            return queryset.filter(plan__created_by=user)
        return queryset.filter(plan__user=user)
