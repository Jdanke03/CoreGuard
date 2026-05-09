from django.urls import path
from rest_framework.routers import DefaultRouter

from tracker.api.analysis import AnalysisSessionViewSet
from tracker.api.auth import login_view, logout_view, me_view
from tracker.api.clients import ClientViewSet
from tracker.api.dashboard import dashboard_view
from tracker.api.exercises import ExerciseViewSet
from tracker.api.logs import SessionLogViewSet
from tracker.api.plans import PlanExerciseViewSet, PlanViewSet

router = DefaultRouter()
router.register("exercises", ExerciseViewSet, basename="api-exercise")
router.register("clients", ClientViewSet, basename="api-client")
router.register("plans", PlanViewSet, basename="api-plan")
router.register("plan-exercises", PlanExerciseViewSet, basename="api-plan-exercise")
router.register("logs", SessionLogViewSet, basename="api-log")
router.register("analysis-sessions", AnalysisSessionViewSet, basename="api-analysis-session")

urlpatterns = [
    path("auth/login/", login_view, name="api-login"),
    path("auth/logout/", logout_view, name="api-logout"),
    path("dashboard/", dashboard_view, name="api-dashboard"),
    path("me/", me_view, name="api-me"),
] + router.urls
