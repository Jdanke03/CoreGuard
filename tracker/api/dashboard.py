from rest_framework.decorators import api_view
from rest_framework.response import Response

from tracker.api.serializers import AnalysisSessionSerializer, PlanSerializer
from tracker.models import AnalysisSession, Plan, SessionLog
from tracker.services.roles import is_physio


@api_view(["GET"])
def dashboard_view(request):
    user = request.user

    if is_physio(user):
        plans = Plan.objects.filter(created_by=user)
        sessions = AnalysisSession.objects.filter(plan__created_by=user).select_related("client", "plan")
        awaiting_review = sessions.filter(feedback_shared=False)
        feedback_sent = sessions.filter(feedback_shared=True)

        return Response({
            "role": "physio",
            "metrics": {
                "clients": plans.values("user_id").distinct().count(),
                "active_plans": plans.count(),
                "awaiting_review": awaiting_review.count(),
                "feedback_sent": feedback_sent.count(),
            },
            "recent_sessions": AnalysisSessionSerializer(
                sessions.order_by("-started_at")[:5],
                many=True,
                context={"request": request},
            ).data,
            "clients_needing_attention": AnalysisSessionSerializer(
                awaiting_review.order_by("-flagged_frames", "-started_at")[:5],
                many=True,
                context={"request": request},
            ).data,
        })

    plans = (
        Plan.objects.filter(user=user)
        .prefetch_related("plan_exercises__exercise")
        .select_related("created_by")
        .order_by("-created_at")
    )
    sessions = AnalysisSession.objects.filter(client=user).select_related("plan").order_by("-started_at")
    logs = SessionLog.objects.filter(user=user)
    latest_feedback = sessions.filter(feedback_shared=True).first()

    return Response({
        "role": "client",
        "metrics": {
            "active_plans": plans.count(),
            "sessions_logged": logs.count(),
            "analyses_completed": sessions.count(),
            "feedback_ready": sessions.filter(feedback_shared=True).count(),
        },
        "latest_plan": PlanSerializer(
            plans.first(),
            context={"request": request},
        ).data if plans.exists() else None,
        "latest_feedback": AnalysisSessionSerializer(
            latest_feedback,
            context={"request": request},
        ).data if latest_feedback else None,
        "latest_analysis": AnalysisSessionSerializer(
            sessions.first(),
            context={"request": request},
        ).data if sessions.exists() else None,
        "next_action": (
            "Review your latest physiotherapist feedback."
            if latest_feedback else
            "Complete a progress log or live analysis when your plan asks for it."
        ),
    })
