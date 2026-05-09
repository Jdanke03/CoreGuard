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
