from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic.edit import CreateView
from django.contrib.auth.views import LoginView  
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import StreamingHttpResponse, HttpResponse
import json
import math

from .models import Exercise, Plan, SessionLog, AnalysisSession
from .forms import UserSignupForm, PlanForm, SessionLogForm, ExerciseForm

 # helper function for user roles
def is_physio(user):
    return user.is_authenticated and user.groups.filter(name="Physio").exists()

def is_not_physio(user):
    return not user.groups.filter(name="Physio").exists()


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

#plans - details - adding - deleting - editing + Physio only users allowed create
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
        client_id = request.GET.get('client')
        client_ids = list(Plan.objects.filter(created_by=request.user).values_list('user_id', flat=True).distinct())
        if client_id and client_id.isdigit() and int(client_id) in client_ids:
            plans = plans.filter(user_id=int(client_id))
        clients = User.objects.filter(id__in=client_ids).order_by('username')
    else:
        # Normal user: show plans assigned to them
        plans = Plan.objects.filter(user=request.user).order_by('-created_at')
        clients = None

    return render(request, 'plan_list.html', {
        'plans': plans,
        'clients': clients,
        'selected_client_id': client_id if is_physio(request.user) else '',
    })

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
@user_passes_test(is_not_physio)
def log_list(request):
    if is_physio(request.user):
        # All logs for plans created by this physio
        logs = SessionLog.objects.filter(plan__created_by=request.user).order_by('-date')
    else:
        # Normal user: their own logs
        logs = SessionLog.objects.filter(user=request.user).order_by('-date')
    return render(request, 'log_list.html', {'logs': logs})


@login_required
@user_passes_test(is_not_physio)
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


@login_required
@user_passes_test(is_not_physio)
def analysis_start(request):
    if request.method == "POST":
        session = AnalysisSession.objects.create(
            client=request.user,
            created_by=None,
            exercise_name="Squat"
        )
        return redirect('analysis_live', session_id=session.pk)

    return render(request, 'start_session.html')


@login_required
def analysis_live(request, session_id):
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.client != request.user and not is_physio(request.user):
        return redirect('home')

    return render(request, 'analysis_live.html', {
        'session': session,
    })


