from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic.edit import CreateView
from django.contrib.auth.views import LoginView
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import StreamingHttpResponse, HttpResponse
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db.models import Count, Q
import os
import urllib.request
import urllib.error
import json
import math

from .models import Exercise, Plan, PlanExercise, SessionLog, AnalysisSession
from .forms import UserSignupForm, PlanForm, SessionLogForm, ExerciseForm, AnalysisFeedbackForm

# Role helpers
def is_physio(user):
    # Physio users are grouped under "Physio"
    return user.is_authenticated and user.groups.filter(name="Physio").exists()

def is_not_physio(user):
    # Non-physio users are normal clients
    return not user.groups.filter(name="Physio").exists()


def _build_exercise_prescription_rows(plan=None, post_data=None):
    # Builds one row per exercise so the plan form can collect sets and reps
    existing = {}
    if plan is not None:
        existing = {
            item.exercise_id: item
            for item in plan.plan_exercises.select_related('exercise')
        }

    rows = []
    for exercise in Exercise.objects.order_by('name'):
        item = existing.get(exercise.id)
        rows.append({
            'exercise': exercise,
            'sets_name': f'exercise_{exercise.id}_sets',
            'reps_name': f'exercise_{exercise.id}_reps',
            'sets_value': post_data.get(f'exercise_{exercise.id}_sets') if post_data else (item.sets if item else 3),
            'reps_value': post_data.get(f'exercise_{exercise.id}_reps') if post_data else (item.reps if item else 10),
        })
    return rows


def _save_plan_prescriptions(plan, selected_exercises, post_data):
    # Sync the per-exercise prescription rows after the main plan is saved
    selected_ids = [exercise.id for exercise in selected_exercises]
    PlanExercise.objects.filter(plan=plan).exclude(exercise_id__in=selected_ids).delete()

    for index, exercise in enumerate(selected_exercises):
        sets_raw = post_data.get(f'exercise_{exercise.id}_sets', '3')
        reps_raw = post_data.get(f'exercise_{exercise.id}_reps', '10')

        try:
            sets = max(1, int(sets_raw))
        except (TypeError, ValueError):
            sets = 3

        try:
            reps = max(1, int(reps_raw))
        except (TypeError, ValueError):
            reps = 10

        PlanExercise.objects.update_or_create(
            plan=plan,
            exercise=exercise,
            defaults={
                'sets': sets,
                'reps': reps,
                'order': index,
            }
        )


