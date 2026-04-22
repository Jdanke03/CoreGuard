from django.db import models
from django.contrib.auth.models import User


class Exercise(models.Model):
    # Simple library of exercises used in plans
    BODY_AREAS = [
        ('Legs', 'Legs'),
        ('Knee', 'Knee'),
        ('Hips', 'Hips'),
        ('Shoulder', 'Shoulder'),
        ('Arms', 'Arms'),
        ('Chest', 'Chest'),
        ('Back', 'Back'),
        ('Core', 'Core'),
        ('Neck', 'Neck'),
        ('Ankle', 'Ankle'),
        ('Other', 'Other'),
    ]

    DIFFICULTIES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]

    # Basic exercise metadata
    name = models.CharField(max_length=100)
    description = models.TextField()
    body_area = models.CharField(max_length=20, choices=BODY_AREAS)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES)
    image = models.ImageField(upload_to='exercises/', blank=True, null=True)
    video_url = models.URLField(blank=True, default='')


    def __str__(self):
        return self.name

class Plan(models.Model):
    # The patient / end user the plan is assigned to
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # The physio who created the plan (can be null for legacy data)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plans_created'
    )

    # Plan details and content
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    duration_weeks = models.PositiveIntegerField(default=6)
    exercises = models.ManyToManyField(Exercise, blank=True)
    # Flag that tells the client they must do live analysis
    requires_analysis = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class PlanExercise(models.Model):
    # Stores the exercise prescription details for a specific plan
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='plan_exercises')
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    sets = models.PositiveIntegerField(default=3)
    reps = models.PositiveIntegerField(default=10)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('plan', 'exercise')

    def __str__(self):
        return f"{self.plan.name} - {self.exercise.name} ({self.sets}x{self.reps})"



class SessionLog(models.Model):
    # Progress logs submitted by clients for a plan
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    pain_level = models.IntegerField()
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Log for {self.plan.name} on {self.date} ({self.user.username})"


class AnalysisSession(models.Model):
    # Live analysis session linked to a client and (optionally) a plan
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analysis_sessions')
    # Nullable so older sessions still work even if a plan was deleted
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    # Physio responsible for the client (optional, used for tracking)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analysis_sessions_created'
    )
    # Basic session meta
    exercise_name = models.CharField(max_length=100, default='Squat')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    # Captured metrics summary from the live analysis
    total_frames = models.IntegerField(default=0)
    flagged_frames = models.IntegerField(default=0)
    summary_json = models.TextField(blank=True)
    # Physio feedback workflow
    physio_feedback_draft = models.TextField(blank=True)
    physio_feedback = models.TextField(blank=True)
    feedback_shared = models.BooleanField(default=False)
    feedback_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.exercise_name} session ({self.client.username})"
