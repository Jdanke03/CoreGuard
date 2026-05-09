from django.contrib.auth.models import User
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from tracker.api.base import AuthenticatedReadOnlyViewSet
from tracker.api.permissions import IsPhysio
from tracker.api.serializers import ClientSummarySerializer
from tracker.models import Plan


class ClientViewSet(AuthenticatedReadOnlyViewSet):
    permission_classes = [IsPhysio]
    serializer_class = ClientSummarySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "email", "date_joined"]
    ordering = ["username"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()

        user = self.request.user
        client_ids = Plan.objects.filter(created_by=user).values_list("user_id", flat=True).distinct()
        return User.objects.filter(id__in=client_ids)