@login_required
def analysis_stream(request, session_id):
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.client != request.user and not is_physio(request.user):
        return redirect('home')

    try:
        import cv2
        import mediapipe as mp
    except Exception:
        return HttpResponse("MediaPipe or OpenCV not installed.", status=503)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return HttpResponse("Camera not available.", status=503)

    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

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
                    total_frames += 1
                    frame_tick += 1

                    if frame_tick % 10 == 0:
                        ended = AnalysisSession.objects.filter(pk=session.pk, ended_at__isnull=False).exists()
                        if ended:
                            break

                    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = pose.process(image)

                    output = frame.copy()
                    if results.pose_landmarks:
                        mp_drawing.draw_landmarks(
                            output,
                            results.pose_landmarks,
                            mp_pose.POSE_CONNECTIONS
                        )

                        lms = results.pose_landmarks.landmark
                        lm = mp_pose.PoseLandmark

                        def _get_point(landmark):
                            return (landmark.x, landmark.y, landmark.visibility)

                        left_hip = _get_point(lms[lm.LEFT_HIP])
                        left_knee = _get_point(lms[lm.LEFT_KNEE])
                        left_ankle = _get_point(lms[lm.LEFT_ANKLE])
                        left_shoulder = _get_point(lms[lm.LEFT_SHOULDER])

                        right_hip = _get_point(lms[lm.RIGHT_HIP])
                        right_knee = _get_point(lms[lm.RIGHT_KNEE])
                        right_ankle = _get_point(lms[lm.RIGHT_ANKLE])
                        right_shoulder = _get_point(lms[lm.RIGHT_SHOULDER])

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
                            left_hip_xy = (left_hip[0], left_hip[1])
                            left_knee_xy = (left_knee[0], left_knee[1])
                            left_ankle_xy = (left_ankle[0], left_ankle[1])
                            left_shoulder_xy = (left_shoulder[0], left_shoulder[1])

                            right_hip_xy = (right_hip[0], right_hip[1])
                            right_knee_xy = (right_knee[0], right_knee[1])
                            right_ankle_xy = (right_ankle[0], right_ankle[1])
                            right_shoulder_xy = (right_shoulder[0], right_shoulder[1])

                            knee_angle_left = _angle(left_hip_xy, left_knee_xy, left_ankle_xy)
                            knee_angle_right = _angle(right_hip_xy, right_knee_xy, right_ankle_xy)
                            hip_angle_left = _angle(left_shoulder_xy, left_hip_xy, left_knee_xy)
                            hip_angle_right = _angle(right_shoulder_xy, right_hip_xy, right_knee_xy)

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

                            angles = [a for a in [knee_angle_left, knee_angle_right] if a is not None]
                            if angles:
                                angle_sums['knee'] += sum(angles) / len(angles)
                                angle_counts['knee'] += 1
                            hip_angles = [a for a in [hip_angle_left, hip_angle_right] if a is not None]
                            if hip_angles:
                                angle_sums['hip'] += sum(hip_angles) / len(hip_angles)
                                angle_counts['hip'] += 1

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

                    encoded, buffer = cv2.imencode('.jpg', output)
                    if not encoded:
                        continue

                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' +
                           buffer.tobytes() + b'\r\n')
        finally:
            cap.release()
            if total_frames > 0:
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

    return StreamingHttpResponse(
        frame_generator(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )


@login_required
def analysis_summary(request, session_id):
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.client != request.user and not is_physio(request.user):
        return redirect('home')

    summary = {}
    if session.summary_json:
        try:
            summary = json.loads(session.summary_json)
        except Exception:
            summary = {}

    rules = summary.get('rules', {})
    total_frames = summary.get('total_frames', session.total_frames or 0)
    feedback = []

    def rule_rate(key):
        if total_frames == 0:
            return 0
        return rules.get(key, 0) / total_frames

    knee_rate = rule_rate('knee_valgus')
    if knee_rate == 0:
        feedback.append("Great knee tracking throughout the squat.")
    elif knee_rate < 0.2:
        feedback.append("Occasional knee cave-in detected. Focus on keeping knees aligned over toes.")
    else:
        feedback.append("Knees drifted inward often. Try to actively push knees outward during the squat.")

    depth_rate = rule_rate('shallow_depth')
    if depth_rate == 0:
        feedback.append("Depth was consistent with hips dropping below the knees.")
    elif depth_rate < 0.2:
        feedback.append("Some reps were a little shallow. Aim to sit slightly deeper.")
    else:
        feedback.append("Depth was shallow in many frames. Try to lower hips below knee level.")

    lean_rate = rule_rate('forward_lean')
    if lean_rate == 0:
        feedback.append("Torso angle looked stable with a good upright posture.")
    elif lean_rate < 0.2:
        feedback.append("A bit of forward lean showed up at times. Keep your chest up.")
    else:
        feedback.append("Excess forward lean detected often. Focus on a more upright torso.")

    return render(request, 'analysis_summary.html', {
        'session': session,
        'summary': summary,
        'feedback': feedback,
    })


@login_required
def analysis_stop(request, session_id):
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.client != request.user and not is_physio(request.user):
        return redirect('home')

    if session.ended_at is None:
        from django.utils import timezone
        session.ended_at = timezone.now()
        session.save()

    return redirect('analysis_summary', session_id=session.pk)


@login_required
def analysis_cancel(request, session_id):
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.client != request.user and not is_physio(request.user):
        return redirect('home')

    if request.method == "POST":
        session.delete()
        return redirect('analysis_start')

    return render(request, 'analysis_cancel.html', {'session': session})


@login_required
@user_passes_test(is_physio)
def analysis_sessions_physio(request):
    client_ids = Plan.objects.filter(created_by=request.user).values_list('user_id', flat=True)
    client_id = request.GET.get('client')

    sessions = AnalysisSession.objects.filter(client_id__in=client_ids).order_by('-started_at')
    if client_id:
        sessions = sessions.filter(client_id=client_id)

    clients = User.objects.filter(id__in=client_ids).order_by('username')
    return render(request, 'analysis_sessions_physio.html', {
        'sessions': sessions,
        'clients': clients,
        'selected_client_id': client_id or '',
    })
