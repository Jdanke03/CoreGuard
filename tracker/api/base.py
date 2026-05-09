from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet


class AuthenticatedReadOnlyViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
