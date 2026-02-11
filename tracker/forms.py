from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Plan, Exercise, SessionLog


class UserSignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

# Plan Creation
class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = ("user", "name", "description", "exercises")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "exercises": forms.CheckboxSelectMultiple,
        }


  # Progress Creation (logging)
class SessionLogForm(forms.ModelForm):
    class Meta:
        model = SessionLog
        fields = ("plan", "pain_level", "notes")
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    # Makes sure users only see their own plans when logging a session
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # Only show the current user's plans in the dropdown
        if user is not None:
            self.fields["plan"].queryset = Plan.objects.filter(user=user)


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = ("name", "description", "body_area", "difficulty", "image")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
