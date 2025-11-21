from django.contrib import admin
from .models import Exercise, Plan

@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('name', 'body_area', 'difficulty')

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    list_filter = ('user',)

class SessionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'date', 'pain_level')
    list_filter = ('user', 'plan', 'date')