from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tracker.models import Exercise, Plan


class RouteSmokeTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username="client",
            email="client@example.com",
            password="testpass",
        )
        self.exercise = Exercise.objects.create(
            name="Squat",
            description="Controlled lower-body movement",
            body_area="Legs",
            difficulty="Easy",
        )
        self.plan = Plan.objects.create(
            user=self.client_user,
            name="Knee Rehab",
            description="Strength plan",
            duration_weeks=6,
        )

    def test_public_pages_render(self):
        for route_name in ["home", "faq_support", "login", "register"]:
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)

    def test_client_dashboard_routes_render_after_login(self):
        self.client.login(username="client", password="testpass")

        routes = [
            reverse("home"),
            reverse("profile"),
            reverse("exercise_list"),
            reverse("exercise_detail", args=[self.exercise.pk]),
            reverse("plan_list"),
            reverse("plan_detail", args=[self.plan.pk]),
            reverse("log_list"),
            reverse("analysis_start"),
        ]

        for route in routes:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)

    def test_client_can_open_log_form_for_own_plan(self):
        self.client.login(username="client", password="testpass")

        response = self.client.get(reverse("log_create_for_plan", args=[self.plan.pk]))

        self.assertEqual(response.status_code, 200)

