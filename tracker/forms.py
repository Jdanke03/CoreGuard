from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Plan, Exercise, SessionLog, AnalysisSession

# Pain levels shown as 1-10 buttons
PAIN_CHOICES = [(i, str(i)) for i in range(1, 11)]


class UserSignupForm(UserCreationForm):
    # Capture email at signup (required)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

# Plan creation (physio)
class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = ("user", "name", "duration_weeks", "description", "exercises", "requires_analysis")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "duration_weeks": forms.NumberInput(attrs={"min": 1, "max": 12, "type": "range", "class": "form-range"}),
            "exercises": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].label = "Client"
        self.fields["duration_weeks"].label = "Duration (weeks)"
        self.fields["exercises"].queryset = Exercise.objects.order_by("name")


# Progress creation (client logging)
class SessionLogForm(forms.ModelForm):
    class Meta:
        model = SessionLog
        fields = ("plan", "pain_level", "notes")
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "pain_level": forms.RadioSelect(choices=PAIN_CHOICES, attrs={"class": "btn-check"}),
        }

    # Makes sure users only see their own plans when logging a session
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # Only show the current user's plans in the dropdown
        if user is not None:
            self.fields["plan"].queryset = Plan.objects.filter(user=user)


class ExerciseForm(forms.ModelForm):
    # Exercise library form (physio/admin)
    class Meta:
        model = Exercise
        fields = ("name", "description", "body_area", "difficulty", "image")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class AnalysisFeedbackForm(forms.ModelForm):
    # Physio feedback text on analysis sessions
    class Meta:
        model = AnalysisSession
        fields = ("physio_feedback",)
        widgets = {
            "physio_feedback": forms.Textarea(attrs={"rows": 4}),
        }


class ProfileEmailForm(forms.ModelForm):
    # Simple profile form for updating email
    class Meta:
        model = User
        fields = ("email",)
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }
