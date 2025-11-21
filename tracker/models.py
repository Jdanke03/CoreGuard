from django.db import models
from django.contrib.auth.models import User


class Exercise(models.Model):
    BODY_AREAS = [
        ('Legs', 'Legs'),
        ('Shoulder', 'Shoulder'),
        ('Back', 'Back'),
        ('Neck', 'Neck'),
        ('Other', 'Other'),
    ]

    DIFFICULTIES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField()
    body_area = models.CharField(max_length=20, choices=BODY_AREAS)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES)
    image = models.ImageField(upload_to='exercises/', blank=True, null=True)


    def __str__(self):
        return self.name

class Plan(models.Model):
    # The patient / end user the plan is for
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # The patient / end user the plan is for
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plans_created'
    )



    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    exercises = models.ManyToManyField(Exercise, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"
    

class SessionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    pain_level = models.IntegerField()
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Log for {self.plan.name} on {self.date} ({self.user.username})"