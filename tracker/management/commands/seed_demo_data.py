import json
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from tracker.models import AnalysisSession, Exercise, Plan, PlanExercise, SessionLog


class Command(BaseCommand):
    help = "Create repeatable demo data for local CoreGuard development."

    def handle(self, *args, **options):
        physio_group, _ = Group.objects.get_or_create(name="Physio")

        physio = self._user("demo_physio", "physio@coreguard.local", "CoreGuardDemo123")
        physio.groups.add(physio_group)

        clients = [
            self._user("demo_client_amy", "amy.client@coreguard.local", "CoreGuardDemo123"),
            self._user("demo_client_ben", "ben.client@coreguard.local", "CoreGuardDemo123"),
        ]

        exercises = self._exercises()
        plans = self._plans(physio, clients, exercises)
        self._logs(plans)
        self._analysis_sessions(physio, plans)

        self.stdout.write(self.style.SUCCESS("CoreGuard demo data is ready."))
        self.stdout.write("Physio login: demo_physio / CoreGuardDemo123")
        self.stdout.write("Client login: demo_client_amy / CoreGuardDemo123")

    def _user(self, username, email, password):
        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
        elif user.email != email:
            user.email = email
            user.save(update_fields=["email"])
        return user

    def _exercises(self):
        exercise_specs = [
            ("Squat", "Controlled lower-body movement for knee and hip strength.", "Legs", "Easy"),
            ("Wall Sit", "Hold a seated position against a wall to build quad endurance.", "Legs", "Medium"),
            ("Resistance Band Row", "Pull the band towards the body while keeping shoulders controlled.", "Back", "Medium"),
            ("Calf Raise", "Rise onto the toes and lower with control to strengthen the ankle and calf.", "Ankle", "Easy"),
            ("Shoulder Press", "Press upward while keeping the trunk stable and shoulders level.", "Shoulder", "Medium"),
        ]
        exercises = {}
        for name, description, body_area, difficulty in exercise_specs:
            exercise, _ = Exercise.objects.update_or_create(
                name=name,
                defaults={
                    "description": description,
                    "body_area": body_area,
                    "difficulty": difficulty,
                    "video_url": "",
                },
            )
            exercises[name] = exercise
        return exercises

    def _plans(self, physio, clients, exercises):
        plan_specs = [
            {
                "client": clients[0],
                "name": "Knee Control Programme",
                "description": "Build squat control, quad endurance, and confidence with loaded movement.",
                "duration_weeks": 6,
                "requires_analysis": True,
                "items": [("Squat", 3, 10), ("Wall Sit", 3, 30), ("Calf Raise", 3, 12)],
            },
            {
                "client": clients[1],
                "name": "Shoulder Stability Programme",
                "description": "Improve shoulder control, upper-back strength, and daily movement tolerance.",
                "duration_weeks": 8,
                "requires_analysis": False,
                "items": [("Shoulder Press", 3, 8), ("Resistance Band Row", 4, 12)],
            },
        ]

        plans = []
        for spec in plan_specs:
            plan, _ = Plan.objects.update_or_create(
                user=spec["client"],
                created_by=physio,
                name=spec["name"],
                defaults={
                    "description": spec["description"],
                    "duration_weeks": spec["duration_weeks"],
                    "requires_analysis": spec["requires_analysis"],
                },
            )
            plan.exercises.set([exercises[name] for name, _, _ in spec["items"]])
            for order, (exercise_name, sets, reps) in enumerate(spec["items"]):
                PlanExercise.objects.update_or_create(
                    plan=plan,
                    exercise=exercises[exercise_name],
                    defaults={"sets": sets, "reps": reps, "order": order},
                )
            plans.append(plan)
        return plans

    def _logs(self, plans):
        log_specs = [
            (plans[0], 3, "Completed all exercises. Squats felt controlled."),
            (plans[0], 4, "Wall sits were harder today but manageable."),
            (plans[1], 2, "Shoulder press felt smooth with light resistance."),
        ]
        for index, (plan, pain_level, notes) in enumerate(log_specs):
            log, _ = SessionLog.objects.get_or_create(
                user=plan.user,
                plan=plan,
                notes=notes,
                defaults={"pain_level": pain_level},
            )
            log.pain_level = pain_level
            log.date = timezone.localdate() - timedelta(days=index)
            log.save(update_fields=["pain_level", "date"])

    def _analysis_sessions(self, physio, plans):
        summary = {
            "rules": {"knee_valgus": 3, "shallow_depth": 8, "forward_lean": 4},
            "angles": {"knee_avg": 96.4, "hip_avg": 72.1, "torso_avg": 18.6},
            "total_frames": 240,
            "flagged_frames": 15,
        }
        session, _ = AnalysisSession.objects.update_or_create(
            client=plans[0].user,
            plan=plans[0],
            exercise_name="Squat",
            defaults={
                "created_by": physio,
                "total_frames": 240,
                "flagged_frames": 15,
                "summary_json": json.dumps(summary),
                "physio_feedback_draft": "Good effort. Focus on reaching slightly more depth while keeping the knees aligned.",
                "physio_feedback": "Good effort overall. Keep working on controlled depth and steady knee alignment.",
                "feedback_shared": True,
                "feedback_at": timezone.now(),
            },
        )
        session.started_at = timezone.now() - timedelta(days=1)
        session.ended_at = session.started_at + timedelta(minutes=2)
        session.save(update_fields=["started_at", "ended_at"])
