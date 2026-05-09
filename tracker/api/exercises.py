from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

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

    def get_serializer_class(self):
        if self.action == "create":
            return ExerciseCreateSerializer
        return ExerciseSerializer
