from django.contrib.auth.models import Group, User
from django.test import TestCase

from tracker.models import AnalysisSession, Exercise, Plan, PlanExercise, SessionLog


class ActionQueueApiTests(TestCase):
    def setUp(self):
        physio_group = Group.objects.create(name="Physio")
        self.physio = User.objects.create_user(username="physio", password="testpass")
        self.physio.groups.add(physio_group)
        self.client_user = User.objects.create_user(username="client", password="testpass")
        self.exercise = Exercise.objects.create(
            name="Squat",
            description="Controlled squat movement",
            body_area="Legs",
            difficulty="Easy",
        )
        self.plan = Plan.objects.create(
            user=self.client_user,
            created_by=self.physio,
            name="Knee Rehab",
            description="Build lower-body control.",
            requires_analysis=True,
            duration_weeks=6,
        )
        PlanExercise.objects.create(plan=self.plan, exercise=self.exercise, sets=3, reps=10)
        SessionLog.objects.create(user=self.client_user, plan=self.plan, pain_level=3, notes="Good session")
        self.session = AnalysisSession.objects.create(
            client=self.client_user,
            plan=self.plan,
            exercise_name="Squat",
            total_frames=120,
            flagged_frames=9,
        )

    def test_client_action_queue_prioritises_feedback_when_ready(self):
        self.session.feedback_shared = True
        self.session.physio_feedback = "Keep your knees aligned."
        self.session.save(update_fields=["feedback_shared", "physio_feedback"])
        self.client.login(username="client", password="testpass")

        response = self.client.get("/api/actions/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], "client")
        self.assertEqual(payload["actions"][0]["type"], "review_feedback")
        self.assertEqual(payload["latest_plan"]["name"], "Knee Rehab")

    def test_client_action_queue_suggests_live_analysis_for_analysis_plan(self):
        self.session.delete()
        self.client.login(username="client", password="testpass")

        response = self.client.get("/api/actions/")

        self.assertEqual(response.status_code, 200)
        action_types = [action["type"] for action in response.json()["actions"]]
        self.assertIn("complete_live_analysis", action_types)
        self.assertIn("log_progress", action_types)

    def test_physio_action_queue_returns_sessions_waiting_for_review(self):
        self.client.login(username="physio", password="testpass")

        response = self.client.get("/api/actions/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], "physio")
        self.assertEqual(payload["actions"][0]["type"], "review_analysis")
        self.assertEqual(payload["summary"]["awaiting_review"], 1)
        self.assertEqual(payload["next_review"]["id"], self.session.id)

    def test_action_queue_requires_login(self):
        response = self.client.get("/api/actions/")

        self.assertIn(response.status_code, [401, 403])