# Home
def home(request):
    # Logged-out users see a dedicated landing page
    if not request.user.is_authenticated:
        return render(request, 'landing.html')

    # Logged-in users stay on the existing dashboard-style home page
    exercises = Exercise.objects.all()[:3]
    is_physio_user = request.user.groups.filter(name="Physio").exists()
    context = {
        'exercises': exercises,
        'is_physio': is_physio_user,
    }

    if is_physio_user:
        physio_plans = Plan.objects.filter(created_by=request.user)
        physio_sessions = AnalysisSession.objects.filter(plan__created_by=request.user).select_related('client', 'plan')
        client_ids = physio_plans.values_list('user_id', flat=True).distinct()

        feedback_sent = physio_sessions.filter(feedback_shared=True).count()
        awaiting_review = physio_sessions.filter(feedback_shared=False).count()

        sessions_per_client = list(
            physio_sessions.values('client__username')
            .annotate(total=Count('id'))
            .order_by('-total', 'client__username')[:6]
        )

        clients_needing_attention = (
            physio_sessions.filter(feedback_shared=False)
            .order_by('-flagged_frames', '-started_at')[:4]
        )

        recent_sessions = physio_sessions.order_by('-started_at')[:5]

        context.update({
            'physio_total_clients': len(set(client_ids)),
            'physio_active_plans': physio_plans.count(),
            'physio_awaiting_review': awaiting_review,
            'physio_feedback_sent': feedback_sent,
            'recent_sessions': recent_sessions,
            'clients_needing_attention': clients_needing_attention,
            'feedback_chart_data': json.dumps({
                'labels': ['Awaiting review', 'Feedback sent'],
                'values': [awaiting_review, feedback_sent],
            }),
            'sessions_per_client_data': json.dumps({
                'labels': [row['client__username'] for row in sessions_per_client],
                'values': [row['total'] for row in sessions_per_client],
            }),
        })
    else:
        client_plans = Plan.objects.filter(user=request.user).order_by('-created_at')
        client_logs = SessionLog.objects.filter(user=request.user)
        client_sessions = AnalysisSession.objects.filter(client=request.user).select_related('plan').order_by('-started_at')
        feedback_ready = client_sessions.filter(feedback_shared=True).count()
        pending_review = client_sessions.filter(feedback_shared=False).count()
        latest_feedback_session = client_sessions.filter(feedback_shared=True).first()
        latest_analysis_session = client_sessions.first()

        context.update({
            'client_active_plans': client_plans.count(),
            'client_sessions_logged': client_logs.count(),
            'client_analyses_completed': client_sessions.count(),
            'client_feedback_ready': feedback_ready,
            'latest_feedback_session': latest_feedback_session,
            'latest_analysis_session': latest_analysis_session,
            'client_next_action': (
                'Open your latest feedback to review your physiotherapist’s comments.'
                if latest_feedback_session else
                'Complete a live analysis session when your plan requires it.'
            ),
            'client_status_chart_data': json.dumps({
                'labels': ['Feedback ready', 'Awaiting review'],
                'values': [feedback_ready, pending_review],
            }),
        })

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
    from .forms import ProfileEmailForm

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

# Exercises (physio/admin only for create/delete)
@login_required
@user_passes_test(lambda u: u.is_staff or is_physio(u))
def exercise_create(request):
    # Create a new exercise in the library
    if request.method == "POST":
        form = ExerciseForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('exercise_list')
    else:
        # GET: blank form
        form = ExerciseForm()

    return render(request, 'exercise_form.html', {'form': form})



@login_required
def exercise_list(request):
    # List all exercises for everyone
    exercises = Exercise.objects.all()

    # Only physios/admins can add new exercises
    can_add_exercise = (
        request.user.is_authenticated and
        (request.user.is_staff or is_physio(request.user))
    )

    # Pass a flag so the template can show/hide the add button
    return render(request, 'exercise_list.html', {
        'exercises': exercises,
        'can_add_exercise': can_add_exercise,
    })

def exercise_detail(request, pk):
    # Show details for a single exercise
    exercise = get_object_or_404(Exercise, pk=pk)
    return render(request, 'exercise_detail.html', {
        'exercise': exercise,
        # Used to hide controls for clients
        'is_physio': is_physio(request.user),
    })


@login_required
@user_passes_test(lambda u: u.is_staff or is_physio(u))
def exercise_delete(request, pk):
    # Confirm + delete an exercise
    exercise = get_object_or_404(Exercise, pk=pk)
    if request.method == "POST":
        exercise.delete()
        return redirect('exercise_list')
    # GET: confirm screen
    return render(request, 'exercise_confirm_delete.html', {'exercise': exercise})


# Plans (list, detail, create, edit, delete)
@login_required
def plan_list(request):
    # Shared view: physios see their clients, clients see their plans
    client_id = None
    if is_physio(request.user):
        # Physio: show clients they created plans for
        client_ids = list(
            Plan.objects.filter(created_by=request.user)
            .values_list('user_id', flat=True)
            .distinct()
        )
        # Build a client list for the physio dashboard
        clients = User.objects.filter(id__in=client_ids).order_by('username')
        return render(request, 'physio_clients.html', {
            'clients': clients,
        })
    else:
        # Normal user: show plans assigned to them
        plans = Plan.objects.filter(user=request.user).order_by('-created_at')
        clients = None

    # Client view uses plan_list.html
    return render(request, 'plan_list.html', {
        'plans': plans,
        'clients': clients,
        'selected_client_id': client_id if is_physio(request.user) else '',
    })

