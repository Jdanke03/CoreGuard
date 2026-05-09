from django.shortcuts import redirect, render
from django.views.generic.edit import CreateView
from django.contrib.auth.views import LoginView
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .forms import UserSignupForm, ProfileEmailForm
from .services.dashboard import build_home_context
from .services.roles import is_physio

# Home
def home(request):
    # Logged-out users see a dedicated landing page
    if not request.user.is_authenticated:
        return render(request, 'landing.html')

    # Logged-in dashboard data is assembled in a service so views stay thin.
    is_physio_user = request.user.groups.filter(name="Physio").exists()
    context = build_home_context(request.user, is_physio_user)
    return render(request, 'home.html', context)


def faq_support(request):
    # Public support page answering the main user journey questions
    return render(request, 'faq_support.html')
# User auth
class UserSignupView(CreateView):
    model = User
    form_class = UserSignupForm
    template_name = 'register.html'

    def form_valid(self, form):
        # Create account, then log in immediately
        user = form.save()
        login(self.request, user)
        # Send new users to the homepage
        return redirect('/')


class UserLoginView(LoginView):
    # Simple login view
    template_name = 'login.html'


def logout_user(request):
    # Log out and return to home
    logout(request)
    return redirect('/')

# Profile view (read-only details + email update)
@login_required
def profile_view(request):
    # Role label for display
    role = "Physio" if is_physio(request.user) else "Client"

    if request.method == "POST":
        form = ProfileEmailForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileEmailForm(instance=request.user)

    return render(request, 'profile.html', {
        'form': form,
        'role': role,
    })





