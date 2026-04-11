from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('support/', views.faq_support, name='faq_support'),

    # Login section
    path('register/', views.UserSignupView.as_view(), name='register'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('profile/', views.profile_view, name='profile'),

    # Exercises
    path('exercises/', views.exercise_list, name='exercise_list'),
    path('exercises/<int:pk>/', views.exercise_detail, name='exercise_detail'),
    path('exercises/new/', views.exercise_create, name='exercise_create'),
    path('exercises/<int:pk>/delete/', views.exercise_delete, name='exercise_delete'),

    # Plans
    path('plans/', views.plan_list, name='plan_list'),
    path('plans/create/', views.plan_create, name='plan_create'),
    path('plans/<int:pk>/', views.plan_detail, name='plan_detail'),
    path('plans/<int:pk>/edit/', views.plan_edit, name='plan_edit'),
    path('plans/<int:pk>/delete/', views.plan_delete, name='plan_delete'),
    path('clients/<int:client_id>/', views.physio_client_detail, name='physio_client_detail'),

    # Logs
    path('logs/', views.log_list, name='log_list'),
    path('logs/create/', views.log_create, name='log_create'),
    path('logs/create/<int:plan_id>/', views.log_create, name='log_create_for_plan'),

    # Analysis
    path('analysis/start/', views.analysis_start, name='analysis_start'),
    path('analysis/start/<int:plan_id>/', views.analysis_start, name='analysis_start_for_plan'),
    path('analysis/live/<int:session_id>/', views.analysis_live, name='analysis_live'),
    path('analysis/stream/<int:session_id>/', views.analysis_stream, name='analysis_stream'),
    path('analysis/summary/<int:session_id>/', views.analysis_summary, name='analysis_summary'),
    path('analysis/stop/<int:session_id>/', views.analysis_stop, name='analysis_stop'),
    path('analysis/cancel/<int:session_id>/', views.analysis_cancel, name='analysis_cancel'),
    path('analysis/physio/', views.analysis_sessions_physio, name='analysis_sessions_physio'),
]
