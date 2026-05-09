from django.urls import path
from rest_framework.routers import DefaultRouter

from tracker.api.views import (
    AnalysisSessionViewSet,
    ExerciseViewSet,
    PlanExerciseViewSet,
    PlanViewSet,
    SessionLogViewSet,
    login_view,
    logout_view,
    me_view,
)

router = DefaultRouter()
router.register("exercises", ExerciseViewSet, basename="api-exercise")
router.register("plans", PlanViewSet, basename="api-plan")
router.register("plan-exercises", PlanExerciseViewSet, basename="api-plan-exercise")
router.register("logs", SessionLogViewSet, basename="api-log")
router.register("analysis-sessions", AnalysisSessionViewSet, basename="api-analysis-session")

urlpatterns = [
    path("auth/login/", login_view, name="api-login"),
    path("auth/logout/", logout_view, name="api-logout"),
    path("me/", me_view, name="api-me"),
] + router.urls
