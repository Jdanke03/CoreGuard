from rest_framework.routers import DefaultRouter

from tracker.api.views import (
    AnalysisSessionViewSet,
    ExerciseViewSet,
    PlanExerciseViewSet,
    PlanViewSet,
    SessionLogViewSet,
)

router = DefaultRouter()
router.register("exercises", ExerciseViewSet, basename="api-exercise")
router.register("plans", PlanViewSet, basename="api-plan")
router.register("plan-exercises", PlanExerciseViewSet, basename="api-plan-exercise")
router.register("logs", SessionLogViewSet, basename="api-log")
router.register("analysis-sessions", AnalysisSessionViewSet, basename="api-analysis-session")

urlpatterns = router.urls
