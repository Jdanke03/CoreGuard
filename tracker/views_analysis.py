import json
import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AnalysisFeedbackForm
from .models import AnalysisSession, Plan
from .services.analysis import build_summary, create_analysis_state, extract_squat_points, update_squat_analysis_state
from .services.feedback import generate_ai_draft, send_feedback_email
from .services.roles import is_not_physio, is_physio


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
