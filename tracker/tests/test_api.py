from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from tracker.models import AnalysisSession, Exercise, Plan, PlanExercise, SessionLog


class ApiRouteTests(TestCase):
    def setUp(self):
        self.physio_group = Group.objects.create(name="Physio")
        self.physio = User.objects.create_user(username="physio", password="testpass")
        self.physio.groups.add(self.physio_group)
        self.client_user = User.objects.create_user(username="client", password="testpass")
        self.other_client = User.objects.create_user(username="other", password="testpass")

        self.exercise = Exercise.objects.create(
            name="Squat",
            description="Controlled lower-body movement",
            body_area="Legs",
            difficulty="Easy",
        )
        self.plan = Plan.objects.create(
            user=self.client_user,
            created_by=self.physio,
            name="Knee Rehab",
            description="Strength plan",
            duration_weeks=6,
            requires_analysis=True,
        )
        self.other_plan = Plan.objects.create(
            user=self.other_client,
            name="Other Plan",
            description="Private plan",
            duration_weeks=4,
        )
        PlanExercise.objects.create(plan=self.plan, exercise=self.exercise, sets=3, reps=10)
        SessionLog.objects.create(user=self.client_user, plan=self.plan, pain_level=3, notes="Good session")
        AnalysisSession.objects.create(client=self.client_user, plan=self.plan, exercise_name="Squat")

    def test_api_requires_authentication(self):
        response = self.client.get("/api/exercises/")
        self.assertIn(response.status_code, [403, 401])

    def test_client_only_sees_their_own_plans(self):
        self.client.login(username="client", password="testpass")

        response = self.client.get("/api/plans/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["name"], "Knee Rehab")

    def test_physio_only_sees_plans_they_created(self):
        self.client.login(username="physio", password="testpass")

        response = self.client.get("/api/plans/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["client_username"], "client")

    def test_plan_api_includes_prescription_details(self):
        self.client.login(username="client", password="testpass")

        response = self.client.get("/api/plans/")
        prescription = response.json()[0]["prescriptions"][0]

        self.assertEqual(prescription["sets"], 3)
        self.assertEqual(prescription["reps"], 10)
        self.assertEqual(prescription["exercise"]["name"], "Squat")

    def test_client_can_read_their_analysis_sessions(self):
        self.client.login(username="client", password="testpass")

        response = self.client.get("/api/analysis-sessions/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["exercise_name"], "Squat")

    def test_client_can_create_progress_log_for_own_plan(self):
        self.client.login(username="client", password="testpass")

        response = self.client.post("/api/logs/", {
            "plan": self.plan.id,
            "pain_level": 4,
            "notes": "Completed the session with mild discomfort.",
        })

        self.assertEqual(response.status_code, 201)
        log = SessionLog.objects.latest("id")
        self.assertEqual(log.user, self.client_user)
        self.assertEqual(log.plan, self.plan)
        self.assertEqual(log.pain_level, 4)

    def test_client_cannot_create_progress_log_for_another_clients_plan(self):
        self.client.login(username="client", password="testpass")

        response = self.client.post("/api/logs/", {
            "plan": self.other_plan.id,
            "pain_level": 4,
            "notes": "Trying to log against another plan.",
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            SessionLog.objects.filter(user=self.client_user, plan=self.other_plan).exists()
        )

    def test_physio_cannot_create_client_progress_log(self):
        self.client.login(username="physio", password="testpass")

        response = self.client.post("/api/logs/", {
            "plan": self.plan.id,
            "pain_level": 4,
            "notes": "Physio should not create client logs.",
        })

        self.assertEqual(response.status_code, 400)

    def test_progress_log_pain_level_must_be_between_one_and_ten(self):
        self.client.login(username="client", password="testpass")

        response = self.client.post("/api/logs/", {
            "plan": self.plan.id,
            "pain_level": 11,
            "notes": "Invalid pain level.",
        })

        self.assertEqual(response.status_code, 400)

    def test_client_dashboard_returns_home_screen_summary(self):
        self.client.login(username="client", password="testpass")
        AnalysisSession.objects.create(
            client=self.client_user,
            plan=self.plan,
            exercise_name="Squat",
            feedback_shared=True,
            physio_feedback="Keep focusing on controlled depth.",
        )

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], "client")
        self.assertEqual(payload["metrics"]["active_plans"], 1)
        self.assertEqual(payload["metrics"]["sessions_logged"], 1)
        self.assertEqual(payload["metrics"]["analyses_completed"], 2)
        self.assertEqual(payload["metrics"]["feedback_ready"], 1)
        self.assertEqual(payload["latest_plan"]["name"], "Knee Rehab")
        self.assertEqual(payload["latest_feedback"]["physio_feedback"], "Keep focusing on controlled depth.")

    def test_physio_dashboard_returns_review_summary(self):
        self.client.login(username="physio", password="testpass")

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role"], "physio")
        self.assertEqual(payload["metrics"]["clients"], 1)
        self.assertEqual(payload["metrics"]["active_plans"], 1)
        self.assertEqual(payload["metrics"]["awaiting_review"], 1)
        self.assertEqual(payload["metrics"]["feedback_sent"], 0)
        self.assertEqual(len(payload["recent_sessions"]), 1)
        self.assertEqual(len(payload["clients_needing_attention"]), 1)


class ApiAuthTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client",
            email="client@example.com",
            password="testpass",
        )
        self.physio_group = Group.objects.create(name="Physio")
        self.physio = User.objects.create_user(
            username="physio",
            email="physio@example.com",
            password="testpass",
        )
        self.physio.groups.add(self.physio_group)

    def test_login_returns_token_and_user_payload(self):
        response = self.client.post("/api/auth/login/", {
            "username": "client",
            "password": "testpass",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())
        self.assertEqual(response.json()["user"]["username"], "client")
        self.assertEqual(response.json()["user"]["role"], "client")

    def test_invalid_login_fails(self):
        response = self.client.post("/api/auth/login/", {
            "username": "client",
            "password": "wrongpass",
        })

        self.assertEqual(response.status_code, 400)

    def test_token_can_access_me_endpoint(self):
        login_response = self.client.post("/api/auth/login/", {
            "username": "client",
            "password": "testpass",
        })
        token = login_response.json()["token"]

        response = self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Token {token}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "client@example.com")
        self.assertEqual(response.json()["role"], "client")

    def test_me_endpoint_returns_physio_role(self):
        login_response = self.client.post("/api/auth/login/", {
            "username": "physio",
            "password": "testpass",
        })
        token = login_response.json()["token"]

        response = self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Token {token}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "physio")

    def test_user_can_update_own_email(self):
        login_response = self.client.post("/api/auth/login/", {
            "username": "client",
            "password": "testpass",
        })
        token = login_response.json()["token"]

        response = self.client.patch(
            "/api/me/",
            {"email": "updated@example.com"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "updated@example.com")
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.email, "updated@example.com")

    def test_user_cannot_update_email_to_an_existing_email(self):
        User.objects.create_user(
            username="other",
            email="other@example.com",
            password="testpass",
        )
        login_response = self.client.post("/api/auth/login/", {
            "username": "client",
            "password": "testpass",
        })
        token = login_response.json()["token"]

        response = self.client.patch(
            "/api/me/",
            {"email": "other@example.com"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {token}",
        )

        self.assertEqual(response.status_code, 400)

    def test_logout_deletes_token(self):
        login_response = self.client.post("/api/auth/login/", {
            "username": "client",
            "password": "testpass",
        })
        token = login_response.json()["token"]

        logout_response = self.client.post("/api/auth/logout/", HTTP_AUTHORIZATION=f"Token {token}")
        me_response = self.client.get("/api/me/", HTTP_AUTHORIZATION=f"Token {token}")

        self.assertEqual(logout_response.status_code, 204)
        self.assertIn(me_response.status_code, [401, 403])
