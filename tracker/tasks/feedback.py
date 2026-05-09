from dataclasses import dataclass

from django.utils import timezone

from tracker.models import AnalysisSession
from tracker.services.feedback import generate_ai_draft, send_feedback_email


DRAFT_STATUS_READY = "ready"
EMAIL_STATUS_SENT = "sent"
EMAIL_STATUS_FAILED = "failed"
EMAIL_STATUS_SKIPPED_NO_EMAIL = "skipped_no_email"


@dataclass(frozen=True)
class FeedbackDraftResult:
    session: AnalysisSession
    draft: str
    status: str = DRAFT_STATUS_READY


@dataclass(frozen=True)
class FeedbackDeliveryResult:
    session: AnalysisSession
    email_status: str
    email_error: str = ""


def generate_feedback_draft_task(session_id):
    session = AnalysisSession.objects.select_related("client", "plan").get(pk=session_id)
    draft = generate_ai_draft(session)
    session.physio_feedback_draft = draft
    if not session.physio_feedback:
        session.physio_feedback = draft
    session.save(update_fields=["physio_feedback_draft", "physio_feedback"])
    return FeedbackDraftResult(session=session, draft=draft)


def send_feedback_email_task(session_id, feedback_text):
    session = AnalysisSession.objects.select_related("client", "plan").get(pk=session_id)
    session.physio_feedback = feedback_text
    session.feedback_shared = True
    session.feedback_at = timezone.now()
    session.save(update_fields=["physio_feedback", "feedback_shared", "feedback_at"])

    if not session.client or not session.client.email:
        return FeedbackDeliveryResult(
            session=session,
            email_status=EMAIL_STATUS_SKIPPED_NO_EMAIL,
        )

    try:
        email_sent = send_feedback_email(session)
    except Exception as exc:
        return FeedbackDeliveryResult(
            session=session,
            email_status=EMAIL_STATUS_FAILED,
            email_error=str(exc),
        )

    return FeedbackDeliveryResult(
        session=session,
        email_status=EMAIL_STATUS_SENT if email_sent else EMAIL_STATUS_SKIPPED_NO_EMAIL,
    )
