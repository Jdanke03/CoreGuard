from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ExerciseForm
from .models import Exercise
from .services.roles import is_physio


@login_required
@user_passes_test(lambda user: user.is_staff or is_physio(user))
def exercise_create(request):
    if request.method == "POST":
        form = ExerciseForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("exercise_list")
    else:
        form = ExerciseForm()

    return render(request, "exercise_form.html", {"form": form})


@login_required
def exercise_list(request):
    exercises = Exercise.objects.all()
    can_add_exercise = request.user.is_staff or is_physio(request.user)

    return render(request, "exercise_list.html", {
        "exercises": exercises,
        "can_add_exercise": can_add_exercise,
    })


def exercise_detail(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    return render(request, "exercise_detail.html", {
        "exercise": exercise,
        "is_physio": is_physio(request.user),
    })


@login_required
@user_passes_test(lambda user: user.is_staff or is_physio(user))
def exercise_delete(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    if request.method == "POST":
        exercise.delete()
        return redirect("exercise_list")

    return render(request, "exercise_confirm_delete.html", {"exercise": exercise})
