from dataclasses import dataclass

from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from tracker.api.serializers import AnalysisSessionSerializer, PlanSerializer
from tracker.models import AnalysisSession, Plan, SessionLog
from tracker.services.roles import is_physio


@dataclass
class ActionItem:
    action_type: str
    title: str
    description: str
    priority: str
    url: str
    object_type: str
    object_id: int | None = None

    def as_dict(self):
        return {
            "type": self.action_type,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "url": self.url,
            "object_type": self.object_type,
            "object_id": self.object_id,
        }


@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(["GET"])
def action_queue_view(request):
    if is_physio(request.user):
        return Response(build_physio_action_queue(request))
    return Response(build_client_action_queue(request))


def build_client_action_queue(request):
    user = request.user
    plans = (
        Plan.objects.filter(user=user)
        .prefetch_related("plan_exercises__exercise")
        .select_related("created_by")
        .order_by("-created_at")
    )
    sessions = AnalysisSession.objects.filter(client=user).select_related("plan").order_by("-started_at")
    logs = SessionLog.objects.filter(user=user).select_related("plan")

    latest_plan = plans.first()
    latest_feedback = sessions.filter(feedback_shared=True).first()
    latest_analysis = sessions.first()
    pending_feedback = sessions.filter(feedback_shared=False).count()

    actions = []
    if latest_feedback:
        actions.append(ActionItem(
            action_type="review_feedback",
            title="Review your latest feedback",
            description=f"Feedback is ready for your {latest_feedback.exercise_name} session.",
            priority="high",
            url=f"/analysis/summary/{latest_feedback.id}/",
            object_type="analysis_session",
            object_id=latest_feedback.id,
        ))

    if latest_plan and latest_plan.requires_analysis and not pending_feedback:
        actions.append(ActionItem(
            action_type="complete_live_analysis",
            title="Complete your live analysis",
            description=f"Your {latest_plan.name} plan includes a movement analysis check.",
            priority="medium",
            url="/analysis/start/",
            object_type="plan",
            object_id=latest_plan.id,
        ))

    if latest_plan:
        actions.append(ActionItem(
            action_type="log_progress",
            title="Log your rehab progress",
            description=f"Add a short progress note for {latest_plan.name}.",
            priority="medium" if logs.filter(plan=latest_plan).count() == 0 else "low",
            url="/logs/new/",
            object_type="plan",
            object_id=latest_plan.id,
        ))

    return {
        "role": "client",
        "actions": [action.as_dict() for action in actions[:5]],
        "latest_plan": PlanSerializer(latest_plan, context={"request": request}).data if latest_plan else None,
        "latest_analysis": AnalysisSessionSerializer(latest_analysis, context={"request": request}).data if latest_analysis else None,
        "pending_feedback_count": pending_feedback,
    }


def build_physio_action_queue(request):
    user = request.user
    sessions = AnalysisSession.objects.filter(plan__created_by=user).select_related("client", "plan")
    awaiting_review = sessions.filter(feedback_shared=False).order_by("-flagged_frames", "-started_at")
    feedback_sent = sessions.filter(feedback_shared=True).count()
    plans = Plan.objects.filter(created_by=user).select_related("user")

    actions = [
        ActionItem(
            action_type="review_analysis",
            title=f"Review {session.client.username}'s {session.exercise_name} session",
            description=f"{session.flagged_frames} flagged frames are waiting for physiotherapist feedback.",
            priority="high" if session.flagged_frames > 0 else "medium",
            url=f"/analysis/summary/{session.id}/",
            object_type="analysis_session",
            object_id=session.id,
        )
        for session in awaiting_review[:5]
    ]

    return {
        "role": "physio",
        "actions": [action.as_dict() for action in actions],
        "summary": {
            "clients": plans.values("user_id").distinct().count(),
            "active_plans": plans.count(),
            "awaiting_review": awaiting_review.count(),
            "feedback_sent": feedback_sent,
        },
        "next_review": AnalysisSessionSerializer(
            awaiting_review.first(),
            context={"request": request},
        ).data if awaiting_review.exists() else None,
    }
