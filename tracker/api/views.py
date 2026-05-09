from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from tracker.api.serializers import (
    AnalysisSessionSerializer,
    ExerciseSerializer,
    PlanExerciseSerializer,
    PlanSerializer,
    SessionLogCreateSerializer,
    SessionLogSerializer,
)
from tracker.models import AnalysisSession, Exercise, Plan, PlanExercise, SessionLog
from tracker.services.roles import is_physio


class AuthenticatedReadOnlyViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]


class ExerciseViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = ExerciseSerializer
    queryset = Exercise.objects.order_by("name")


class PlanViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = PlanSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Plan.objects.prefetch_related("plan_exercises__exercise").select_related("user", "created_by")
        if is_physio(user):
            return queryset.filter(created_by=user).order_by("-created_at")
        return queryset.filter(user=user).order_by("-created_at")


class PlanExerciseViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = PlanExerciseSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = PlanExercise.objects.select_related("plan", "exercise", "plan__user", "plan__created_by")
        if is_physio(user):
            return queryset.filter(plan__created_by=user)
        return queryset.filter(plan__user=user)


class SessionLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return SessionLogCreateSerializer
        return SessionLogSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = SessionLog.objects.select_related("user", "plan", "plan__created_by")
        if is_physio(user):
            return queryset.filter(plan__created_by=user).order_by("-date")
        return queryset.filter(user=user).order_by("-date")


class AnalysisSessionViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = AnalysisSessionSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = AnalysisSession.objects.select_related("client", "plan", "plan__created_by")
        if is_physio(user):
            return queryset.filter(plan__created_by=user).order_by("-started_at")
        return queryset.filter(client=user).order_by("-started_at")

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from tracker.api.serializers import UserSerializer, UserUpdateSerializer


@api_view(["POST"])
@permission_classes([])
def login_view(request):
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        "token": token.key,
        "user": UserSerializer(user).data,
    })


@api_view(["POST"])
def logout_view(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "PATCH"])
def me_view(request):
    if request.method == "PATCH":
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

    return Response(UserSerializer(request.user).data)


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
