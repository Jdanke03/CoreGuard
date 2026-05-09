# CoreGuard

[![Django CI](https://github.com/Jdanke03/CoreGuard/actions/workflows/django.yml/badge.svg)](https://github.com/Jdanke03/CoreGuard/actions/workflows/django.yml)

CoreGuard is a rehabilitation support platform for physiotherapists and clients. The current version began as a Django prototype for assigning rehab plans, logging client progress, running live squat analysis, and sending physiotherapist feedback.

This personal repository continues CoreGuard beyond the original university submission. The goal is to evolve it from a local Django web app into a more complete product with a modern web dashboard, mobile client experience, stronger analysis workflows, and production-ready infrastructure.

## Current Version

- Django web application with server-rendered templates
- Physiotherapist and client role-based workflows
- Exercise library and structured rehab plans
- Client progress logs
- Live squat analysis using OpenCV and MediaPipe Pose
- AI-assisted physiotherapist feedback drafting
- Feedback delivery through the app and email
- SQLite database for local development

## Product Direction

The next version of CoreGuard will move toward a multi-platform architecture:

- API backend for shared web and mobile clients
- PostgreSQL database
- Modern physiotherapist web dashboard
- iOS-first client app
- Cloud-ready media storage
- Improved movement analysis and reporting
- Notifications for plan reminders and feedback updates

See [docs/ROADMAP.md](docs/ROADMAP.md) for the planned technical direction.

## Local Development

Create a local `.env` file in the project root. The easiest way is to copy the example file:

```bash
cp .env.example .env
```

Then fill in the values you need:

```env
SECRET_KEY=change-me-for-production
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
OPENAI_API_KEY=your_openai_api_key
GMAIL_USER=your_gmail_address
GMAIL_APP_PASSWORD=your_gmail_app_password
DEFAULT_FROM_EMAIL=CoreGuard <your_gmail_address>
```

Run the Django app:

```bash
python3 manage.py migrate
python3 manage.py runserver
```

The app uses local media files and a local SQLite database during development. These are intentionally not committed.

## Environment Notes

- `.env` stores local secrets and should stay untracked.
- `.env.example` documents the required variables without exposing real credentials.
- `OPENAI_API_KEY` powers AI-assisted feedback drafts.
- `GMAIL_USER` and `GMAIL_APP_PASSWORD` power SMTP email delivery.
- `DEBUG` and `ALLOWED_HOSTS` can be changed when preparing for deployment.