@login_required
def plan_detail(request, pk):
    # Show plan details (with logs + analysis sessions)
    plan = get_object_or_404(Plan, pk=pk)

    # Permissions: patient or physio who created it
    if not (
        (not is_physio(request.user) and plan.user == request.user) or
        (is_physio(request.user) and plan.created_by == request.user)
    ):
        # Guard against unauthorized access
        return redirect('plan_list')

    # Load session logs and analysis sessions linked to this plan
    logs = SessionLog.objects.filter(plan=plan).order_by('-date')
    analysis_sessions = AnalysisSession.objects.filter(plan=plan).order_by('-started_at')
    plan_exercises = plan.plan_exercises.select_related('exercise').order_by('order', 'id')

    return render(request, 'plan_detail.html', {
        'plan': plan,
        'logs': logs,
        'analysis_sessions': analysis_sessions,
        'plan_exercises': plan_exercises,
        # Used to control which actions appear in the template
        'is_physio': is_physio(request.user),
    })


@login_required
@user_passes_test(is_physio)
def plan_create(request):
    # Physio creates a plan and assigns it to a client
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            # Link this plan to the physio who created it
            plan.created_by = request.user
            plan.save()
            form.save_m2m()
            _save_plan_prescriptions(plan, form.cleaned_data['exercises'], request.POST)
            return redirect('plan_list')
    else:
        # Pre-fill the client if coming from a physio client page
        initial = {}
        client_id = request.GET.get('client_id')
        if client_id:
            initial['user'] = client_id
        form = PlanForm(initial=initial)

    return render(request, 'plan_form.html', {
        'form': form,
        'title': 'Create Plan',
        'exercise_rows': _build_exercise_prescription_rows(post_data=request.POST if request.method == "POST" else None),
    })


@login_required
@user_passes_test(is_physio)
def physio_client_detail(request, client_id):
    # Physio-focused page for a single client
    client = get_object_or_404(User, pk=client_id)
    # Only show plans created by this physio for this client
    plans = Plan.objects.filter(created_by=request.user, user=client).order_by('-created_at')
    return render(request, 'physio_client_detail.html', {
        'client': client,
        'plans': plans,
    })



@login_required
@user_passes_test(is_physio)
def plan_edit(request, pk):
    # Physio can edit a plan they created
    plan = get_object_or_404(Plan, pk=pk, created_by=request.user)

    if request.method == "POST":
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            updated_plan = form.save()
            _save_plan_prescriptions(updated_plan, form.cleaned_data['exercises'], request.POST)
            return redirect('plan_detail', pk=plan.pk)
    else:
        # GET: fill the form with current plan data
        form = PlanForm(instance=plan)

    return render(request, 'plan_form.html', {
        'form': form,
        'title': 'Edit Plan',
        'exercise_rows': _build_exercise_prescription_rows(plan, request.POST if request.method == "POST" else None),
    })



@login_required
@user_passes_test(is_physio)
def plan_delete(request, pk):
    # Physio can delete a plan they created
    plan = get_object_or_404(Plan, pk=pk, created_by=request.user)
    if request.method == "POST":
        plan.delete()
        return redirect('plan_list')

    # GET: confirm delete screen
    return render(request, 'plan_confirm_delete.html', {'plan': plan})



# Progress logs (clients only)
@login_required
@user_passes_test(is_not_physio)
def log_list(request):
    # This view is client-only by default (guarded above)
    if is_physio(request.user):
        # All logs for plans created by this physio
        logs = SessionLog.objects.filter(plan__created_by=request.user).order_by('-date')
    else:
        # Normal user: their own logs
        logs = SessionLog.objects.filter(user=request.user).order_by('-date')
    # Render the log list page
    return render(request, 'log_list.html', {'logs': logs})


