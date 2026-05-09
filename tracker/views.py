from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic.edit import CreateView
from django.contrib.auth.views import LoginView
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import StreamingHttpResponse, HttpResponse
import time
import json
from .models import Plan, SessionLog, AnalysisSession
from .forms import UserSignupForm, PlanForm, SessionLogForm, AnalysisFeedbackForm, ProfileEmailForm
from .services.feedback import generate_ai_draft, send_feedback_email
from .services.analysis import build_summary, create_analysis_state, extract_squat_points, update_squat_analysis_state
from .services.plans import build_exercise_prescription_rows, save_plan_prescriptions
from .services.dashboard import build_home_context
from .services.roles import is_physio, is_not_physio

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
            save_plan_prescriptions(plan, form.cleaned_data['exercises'], request.POST)
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
        'exercise_rows': build_exercise_prescription_rows(post_data=request.POST if request.method == "POST" else None),
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
            save_plan_prescriptions(updated_plan, form.cleaned_data['exercises'], request.POST)
            return redirect('plan_detail', pk=plan.pk)
    else:
        # GET: fill the form with current plan data
        form = PlanForm(instance=plan)

    return render(request, 'plan_form.html', {
        'form': form,
        'title': 'Edit Plan',
        'exercise_rows': build_exercise_prescription_rows(plan, request.POST if request.method == "POST" else None),
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
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        return HttpResponse("Camera not available.", status=503)

    # Continuity Camera can take a moment to start returning frames on macOS.
    initial_frame = None
    for _ in range(20):
        success, frame = cap.read()
        if success and frame is not None:
            initial_frame = frame
            break
        time.sleep(0.15)
    if initial_frame is None:
        cap.release()
        return HttpResponse("Camera stream did not start.", status=503)

    # Initialize pose pipeline + drawing helpers
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    # Running counters for this session
    analysis_state = create_analysis_state()

    # Generator yields frames for StreamingHttpResponse
    def frame_generator():
        frame_tick = 0
        pending_frame = initial_frame
        read_failures = 0
        try:
            with mp_pose.Pose(
                static_image_mode=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            ) as pose:
                while True:
                    if pending_frame is not None:
                        frame = pending_frame
                        pending_frame = None
                        success = True
                    else:
                        success, frame = cap.read()
                    if not success:
                        read_failures += 1
                        if read_failures >= 15:
                            break
                        time.sleep(0.1)
                        continue
                    read_failures = 0

                    # Update counters on every frame
                    analysis_state["total_frames"] += 1
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

                        # Pull visible squat keypoints and update rule counters when usable.
                        squat_points = extract_squat_points(lms, lm)
                        if squat_points:
                            update_squat_analysis_state(analysis_state, squat_points)

                    # Periodically persist a summary for the live session
                    if frame_tick % 10 == 0:
                        summary = build_summary(analysis_state)
                        AnalysisSession.objects.filter(pk=session.pk).update(
                            total_frames=analysis_state["total_frames"],
                            flagged_frames=analysis_state["flagged_frames"],
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
            if analysis_state["total_frames"] > 0:
                # Final summary save after the stream ends
                summary = build_summary(analysis_state)
                AnalysisSession.objects.filter(pk=session.pk).update(
                    total_frames=analysis_state["total_frames"],
                    flagged_frames=analysis_state["flagged_frames"],
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
                draft = generate_ai_draft(session)
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
                    send_feedback_email(updated)
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
    status = request.GET.get('status')

    # Base queryset: sessions for any of this physio's clients
    sessions = AnalysisSession.objects.filter(client_id__in=client_ids).order_by('-started_at')
    if client_id:
        # Optional filter by selected client
        sessions = sessions.filter(client_id=client_id)
    if status == 'pending':
        sessions = sessions.filter(feedback_shared=False)
    elif status == 'sent':
        sessions = sessions.filter(feedback_shared=True)

    # Build the client filter dropdown
    clients = User.objects.filter(id__in=client_ids).order_by('username')
    return render(request, 'analysis_sessions_physio.html', {
        'sessions': sessions,
        'clients': clients,
        'selected_client_id': client_id or '',
        'selected_status': status or '',
    })
