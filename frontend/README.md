# CoreGuard Studio Frontend

This is a dependency-free modern frontend prototype for CoreGuard. It talks to the Django API and can also run in demo mode without a backend session.

## Run locally

Start Django from the project root:

```bash
python3 manage.py migrate
python3 manage.py seed_demo_data
python3 manage.py runserver
```

Start the static frontend from the project root in another terminal:

```bash
python3 -m http.server 3000 --directory frontend
```

Open `http://localhost:3000` and sign in with:

- Physio: `demo_physio` / `CoreGuardDemo123`
- Client: `demo_client_amy` / `CoreGuardDemo123`

The Django `.env` should include:

```env
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_CREDENTIALS=False
```

The existing Django templates remain intact. This frontend is the first product-facing shell for a future standalone web dashboard or mobile companion experience.
