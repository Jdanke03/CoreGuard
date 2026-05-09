from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from tracker.api.base import AuthenticatedReadOnlyViewSet
from tracker.api.permissions import IsAssignedPhysioForAnalysis
from tracker.api.serializers import AnalysisSessionSerializer, FeedbackSendSerializer
from tracker.models import AnalysisSession
from tracker.services.feedback import generate_ai_draft, send_feedback_email
from tracker.services.roles import is_physio


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
        draft = generate_ai_draft(session)
        session.physio_feedback_draft = draft
        if not session.physio_feedback:
            session.physio_feedback = draft
        session.save(update_fields=["physio_feedback_draft", "physio_feedback"])
        return Response(AnalysisSessionSerializer(session, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="send-feedback")
    def send_feedback(self, request, pk=None):
        session = self._get_physio_session()
        serializer = FeedbackSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session.physio_feedback = serializer.validated_data["physio_feedback"]
        session.feedback_shared = True
        session.feedback_at = timezone.now()
        session.save(update_fields=["physio_feedback", "feedback_shared", "feedback_at"])
        email_sent = send_feedback_email(session)

        data = AnalysisSessionSerializer(session, context={"request": request}).data
        data["email_sent"] = email_sent
        return Response(data)
