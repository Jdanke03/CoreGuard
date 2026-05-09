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


## API Foundation

CoreGuard now includes an authenticated API under `/api/`. This is intended as the foundation for future mobile and modern frontend clients while keeping the existing Django template UI intact.

Current API endpoints:

- `/api/docs/` - interactive Swagger API documentation
- `/api/schema/` - OpenAPI schema
- `/api/auth/login/` - returns an API token for valid credentials
- `/api/auth/logout/` - deletes the current user's API token
- `/api/me/` - returns the current user's profile and role, and supports email updates with `PATCH`
- `/api/dashboard/` - returns role-specific dashboard metrics and latest activity
- `/api/actions/` - returns a role-specific action queue for next best client or physiotherapist tasks
- `/api/exercises/` - read the exercise library; physiotherapists can create exercises with image uploads
- `/api/clients/` - lists clients assigned to the logged-in physiotherapist
- `/api/plans/` - read plans; physiotherapists can create structured plans with exercise prescriptions
- `/api/plan-exercises/`
- `/api/logs/` - clients can also create their own progress logs with `POST`
- `/api/analysis-sessions/` - includes parsed summary metrics for app-friendly display
- `/api/analysis-sessions/{id}/generate-draft/` - physiotherapists can generate an AI feedback draft
- `/api/analysis-sessions/{id}/send-feedback/` - physiotherapists can share final feedback and trigger email delivery with a clear `email_delivery` status

API responses are filtered by the logged-in user. Clients only see their own plans, logs, and analysis sessions. Physiotherapists see records connected to plans they created. Token authentication is available for future mobile and standalone frontend clients. List endpoints also support practical query controls such as `search`, `ordering`, and model-specific filters like `body_area`, `difficulty`, `requires_analysis`, `plan`, and `feedback_shared`.

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
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_CREDENTIALS=False
DATABASE_URL=
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

Optional: create a realistic local dataset for demos and frontend development:

```bash
python3 manage.py seed_demo_data
```

This creates a demo physiotherapist, two demo clients, exercises, plans, progress logs, and one reviewed analysis session. The command is safe to run more than once.

The app uses local media files and a local SQLite database during development. These are intentionally not committed.

## Environment Notes

- `.env` stores local secrets and should stay untracked.
- `.env.example` documents the required variables without exposing real credentials.
- `DATABASE_URL` is optional locally. Leave it blank to use SQLite, or set a PostgreSQL URL for deployment.
- `CORS_ALLOWED_ORIGINS` controls which separate frontend apps can call the API in a browser.
- `OPENAI_API_KEY` powers AI-assisted feedback drafts.
- `GMAIL_USER` and `GMAIL_APP_PASSWORD` power SMTP email delivery.
- `DEBUG` and `ALLOWED_HOSTS` can be changed when preparing for deployment.
- API list endpoints are paginated by default with a page size of 20.

## Background-Ready Workflows

CoreGuard keeps feedback draft generation and email delivery behind task-style functions in `tracker/tasks/`. They still run synchronously during local development, but the boundaries are ready for Celery or another background worker later.
