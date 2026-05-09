from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SessionLogForm
from .models import Plan, SessionLog
from .services.roles import is_not_physio, is_physio


@login_required
@user_passes_test(is_not_physio)
def log_list(request):
    logs = SessionLog.objects.filter(user=request.user).order_by("-date")
    return render(request, "log_list.html", {"logs": logs})


@login_required
@user_passes_test(is_not_physio)
def log_create(request, plan_id=None):
    initial = {}
    plan = None

    if plan_id is not None:
        plan = get_object_or_404(Plan, pk=plan_id)
        if not is_physio(request.user) and plan.user != request.user:
            return redirect("plan_list")
        initial["plan"] = plan

    if request.method == "POST":
        form = SessionLogForm(request.POST, user=request.user)
        if form.is_valid():
            log = form.save(commit=False)
            log.user = request.user
            log.save()
            if plan:
                return redirect("plan_detail", pk=plan.pk)
            return redirect("log_list")
    else:
        form = SessionLogForm(user=request.user, initial=initial)

    return render(request, "log_form.html", {"form": form})
