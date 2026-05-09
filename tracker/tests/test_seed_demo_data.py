from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from tracker.models import AnalysisSession, Exercise, Plan, PlanExercise, SessionLog


class SeedDemoDataCommandTests(TestCase):
    def test_seed_demo_data_creates_repeatable_demo_records(self):
        output = StringIO()

        call_command("seed_demo_data", stdout=output)
        call_command("seed_demo_data", stdout=output)

        self.assertTrue(Group.objects.filter(name="Physio").exists())
        self.assertTrue(User.objects.filter(username="demo_physio").exists())
        self.assertEqual(User.objects.filter(username__startswith="demo_client_").count(), 2)
        self.assertGreaterEqual(Exercise.objects.count(), 5)
        self.assertEqual(Plan.objects.count(), 2)
        self.assertGreaterEqual(PlanExercise.objects.count(), 5)
        self.assertEqual(SessionLog.objects.count(), 3)
        self.assertEqual(AnalysisSession.objects.count(), 1)
        self.assertIn("CoreGuard demo data is ready", output.getvalue())
