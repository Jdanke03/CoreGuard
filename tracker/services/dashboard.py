import json

from django.db.models import Count

from ..models import AnalysisSession, Exercise, Plan, SessionLog


def build_home_context(user, is_physio_user):
    context = {
        "exercises": Exercise.objects.all()[:3],
        "is_physio": is_physio_user,
    }

    if is_physio_user:
        context.update(build_physio_dashboard_context(user))
    else:
        context.update(build_client_dashboard_context(user))

    return context


def build_physio_dashboard_context(user):
    physio_plans = Plan.objects.filter(created_by=user)
    physio_sessions = AnalysisSession.objects.filter(plan__created_by=user).select_related("client", "plan")
    client_ids = physio_plans.values_list("user_id", flat=True).distinct()

    feedback_sent = physio_sessions.filter(feedback_shared=True).count()
    awaiting_review = physio_sessions.filter(feedback_shared=False).count()

    sessions_per_client = list(
        physio_sessions.values("client__username")
        .annotate(total=Count("id"))
        .order_by("-total", "client__username")[:6]
    )

    return {
        "physio_total_clients": len(set(client_ids)),
        "physio_active_plans": physio_plans.count(),
        "physio_awaiting_review": awaiting_review,
        "physio_feedback_sent": feedback_sent,
        "recent_sessions": physio_sessions.order_by("-started_at")[:5],
        "clients_needing_attention": (
            physio_sessions.filter(feedback_shared=False)
            .order_by("-flagged_frames", "-started_at")[:4]
        ),
        "feedback_chart_data": json.dumps({
            "labels": ["Awaiting review", "Feedback sent"],
            "values": [awaiting_review, feedback_sent],
        }),
        "sessions_per_client_data": json.dumps({
            "labels": [row["client__username"] for row in sessions_per_client],
            "values": [row["total"] for row in sessions_per_client],
        }),
    }


def build_client_dashboard_context(user):
    client_plans = (
        Plan.objects.filter(user=user)
        .prefetch_related("plan_exercises__exercise")
        .order_by("-created_at")
    )
    client_logs = SessionLog.objects.filter(user=user)
    client_sessions = AnalysisSession.objects.filter(client=user).select_related("plan").order_by("-started_at")

    feedback_ready = client_sessions.filter(feedback_shared=True).count()
    pending_review = client_sessions.filter(feedback_shared=False).count()
    latest_feedback_session = client_sessions.filter(feedback_shared=True).first()
    latest_client_plan = client_plans.first()

    return {
        "client_active_plans": client_plans.count(),
        "client_sessions_logged": client_logs.count(),
        "client_analyses_completed": client_sessions.count(),
        "client_feedback_ready": feedback_ready,
        "latest_feedback_session": latest_feedback_session,
        "latest_analysis_session": client_sessions.first(),
        "latest_client_plan": latest_client_plan,
        "latest_plan_items": list(latest_client_plan.plan_exercises.select_related("exercise").all()[:4]) if latest_client_plan else [],
        "client_next_action": (
            "Open your latest feedback to review your physiotherapist’s comments."
            if latest_feedback_session else
            "Complete a live analysis session when your plan requires it."
        ),
        "client_status_chart_data": json.dumps({
            "labels": ["Feedback ready", "Awaiting review"],
            "values": [feedback_ready, pending_review],
        }),
    }
