# CoreGuard Roadmap

This roadmap treats the current Django application as CoreGuard v0: a working prototype that proves the rehabilitation workflow. The next phase is to turn that prototype into a cleaner, scalable product.

## Phase 1: Stabilise The Existing App

Goals:

- keep the current Django app running reliably
- clean up local setup and documentation
- protect secrets and local media from git
- improve the data model where it affects future API design
- add focused tests around plans, analysis sessions, feedback, and permissions

Likely work:

- add a real dependency file
- tighten role and session access checks
- make seed/demo data reproducible
- separate analysis logic from view functions
- move email and AI drafting into service modules

## Phase 2: Build A Backend API

Goal:

- expose CoreGuard workflows through a proper API that can support both web and mobile clients.

Recommended stack:

- Django REST Framework
- PostgreSQL
- token or session-based authentication
- role-aware API permissions
- structured serializers for plans, exercises, logs, analysis sessions, and feedback

Core API areas:

- authentication and user roles
- physiotherapist client list
- exercise library
- rehab plans and prescriptions
- progress logs
- analysis session summaries
- AI draft feedback
- final feedback delivery

## Phase 3: Modern Physio Web Dashboard

Goal:

- replace the template-heavy dashboard with a richer clinician interface.

Recommended stack:

- React or Next.js
- typed API client
- dashboard charts
- client filtering and search
- review queues for flagged analysis sessions
- plan templates and reusable prescriptions

Key workflows:

- view client overview
- create and edit rehab plans
- review analysis summaries
- compare client progress over time
- generate and edit AI-assisted feedback

## Phase 4: iOS Client App

Goal:

- give clients a clean mobile-first rehab experience.

Recommended stack:

- SwiftUI for a native iOS app, or React Native/Expo if cross-platform delivery becomes important

Core app features:

- assigned plan overview
- exercise instructions and media
- session logging
- reminders and notifications
- live or recorded movement analysis
- feedback inbox
- progress history

## Phase 5: Analysis Service

Goal:

- make movement analysis more robust and easier to evolve.

Short-term improvements:

- extract pose and rule logic from `views.py`
- add rep counting
- store more detailed range-of-motion metrics
- support configurable exercise rules
- improve error handling for camera and landmark visibility issues

Long-term improvements:

- process uploaded videos asynchronously
- store analysis artefacts separately from core app data
- compare progress across sessions
- support more exercises beyond squats
- investigate on-device pose estimation for mobile

## Phase 6: Production Infrastructure

Goal:

- make CoreGuard deployable beyond a local machine.

Likely stack:

- PostgreSQL
- S3-compatible media storage
- Redis
- Celery or background workers
- Docker
- environment-specific settings
- hosted web app and API

Production concerns:

- secure authentication
- password reset and invite flows
- organisation accounts for clinics
- audit trails for feedback and session changes
- GDPR-aware data export and deletion
- backups and monitoring

## Product North Star

CoreGuard should help physiotherapists manage rehab plans more efficiently while giving clients a clear, guided way to complete exercises, submit movement analysis, and receive useful feedback.

The strongest future version is not just a prettier website. It is a connected rehab workflow: plan assignment, client adherence, movement review, AI-assisted drafting, clinician feedback, and progress tracking across time.

