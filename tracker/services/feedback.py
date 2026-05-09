import json
import os
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def generate_ai_draft(session):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "AI draft unavailable (missing API key)."

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

    payload = {
        "model": "gpt-4.1-mini",
        "input": prompt,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return "AI draft unavailable (request failed)."

    output_text = data.get("output_text")
    if output_text:
        return output_text.strip()

    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                return text.strip()

    return "AI draft unavailable (no text returned)."


def send_feedback_email(session):
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

