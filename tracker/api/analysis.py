from rest_framework.decorators import action
from rest_framework.response import Response

from tracker.api.base import AuthenticatedReadOnlyViewSet
from tracker.api.permissions import IsAssignedPhysioForAnalysis
from tracker.api.serializers import AnalysisSessionSerializer, FeedbackSendSerializer
from tracker.models import AnalysisSession
from tracker.services.roles import is_physio
from tracker.tasks.feedback import (
    generate_feedback_draft_task,
    send_feedback_email_task,
)


class AnalysisSessionViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = AnalysisSessionSerializer

    def get_permissions(self):
        if self.action in {"generate_draft", "send_feedback"}:
            return [IsAssignedPhysioForAnalysis()]
        return super().get_permissions()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AnalysisSession.objects.none()

        user = self.request.user
        queryset = AnalysisSession.objects.select_related("client", "plan", "plan__created_by")
        if is_physio(user):
            return queryset.filter(plan__created_by=user).order_by("-started_at")
        return queryset.filter(client=user).order_by("-started_at")

    def _get_physio_session(self):
        return self.get_object()

    @action(detail=True, methods=["post"], url_path="generate-draft")
    def generate_draft(self, request, pk=None):
        session = self._get_physio_session()
        result = generate_feedback_draft_task(session.id)
        data = AnalysisSessionSerializer(result.session, context={"request": request}).data
        data["draft_status"] = result.status
        return Response(data)

    @action(detail=True, methods=["post"], url_path="send-feedback")
    def send_feedback(self, request, pk=None):
        session = self._get_physio_session()
        serializer = FeedbackSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = send_feedback_email_task(
            session.id,
            serializer.validated_data["physio_feedback"],
        )

        data = AnalysisSessionSerializer(result.session, context={"request": request}).data
        data["email_delivery"] = result.email_status
        data["email_error"] = result.email_error
        return Response(data)
