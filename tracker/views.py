from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic.edit import CreateView
from django.contrib.auth.views import LoginView  
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test

from .models import Exercise, Plan, SessionLog
from .forms import UserSignupForm, PlanForm, SessionLogForm, ExerciseForm

 # helper function for user roles
def is_physio(user):
    return user.is_authenticated and user.groups.filter(name="Physio").exists()

def home(request):
    # Show a few recent exercises
    exercises = Exercise.objects.all()[:3]

    # Check if the logged-in user is a physio
    is_physio_user = False
    if request.user.is_authenticated:
        is_physio_user = request.user.groups.filter(name="Physio").exists()

    return render(request, 'home.html', {
        'exercises': exercises,
        'is_physio': is_physio_user,
    })




 #User Auth
class UserSignupView(CreateView):
    model = User
    form_class = UserSignupForm
    template_name = 'register.html'  

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect('/')


class UserLoginView(LoginView):
    template_name = 'login.html'


def logout_user(request):
    logout(request)
    return redirect('/')

#details about each exercise + create exercise for physio or admin only
@login_required
@user_passes_test(lambda u: u.is_staff or is_physio(u))
def exercise_create(request):
    if request.method == "POST":
        form = ExerciseForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('exercise_list')
    else:
        form = ExerciseForm()

    return render(request, 'exercise_form.html', {'form': form})



@login_required
def exercise_list(request):
    exercises = Exercise.objects.all()

    can_add_exercise = (
        request.user.is_authenticated and
        (request.user.is_staff or is_physio(request.user))
    )

    return render(request, 'exercise_list.html', {
        'exercises': exercises,
        'can_add_exercise': can_add_exercise,
    })

def exercise_detail(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    return render(request, 'exercise_detail.html', {'exercise': exercise})


#plans - details - adding - deleting - editing 
@login_required
def plan_list(request):
    if is_physio(request.user):
        # Physio: show plans they created for patients
        plans = Plan.objects.filter(created_by=request.user).order_by('-created_at')
    else:
        # Normal user: show plans assigned to them
        plans = Plan.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'plan_list.html', {'plans': plans})

@login_required
def plan_detail(request, pk):
    plan = get_object_or_404(Plan, pk=pk)

    # Permissions: patient or physio who created it
    if not (
        (not is_physio(request.user) and plan.user == request.user) or
        (is_physio(request.user) and plan.created_by == request.user)
    ):
        return redirect('plan_list')

    logs = SessionLog.objects.filter(plan=plan).order_by('-date')

    return render(request, 'plan_detail.html', {
        'plan': plan,
        'logs': logs,
        'is_physio': is_physio(request.user),
    })


@login_required
@user_passes_test(is_physio)
def plan_create(request):
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            # links this plan to the physio who created it
            plan.created_by = request.user
            plan.save()
            form.save_m2m()
            return redirect('plan_list')
    else:
        form = PlanForm()

    return render(request, 'plan_form.html', {'form': form, 'title': 'Create Plan'})



@login_required
@user_passes_test(is_physio)
def plan_edit(request, pk):
    plan = get_object_or_404(Plan, pk=pk, created_by=request.user)

    if request.method == "POST":
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            return redirect('plan_detail', pk=plan.pk)
    else:
        form = PlanForm(instance=plan)

    return render(request, 'plan_form.html', {'form': form, 'title': 'Edit Plan'})



@login_required
@user_passes_test(is_physio)
def plan_delete(request, pk):
    plan = get_object_or_404(Plan, pk=pk, created_by=request.user)
    if request.method == "POST":
        plan.delete()
        return redirect('plan_list')

    return render(request, 'plan_confirm_delete.html', {'plan': plan})



#Progress and creating logs for plans
@login_required
def log_list(request):
    if is_physio(request.user):
        # All logs for plans created by this physio
        logs = SessionLog.objects.filter(plan__created_by=request.user).order_by('-date')
    else:
        # Normal user: their own logs
        logs = SessionLog.objects.filter(user=request.user).order_by('-date')
    return render(request, 'log_list.html', {'logs': logs})


@login_required
def log_create(request, plan_id=None):
    initial = {}
    plan = None

    if plan_id is not None:
        # Only allow patients to log for their own assigned plans
        plan = get_object_or_404(Plan, pk=plan_id)
        if not is_physio(request.user) and plan.user != request.user:
            return redirect('plan_list')
        initial['plan'] = plan

    if request.method == "POST":
        form = SessionLogForm(request.POST, user=request.user)
        if form.is_valid():
            log = form.save(commit=False)
            log.user = request.user
            log.save()
            if plan:
                return redirect('plan_detail', pk=plan.pk)
            return redirect('log_list')
    else:
        form = SessionLogForm(user=request.user, initial=initial)

    return render(request, 'log_form.html', {'form': form})