@login_required
@user_passes_test(is_not_physio)
def log_create(request, plan_id=None):
    # Client creates a progress log linked to a plan
    initial = {}
    plan = None

    if plan_id is not None:
        # Only allow patients to log for their own assigned plans
        plan = get_object_or_404(Plan, pk=plan_id)
        if not is_physio(request.user) and plan.user != request.user:
            return redirect('plan_list')
        # Pre-select the plan on the form
        initial['plan'] = plan

    if request.method == "POST":
        form = SessionLogForm(request.POST, user=request.user)
        if form.is_valid():
            log = form.save(commit=False)
            log.user = request.user
            log.save()
            # After saving, route back to the plan or log list
            if plan:
                return redirect('plan_detail', pk=plan.pk)
            return redirect('log_list')
    else:
        # GET: show empty form (or pre-filled plan)
        form = SessionLogForm(user=request.user, initial=initial)

    return render(request, 'log_form.html', {'form': form})


# Live analysis (client-initiated)
@login_required
@user_passes_test(is_not_physio)
def analysis_start(request, plan_id=None):
    # Start page: choose a plan that requires analysis
    plan = None
    if plan_id is not None:
        plan = get_object_or_404(Plan, pk=plan_id, user=request.user)
    else:
        plan = None

    # Only show plans flagged for analysis
    available_plans = Plan.objects.filter(user=request.user, requires_analysis=True).order_by('-created_at')
    if request.method == "POST":
        selected_plan_id = request.POST.get("plan_id")
        if selected_plan_id:
            # Ensure the plan is owned by the client and requires analysis
            plan = get_object_or_404(Plan, pk=selected_plan_id, user=request.user, requires_analysis=True)

        # Create the analysis session and link it to the plan
        session = AnalysisSession.objects.create(
            client=request.user,
            created_by=None,
            exercise_name="Squat",
            plan=plan
        )
        # Redirect into the live tracking view
        return redirect('analysis_live', session_id=session.pk)

    return render(request, 'start_session.html', {
        'plan': plan,
        'available_plans': available_plans,
    })


@login_required
def analysis_live(request, session_id):
    # Live camera page (stream comes from analysis_stream)
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.client != request.user and not is_physio(request.user):
        return redirect('home')

    return render(request, 'analysis_live.html', {
        'session': session,
    })


