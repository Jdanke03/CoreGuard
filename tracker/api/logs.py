from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

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

    def get_serializer_class(self):
        if self.action == "create":
            return SessionLogCreateSerializer
        return SessionLogSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = SessionLog.objects.select_related("user", "plan", "plan__created_by")
        if is_physio(user):
            return queryset.filter(plan__created_by=user).order_by("-date")
        return queryset.filter(user=user).order_by("-date")
