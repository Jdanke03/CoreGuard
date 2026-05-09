from django.contrib.auth.models import User
from django.test import TestCase

from .models import Exercise, Plan, PlanExercise
from .services.analysis import angle, build_summary, create_analysis_state, update_squat_analysis_state
from .services.plans import build_exercise_prescription_rows, save_plan_prescriptions


class AnalysisServiceTests(TestCase):
    def test_angle_returns_degrees_for_right_angle(self):
        result = angle((0, 0), (1, 0), (1, 1))
        self.assertAlmostEqual(result, 90.0)

    def test_angle_returns_none_for_zero_length_vector(self):
        self.assertIsNone(angle((1, 1), (1, 1), (2, 2)))

    def test_build_summary_handles_empty_angle_counts(self):
        state = create_analysis_state()
        state["total_frames"] = 10

        summary = build_summary(state)

        self.assertEqual(summary["total_frames"], 10)
        self.assertIsNone(summary["angles"]["knee_avg"])
        self.assertIsNone(summary["angles"]["hip_avg"])

    def test_squat_analysis_updates_rule_counts_and_angle_averages(self):
        state = create_analysis_state()
        points = {
            "left_hip": (0.4, 0.3),
            "left_knee": (0.58, 0.5),
            "left_ankle": (0.5, 0.8),
            "left_shoulder": (0.35, 0.1),
            "right_hip": (0.6, 0.3),
            "right_knee": (0.42, 0.5),
            "right_ankle": (0.5, 0.8),
            "right_shoulder": (0.65, 0.1),
        }

        update_squat_analysis_state(state, points)

        self.assertEqual(state["rule_counts"]["knee_valgus"], 1)
        self.assertEqual(state["rule_counts"]["shallow_depth"], 1)
        self.assertEqual(state["flagged_frames"], 1)
        self.assertEqual(state["angle_counts"]["knee"], 1)
        self.assertEqual(state["angle_counts"]["hip"], 1)


class PlanPrescriptionServiceTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(username="client", password="testpass")
        self.plan = Plan.objects.create(
            user=self.client_user,
            name="Knee Rehab",
            description="Strength plan",
            duration_weeks=6,
        )
        self.squat = Exercise.objects.create(
            name="Squat",
            description="Controlled lower-body movement",
            body_area="Legs",
            difficulty="Easy",
        )
        self.row = Exercise.objects.create(
            name="Row",
            description="Upper-back pull",
            body_area="Back",
            difficulty="Medium",
        )

    def test_build_prescription_rows_prefills_existing_sets_and_reps(self):
        PlanExercise.objects.create(plan=self.plan, exercise=self.squat, sets=4, reps=12)

        rows = build_exercise_prescription_rows(self.plan)
        squat_row = next(row for row in rows if row["exercise"] == self.squat)

        self.assertEqual(squat_row["sets_value"], 4)
        self.assertEqual(squat_row["reps_value"], 12)

    def test_save_plan_prescriptions_creates_and_updates_rows(self):
        post_data = {
            f"exercise_{self.squat.id}_sets": "5",
            f"exercise_{self.squat.id}_reps": "8",
            f"exercise_{self.row.id}_sets": "not-a-number",
            f"exercise_{self.row.id}_reps": "0",
        }

        save_plan_prescriptions(self.plan, [self.squat, self.row], post_data)

        squat_plan_exercise = PlanExercise.objects.get(plan=self.plan, exercise=self.squat)
        row_plan_exercise = PlanExercise.objects.get(plan=self.plan, exercise=self.row)

        self.assertEqual(squat_plan_exercise.sets, 5)
        self.assertEqual(squat_plan_exercise.reps, 8)
        self.assertEqual(row_plan_exercise.sets, 3)
        self.assertEqual(row_plan_exercise.reps, 1)
