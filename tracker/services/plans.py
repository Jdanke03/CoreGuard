from ..models import Exercise, PlanExercise


def build_exercise_prescription_rows(plan=None, post_data=None):
    existing = {}
    if plan is not None:
        existing = {
            item.exercise_id: item
            for item in plan.plan_exercises.select_related("exercise")
        }

    rows = []
    for exercise in Exercise.objects.order_by("name"):
        item = existing.get(exercise.id)
        rows.append({
            "exercise": exercise,
            "sets_name": f"exercise_{exercise.id}_sets",
            "reps_name": f"exercise_{exercise.id}_reps",
            "sets_value": post_data.get(f"exercise_{exercise.id}_sets") if post_data else (item.sets if item else 3),
            "reps_value": post_data.get(f"exercise_{exercise.id}_reps") if post_data else (item.reps if item else 10),
        })
    return rows


def save_plan_prescriptions(plan, selected_exercises, post_data):
    selected_ids = [exercise.id for exercise in selected_exercises]
    PlanExercise.objects.filter(plan=plan).exclude(exercise_id__in=selected_ids).delete()

    for index, exercise in enumerate(selected_exercises):
        sets = _positive_int_or_default(post_data.get(f"exercise_{exercise.id}_sets", "3"), default=3)
        reps = _positive_int_or_default(post_data.get(f"exercise_{exercise.id}_reps", "10"), default=10)

        PlanExercise.objects.update_or_create(
            plan=plan,
            exercise=exercise,
            defaults={
                "sets": sets,
                "reps": reps,
                "order": index,
            }
        )


def _positive_int_or_default(value, default):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default
