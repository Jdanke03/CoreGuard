from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from tracker.api.serializers import (
    AnalysisSessionSerializer,
    ExerciseSerializer,
    PlanExerciseSerializer,
    PlanSerializer,
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


class SessionLogViewSet(AuthenticatedReadOnlyViewSet):
    serializer_class = SessionLogSerializer

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

from tracker.api.serializers import UserSerializer


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


@api_view(["GET"])
def me_view(request):
    return Response(UserSerializer(request.user).data)
