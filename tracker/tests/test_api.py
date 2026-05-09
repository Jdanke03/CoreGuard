from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from tracker.models import AnalysisSession, Exercise, Plan, PlanExercise, SessionLog


class ApiRouteTests(TestCase):
    def setUp(self):
        self.physio_group = Group.objects.create(name="Physio")
        self.physio = User.objects.create_user(
            username="physio",
            email="physio@example.com",
            password="testpass",
        )
        self.physio.groups.add(self.physio_group)
        self.client_user = User.objects.create_user(
            username="client",
            email="client@example.com",
            password="testpass",
        )
        self.other_client = User.objects.create_user(
            username="other",
            email="other@example.com",
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

    def test_openapi_schema_and_docs_are_available(self):
        schema_response = self.client.get("/api/schema/")
        docs_response = self.client.get("/api/docs/")

        self.assertEqual(schema_response.status_code, 200)
        self.assertEqual(docs_response.status_code, 200)
        self.assertIn("CoreGuard API", schema_response.content.decode())

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

        self.assertEqual(response.status_code, 403)

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

    def test_physio_can_create_plan_with_prescriptions(self):
        self.client.login(username="physio", password="testpass")

        response = self.client.post(
            "/api/plans/",
            {
                "user": self.client_user.id,
                "name": "Shoulder Rehab",
                "description": "Build control and strength.",
                "duration_weeks": 8,
                "requires_analysis": False,
                "prescriptions": [
                    {"exercise": self.exercise.id, "sets": 4, "reps": 12},
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        plan = Plan.objects.get(name="Shoulder Rehab")
        self.assertEqual(plan.created_by, self.physio)
        self.assertEqual(plan.user, self.client_user)
        prescription = plan.plan_exercises.get()
        self.assertEqual(prescription.sets, 4)
        self.assertEqual(prescription.reps, 12)

    def test_client_cannot_create_plan(self):
        self.client.login(username="client", password="testpass")

        response = self.client.post(
            "/api/plans/",
            {
                "user": self.client_user.id,
                "name": "Client Plan Attempt",
                "description": "Should not work.",
                "duration_weeks": 4,
                "requires_analysis": False,
                "prescriptions": [
                    {"exercise": self.exercise.id, "sets": 3, "reps": 10},
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Plan.objects.filter(name="Client Plan Attempt").exists())

    def test_physio_can_list_assigned_clients(self):
        self.client.login(username="physio", password="testpass")

        response = self.client.get("/api/clients/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["username"], "client")
        self.assertEqual(payload[0]["active_plans"], 1)
        self.assertEqual(payload[0]["awaiting_review"], 1)

    def test_client_cannot_list_physio_clients(self):
        self.client.login(username="client", password="testpass")

        response = self.client.get("/api/clients/")

        self.assertEqual(response.status_code, 403)

    def test_analysis_api_returns_clean_summary_metrics(self):
        self.client.login(username="client", password="testpass")
        session = AnalysisSession.objects.get(client=self.client_user)
        session.total_frames = 120
        session.flagged_frames = 18
        session.summary_json = (
            '{"rules": {"knee_valgus": 4, "shallow_depth": 10, "forward_lean": 4}, '
            '"angles": {"knee_avg": 94.5, "hip_avg": 68.2}, '
            '"total_frames": 120, "flagged_frames": 18}'
        )
        session.save()

        response = self.client.get("/api/analysis-sessions/")

        self.assertEqual(response.status_code, 200)
        metrics = response.json()[0]["summary_metrics"]
        self.assertEqual(metrics["rules"]["shallow_depth"], 10)
        self.assertEqual(metrics["angles"]["knee_avg"], 94.5)
        self.assertEqual(metrics["total_frames"], 120)

    @patch("tracker.tasks.feedback.generate_ai_draft", return_value="Keep your knees aligned and slow the movement slightly.")
    def test_physio_can_generate_feedback_draft(self, mocked_generate):
        self.client.login(username="physio", password="testpass")
        session = AnalysisSession.objects.get(client=self.client_user)

        response = self.client.post(f"/api/analysis-sessions/{session.id}/generate-draft/")

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.physio_feedback_draft, "Keep your knees aligned and slow the movement slightly.")
        self.assertEqual(response.json()["physio_feedback"], "Keep your knees aligned and slow the movement slightly.")
        self.assertEqual(response.json()["draft_status"], "ready")
        mocked_generate.assert_called_once_with(session)

    @patch("tracker.tasks.feedback.send_feedback_email", return_value=True)
    def test_physio_can_send_final_feedback(self, mocked_email):
        self.client.login(username="physio", password="testpass")
        session = AnalysisSession.objects.get(client=self.client_user)

        response = self.client.post(
            f"/api/analysis-sessions/{session.id}/send-feedback/",
            {"physio_feedback": "Good effort. Work on keeping your hips lower."},
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertTrue(session.feedback_shared)
        self.assertEqual(session.physio_feedback, "Good effort. Work on keeping your hips lower.")
        self.assertEqual(response.json()["email_delivery"], "sent")
        mocked_email.assert_called_once_with(session)

    @patch("tracker.tasks.feedback.send_feedback_email", side_effect=RuntimeError("SMTP timeout"))
    def test_feedback_is_still_saved_when_email_delivery_fails(self, mocked_email):
        self.client.login(username="physio", password="testpass")
        session = AnalysisSession.objects.get(client=self.client_user)

        response = self.client.post(
            f"/api/analysis-sessions/{session.id}/send-feedback/",
            {"physio_feedback": "Saved even if email fails."},
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertTrue(session.feedback_shared)
        self.assertEqual(session.physio_feedback, "Saved even if email fails.")
        self.assertEqual(response.json()["email_delivery"], "failed")
        self.assertIn("SMTP timeout", response.json()["email_error"])
        mocked_email.assert_called_once_with(session)

    @patch("tracker.tasks.feedback.send_feedback_email")
    def test_feedback_email_is_skipped_when_client_has_no_email(self, mocked_email):
        self.client.login(username="physio", password="testpass")
        self.client_user.email = ""
        self.client_user.save(update_fields=["email"])
        session = AnalysisSession.objects.get(client=self.client_user)

        response = self.client.post(
            f"/api/analysis-sessions/{session.id}/send-feedback/",
            {"physio_feedback": "Saved inside CoreGuard only."},
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertTrue(session.feedback_shared)
        self.assertEqual(response.json()["email_delivery"], "skipped_no_email")
        mocked_email.assert_not_called()

    def test_physio_can_create_exercise_with_image(self):
        self.client.login(username="physio", password="testpass")
        image = SimpleUploadedFile(
            "exercise.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post("/api/exercises/", {
            "name": "Wall Sit",
            "description": "Hold a controlled seated position against a wall.",
            "body_area": "Legs",
            "difficulty": "Medium",
            "image": image,
            "video_url": "",
        })

        self.assertEqual(response.status_code, 201)
        exercise = Exercise.objects.get(name="Wall Sit")
        self.assertTrue(exercise.image.name.startswith("exercises/"))

    def test_client_cannot_create_exercise(self):
        self.client.login(username="client", password="testpass")

        response = self.client.post("/api/exercises/", {
            "name": "Client Exercise Attempt",
            "description": "Should not work.",
            "body_area": "Legs",
            "difficulty": "Easy",
            "video_url": "",
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Exercise.objects.filter(name="Client Exercise Attempt").exists())

    def test_exercise_api_supports_search_and_filtering(self):
        Exercise.objects.create(
            name="Wall Sit",
            description="Hold a seated position against a wall.",
            body_area="Legs",
            difficulty="Medium",
        )
        self.client.login(username="client", password="testpass")

        filtered = self.client.get("/api/exercises/?difficulty=Medium")
        searched = self.client.get("/api/exercises/?search=wall")

        self.assertEqual(filtered.status_code, 200)
        self.assertEqual({item["name"] for item in filtered.json()}, {"Wall Sit"})
        self.assertEqual(searched.status_code, 200)
        self.assertEqual(searched.json()[0]["name"], "Wall Sit")

    def test_plan_api_supports_safe_filtering(self):
        second_plan = Plan.objects.create(
            user=self.client_user,
            created_by=self.physio,
            name="General Strength",
            description="Follow-up plan",
            duration_weeks=4,
            requires_analysis=False,
        )
        self.client.login(username="physio", password="testpass")

        response = self.client.get("/api/plans/?requires_analysis=false&ordering=name")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.json()], [second_plan.name])
        self.assertNotIn("Other Plan", [item["name"] for item in response.json()])

    def test_logs_api_supports_search_and_ordering(self):
        SessionLog.objects.create(
            user=self.client_user,
            plan=self.plan,
            pain_level=6,
            notes="Harder session with mild knee soreness",
        )
        self.client.login(username="client", password="testpass")

        response = self.client.get("/api/logs/?search=soreness&ordering=-pain_level")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["pain_level"], 6)

    def test_analysis_api_supports_feedback_filtering(self):
        reviewed = AnalysisSession.objects.create(
            client=self.client_user,
            plan=self.plan,
            exercise_name="Squat",
            feedback_shared=True,
            physio_feedback="Reviewed session.",
        )
        self.client.login(username="physio", password="testpass")

        response = self.client.get("/api/analysis-sessions/?feedback_shared=true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [reviewed.id])

    def test_clients_api_supports_search(self):
        self.client.login(username="physio", password="testpass")

        response = self.client.get("/api/clients/?search=client")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["username"], "client")


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
