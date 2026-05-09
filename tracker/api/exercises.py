from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from tracker.api.permissions import IsPhysio
from tracker.api.serializers import ExerciseCreateSerializer, ExerciseSerializer
from tracker.models import Exercise


class ExerciseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    queryset = Exercise.objects.order_by("name")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["body_area", "difficulty"]
    search_fields = ["name", "description", "body_area"]
    ordering_fields = ["name", "body_area", "difficulty", "created_at"]
    ordering = ["name"]

    def get_permissions(self):
        if self.action == "create":
            return [IsPhysio()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return ExerciseCreateSerializer
        return ExerciseSerializer
