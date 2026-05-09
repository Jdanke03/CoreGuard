from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PlanForm
from .models import AnalysisSession, Plan, SessionLog
from .services.plans import build_exercise_prescription_rows, save_plan_prescriptions
from .services.roles import is_physio


@login_required
def plan_list(request):
    if is_physio(request.user):
        client_ids = list(
            Plan.objects.filter(created_by=request.user)
            .values_list("user_id", flat=True)
            .distinct()
        )
        clients = User.objects.filter(id__in=client_ids).order_by("username")
        return render(request, "physio_clients.html", {
            "clients": clients,
        })

    plans = Plan.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "plan_list.html", {
        "plans": plans,
        "clients": None,
        "selected_client_id": "",
    })


@login_required
def plan_detail(request, pk):
    plan = get_object_or_404(Plan, pk=pk)

    if not (
        (not is_physio(request.user) and plan.user == request.user) or
        (is_physio(request.user) and plan.created_by == request.user)
    ):
        return redirect("plan_list")

    return render(request, "plan_detail.html", {
        "plan": plan,
        "logs": SessionLog.objects.filter(plan=plan).order_by("-date"),
        "analysis_sessions": AnalysisSession.objects.filter(plan=plan).order_by("-started_at"),
        "plan_exercises": plan.plan_exercises.select_related("exercise").order_by("order", "id"),
        "is_physio": is_physio(request.user),
    })


@login_required
@user_passes_test(is_physio)
def plan_create(request):
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.created_by = request.user
            plan.save()
            form.save_m2m()
            save_plan_prescriptions(plan, form.cleaned_data["exercises"], request.POST)
            return redirect("plan_list")
    else:
        initial = {}
        client_id = request.GET.get("client_id")
        if client_id:
            initial["user"] = client_id
        form = PlanForm(initial=initial)

    return render(request, "plan_form.html", {
        "form": form,
        "title": "Create Plan",
        "exercise_rows": build_exercise_prescription_rows(
            post_data=request.POST if request.method == "POST" else None
        ),
    })


@login_required
@user_passes_test(is_physio)
def physio_client_detail(request, client_id):
    client = get_object_or_404(User, pk=client_id)
    plans = Plan.objects.filter(created_by=request.user, user=client).order_by("-created_at")
    return render(request, "physio_client_detail.html", {
        "client": client,
        "plans": plans,
    })


@login_required
@user_passes_test(is_physio)
def plan_edit(request, pk):
    plan = get_object_or_404(Plan, pk=pk, created_by=request.user)

    if request.method == "POST":
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            updated_plan = form.save()
            save_plan_prescriptions(updated_plan, form.cleaned_data["exercises"], request.POST)
            return redirect("plan_detail", pk=plan.pk)
    else:
        form = PlanForm(instance=plan)

    return render(request, "plan_form.html", {
        "form": form,
        "title": "Edit Plan",
        "exercise_rows": build_exercise_prescription_rows(
            plan,
            request.POST if request.method == "POST" else None,
        ),
    })


@login_required
@user_passes_test(is_physio)
def plan_delete(request, pk):
    plan = get_object_or_404(Plan, pk=pk, created_by=request.user)
    if request.method == "POST":
        plan.delete()
        return redirect("plan_list")

    return render(request, "plan_confirm_delete.html", {"plan": plan})
