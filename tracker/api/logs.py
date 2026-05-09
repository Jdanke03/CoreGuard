from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from tracker.api.permissions import IsClient
from tracker.api.serializers import SessionLogCreateSerializer, SessionLogSerializer
from tracker.models import SessionLog
from tracker.services.roles import is_physio


class SessionLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["plan", "pain_level", "date"]
    search_fields = ["notes", "plan__name", "user__username"]
    ordering_fields = ["date", "pain_level", "id"]
    ordering = ["-date", "-id"]

    def get_permissions(self):
        if self.action == "create":
            return [IsClient()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return SessionLogCreateSerializer
        return SessionLogSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SessionLog.objects.none()

        user = self.request.user
        queryset = SessionLog.objects.select_related("user", "plan", "plan__created_by")
        if is_physio(user):
            return queryset.filter(plan__created_by=user)
        return queryset.filter(user=user)
