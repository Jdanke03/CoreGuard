from django.contrib.auth.models import User

from tracker.api.base import AuthenticatedReadOnlyViewSet
from tracker.api.serializers import ClientSummarySerializer
from tracker.models import Plan
from tracker.services.roles import is_physio


class ClientViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = ClientSummarySerializer

    def get_queryset(self):
        user = self.request.user
        if not is_physio(user):
            return User.objects.none()
        client_ids = Plan.objects.filter(created_by=user).values_list("user_id", flat=True).distinct()
        return User.objects.filter(id__in=client_ids).order_by("username")
