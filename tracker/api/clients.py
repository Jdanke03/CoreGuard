from django.contrib.auth.models import User

from tracker.api.base import AuthenticatedReadOnlyViewSet
from tracker.api.permissions import IsPhysio
from tracker.api.serializers import ClientSummarySerializer
from tracker.models import Plan


class ClientViewSet(AuthenticatedReadOnlyViewSet):
    permission_classes = [IsPhysio]
    serializer_class = ClientSummarySerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()

        user = self.request.user
        client_ids = Plan.objects.filter(created_by=user).values_list("user_id", flat=True).distinct()
        return User.objects.filter(id__in=client_ids).order_by("username")