@login_required
def analysis_stream(request, session_id):
    # Streaming endpoint used by the <img> tag on the live page
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.client != request.user and not is_physio(request.user):
        return redirect('home')

    # External dependencies are required for live analysis
    try:
        import cv2
        import mediapipe as mp
    except Exception:
        return HttpResponse("MediaPipe or OpenCV not installed.", status=503)

    # Open the webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return HttpResponse("Camera not available.", status=503)

    # Initialize pose pipeline + drawing helpers
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    # Running counters for this session
    total_frames = 0
    flagged_frames = 0
    rule_counts = {
        'knee_valgus': 0,
        'shallow_depth': 0,
        'forward_lean': 0,
    }
    angle_sums = {
        'knee': 0.0,
        'hip': 0.0,
    }
    angle_counts = {
        'knee': 0,
        'hip': 0,
    }

    # Small helper to compute a 2D angle
    def _angle(a, b, c):
        ba = (a[0] - b[0], a[1] - b[1])
        bc = (c[0] - b[0], c[1] - b[1])
        dot = ba[0] * bc[0] + ba[1] * bc[1]
        mag_ba = math.hypot(ba[0], ba[1])
        mag_bc = math.hypot(bc[0], bc[1])
        if mag_ba == 0 or mag_bc == 0:
            return None
        cos_angle = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
        return math.degrees(math.acos(cos_angle))

    # Generator yields frames for StreamingHttpResponse
    def frame_generator():
        frame_tick = 0
        try:
            with mp_pose.Pose(
                static_image_mode=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            ) as pose:
                while True:
                    success, frame = cap.read()
                    if not success:
                        break

                    nonlocal total_frames, flagged_frames
                    # Update counters on every frame
                    total_frames += 1
                    frame_tick += 1

                    # Periodically check if the session was ended
                    if frame_tick % 10 == 0:
                        ended = AnalysisSession.objects.filter(pk=session.pk, ended_at__isnull=False).exists()
                        if ended:
                            break

                    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = pose.process(image)

                    # Copy frame for drawing
                    output = frame.copy()
                    if results.pose_landmarks:
                        # Draw pose overlay for the client preview
                        mp_drawing.draw_landmarks(
                            output,
                            results.pose_landmarks,
                            mp_pose.POSE_CONNECTIONS
                        )

                        lms = results.pose_landmarks.landmark
                        lm = mp_pose.PoseLandmark

                        def _get_point(landmark):
                            return (landmark.x, landmark.y, landmark.visibility)

                        # Pull keypoints needed for simple rules
                        left_hip = _get_point(lms[lm.LEFT_HIP])
                        left_knee = _get_point(lms[lm.LEFT_KNEE])
                        left_ankle = _get_point(lms[lm.LEFT_ANKLE])
                        left_shoulder = _get_point(lms[lm.LEFT_SHOULDER])

                        right_hip = _get_point(lms[lm.RIGHT_HIP])
                        right_knee = _get_point(lms[lm.RIGHT_KNEE])
                        right_ankle = _get_point(lms[lm.RIGHT_ANKLE])
                        right_shoulder = _get_point(lms[lm.RIGHT_SHOULDER])

                        # Only process when the main joints are visible
                        visibility_threshold = 0.6
                        keypoints_visible = all([
                            left_hip[2] > visibility_threshold,
                            left_knee[2] > visibility_threshold,
                            left_ankle[2] > visibility_threshold,
                            right_hip[2] > visibility_threshold,
                            right_knee[2] > visibility_threshold,
                            right_ankle[2] > visibility_threshold,
                            left_shoulder[2] > visibility_threshold,
                            right_shoulder[2] > visibility_threshold,
                        ])

                        if keypoints_visible:
                            # Reduce to just x/y for our calculations
                            left_hip_xy = (left_hip[0], left_hip[1])
                            left_knee_xy = (left_knee[0], left_knee[1])
                            left_ankle_xy = (left_ankle[0], left_ankle[1])
                            left_shoulder_xy = (left_shoulder[0], left_shoulder[1])

                            right_hip_xy = (right_hip[0], right_hip[1])
                            right_knee_xy = (right_knee[0], right_knee[1])
                            right_ankle_xy = (right_ankle[0], right_ankle[1])
                            right_shoulder_xy = (right_shoulder[0], right_shoulder[1])

                            # Compute angles used in the simple rules
                            knee_angle_left = _angle(left_hip_xy, left_knee_xy, left_ankle_xy)
                            knee_angle_right = _angle(right_hip_xy, right_knee_xy, right_ankle_xy)
                            hip_angle_left = _angle(left_shoulder_xy, left_hip_xy, left_knee_xy)
                            hip_angle_right = _angle(right_shoulder_xy, right_hip_xy, right_knee_xy)

                            # Rule checks (simple thresholds)
                            knee_valgus = False
                            if left_knee_xy[0] > left_ankle_xy[0] + 0.03:
                                knee_valgus = True
                            if right_knee_xy[0] < right_ankle_xy[0] - 0.03:
                                knee_valgus = True

                            shallow_depth = False
                            if left_hip_xy[1] <= left_knee_xy[1] - 0.02:
                                shallow_depth = True
                            if right_hip_xy[1] <= right_knee_xy[1] - 0.02:
                                shallow_depth = True

                            forward_lean = False
                            if hip_angle_left is not None and hip_angle_left < 60:
                                forward_lean = True
                            if hip_angle_right is not None and hip_angle_right < 60:
                                forward_lean = True

                            # Count breaches for this frame
                            breached = False
                            if knee_valgus:
                                rule_counts['knee_valgus'] += 1
                                breached = True
                            if shallow_depth:
                                rule_counts['shallow_depth'] += 1
                                breached = True
                            if forward_lean:
                                rule_counts['forward_lean'] += 1
                                breached = True
                            if breached:
                                flagged_frames += 1

                            # Track running averages for key angles
                            angles = [a for a in [knee_angle_left, knee_angle_right] if a is not None]
                            if angles:
                                angle_sums['knee'] += sum(angles) / len(angles)
                                angle_counts['knee'] += 1
                            hip_angles = [a for a in [hip_angle_left, hip_angle_right] if a is not None]
                            if hip_angles:
                                angle_sums['hip'] += sum(hip_angles) / len(hip_angles)
                                angle_counts['hip'] += 1

                    # Periodically persist a summary for the live session
                    if frame_tick % 10 == 0:
                        summary = {
                            'rules': rule_counts,
                            'angles': {
                                'knee_avg': round(angle_sums['knee'] / angle_counts['knee'], 1) if angle_counts['knee'] else None,
                                'hip_avg': round(angle_sums['hip'] / angle_counts['hip'], 1) if angle_counts['hip'] else None,
                            },
                            'total_frames': total_frames,
                            'flagged_frames': flagged_frames,
                        }
                        AnalysisSession.objects.filter(pk=session.pk).update(
                            total_frames=total_frames,
                            flagged_frames=flagged_frames,
                            summary_json=json.dumps(summary)
                        )

                    # Encode and yield the frame to the browser
                    encoded, buffer = cv2.imencode('.jpg', output)
                    if not encoded:
                        continue

                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' +
                           buffer.tobytes() + b'\r\n')
        finally:
            # Always release the camera
            cap.release()
            if total_frames > 0:
                # Final summary save after the stream ends
                summary = {
                    'rules': rule_counts,
                        'angles': {
                            'knee_avg': round(angle_sums['knee'] / angle_counts['knee'], 1) if angle_counts['knee'] else None,
                            'hip_avg': round(angle_sums['hip'] / angle_counts['hip'], 1) if angle_counts['hip'] else None,
                        },
                    'total_frames': total_frames,
                    'flagged_frames': flagged_frames,
                }
                AnalysisSession.objects.filter(pk=session.pk).update(
                    total_frames=total_frames,
                    flagged_frames=flagged_frames,
                    summary_json=json.dumps(summary)
                )

    # Stream the multipart JPEG response
    return StreamingHttpResponse(
        frame_generator(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )


@login_required
def analysis_summary(request, session_id):
    # Summary page for a completed analysis session
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.client != request.user and not is_physio(request.user):
        return redirect('home')

    # Physio feedback handling (draft + submit)
    feedback_form = None
    if is_physio(request.user):
        if session.feedback_shared:
            # Feedback already sent; form is hidden
            feedback_form = None
        else:
            if request.method == "POST" and "generate_draft" in request.POST:
                # Ask external AI to generate a draft
                draft = _generate_ai_draft(session)
                session.physio_feedback_draft = draft
                session.save()
                initial = {}
                if not session.physio_feedback:
                    initial['physio_feedback'] = draft
                feedback_form = AnalysisFeedbackForm(instance=session, initial=initial)
            elif request.method == "POST":
                # Physio finalizes the feedback
                feedback_form = AnalysisFeedbackForm(request.POST, instance=session)
                if feedback_form.is_valid():
                    updated = feedback_form.save(commit=False)
                    updated.feedback_shared = True
                    from django.utils import timezone
                    updated.feedback_at = timezone.now()
                    updated.save()
                    _send_feedback_email(updated)
                    messages.success(
                        request,
                        "Feedback has been shared on CoreGuard and sent to the client by email."
                    )
                    return redirect('analysis_summary', session_id=updated.pk)
            else:
                # GET: show the form (pre-filled if a draft exists)
                initial = {}
                if session.physio_feedback_draft and not session.physio_feedback:
                    initial['physio_feedback'] = session.physio_feedback_draft
                feedback_form = AnalysisFeedbackForm(instance=session, initial=initial)

    # Parse the saved summary JSON for display
    summary = {}
    if session.summary_json:
        try:
            summary = json.loads(session.summary_json)
        except Exception:
            summary = {}

    # Render summary and feedback
    return render(request, 'analysis_summary.html', {
        'session': session,
        'summary': summary,
        'feedback_form': feedback_form,
        'is_physio': is_physio(request.user),
    })

# AI draft helper (OpenAI)
def _generate_ai_draft(session):
    # API key pulled from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "AI draft unavailable (missing API key)."

    # Build a compact stats bundle for the prompt
    summary = {}
    if session.summary_json:
        try:
            summary = json.loads(session.summary_json)
        except Exception:
            summary = {}

    rules = summary.get('rules', {})
    angles = summary.get('angles', {})
    total_frames = summary.get('total_frames', session.total_frames or 0)
    flagged_frames = summary.get('flagged_frames', session.flagged_frames or 0)

    # External prompt to generate a short, friendly draft
    prompt = (
        "Write a short, friendly physio feedback draft (3-4 sentences) based on these squat "
        "analysis stats. Keep it non-clinical and encouraging. Mention the most important 1-2 issues.\n\n"
        f"Exercise: {session.exercise_name}\n"
        f"Total frames: {total_frames}\n"
        f"Flagged frames: {flagged_frames}\n"
        f"Knee cave-in count: {rules.get('knee_valgus', 0)}\n"
        f"Shallow depth count: {rules.get('shallow_depth', 0)}\n"
        f"Forward lean count: {rules.get('forward_lean', 0)}\n"
        f"Avg knee angle: {angles.get('knee_avg', 'n/a')}\n"
        f"Avg hip angle: {angles.get('hip_avg', 'n/a')}\n"
    )

    # Minimal JSON payload for the external API
    payload = {
        "model": "gpt-4.1-mini",
        "input": prompt,
    }

    # Prepare the request
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    # Call the external service (fail safely)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return "AI draft unavailable (request failed)."

    # Prefer the simple output_text field if present
    output_text = data.get("output_text")
    if output_text:
        return output_text.strip()

    # Fallback: walk the response structure
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                return text.strip()

    # If no text found, show a generic message
    return "AI draft unavailable (no text returned)."


def _send_feedback_email(session):
    # Email the final physio feedback to the client
    if not session.client or not session.client.email:
        return False

    context = {
        "session": session,
        "client": session.client,
    }
    html_body = render_to_string("analysis_email.html", context)
    text_body = strip_tags(html_body)

    subject = f"CoreGuard feedback for {session.exercise_name}"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [session.client.email]

    msg = EmailMultiAlternatives(subject, text_body, from_email, recipient_list)
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    return True


@login_required
def analysis_stop(request, session_id):
    # Stop the live analysis session and finalize it
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.client != request.user and not is_physio(request.user):
        return redirect('home')

    # Mark end time once (idempotent)
    if session.ended_at is None:
        from django.utils import timezone
        session.ended_at = timezone.now()
        session.save()

    # Send the user to the summary page
    return redirect('analysis_summary', session_id=session.pk)


@login_required
def analysis_cancel(request, session_id):
    # Cancel an in-progress analysis session (client action)
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.client != request.user and not is_physio(request.user):
        return redirect('home')

    if request.method == "POST":
        # Delete the session and return to start
        session.delete()
        return redirect('analysis_start')

    # GET: show a confirmation prompt
    return render(request, 'analysis_cancel.html', {'session': session})


@login_required
@user_passes_test(is_physio)
def analysis_sessions_physio(request):
    # Physio view: list analysis sessions for their clients
    client_ids = Plan.objects.filter(created_by=request.user).values_list('user_id', flat=True)
    client_id = request.GET.get('client')

    # Base queryset: sessions for any of this physio's clients
    sessions = AnalysisSession.objects.filter(client_id__in=client_ids).order_by('-started_at')
    if client_id:
        # Optional filter by selected client
        sessions = sessions.filter(client_id=client_id)

    # Build the client filter dropdown
    clients = User.objects.filter(id__in=client_ids).order_by('username')
    return render(request, 'analysis_sessions_physio.html', {
        'sessions': sessions,
        'clients': clients,
        'selected_client_id': client_id or '',
    })
