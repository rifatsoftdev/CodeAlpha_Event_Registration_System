# EventHub — Event Registration System

Python 3.10+ · FastAPI · SQLAlchemy 2.0 · JWT auth

## Setup
```bash
python3.10 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open **http://localhost:8000** for the event listing, **http://localhost:8000/login** to sign in, or **http://localhost:8000/register** to create an account. Attendees can register for events and manage their registrations from **http://localhost:8000/dashboard**. Organizer accounts can also publish and manage their own events and view their attendee lists.

The site includes event search, registration cancellation, organizer event create/edit/delete, event and attendee status, and password reset. Password reset emails need SMTP configuration. Copy `.env.example` to `.env`, set the mail credentials and `APP_BASE_URL`, then load it before starting the app:
```bash
cp .env.example .env
set -a && source .env && set +a
python3.10 run.py
```
`run.py` does not load `.env` automatically; configure your deployment environment in the same way.

Create or promote an organizer account from the project directory:
```bash
python create_organizer.py organizer_name 'use-a-long-password' organizer@example.com
python create_organizer.py --promote existing_username
```

API docs are at **http://localhost:8000/docs**; the health endpoint is **http://localhost:8000/health**.

SQLite is the default. For PostgreSQL: `export DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/events`
(and install `psycopg2-binary`). Set a unique, random `SECRET_KEY` and `DATABASE_URL` in production. Tables are created on startup; use database migrations for schema changes after deployment.

Run tests: `pytest -q`

## Endpoints
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | – | `{username, email, password}` (`email` is required for account recovery) |
| POST | `/auth/login` | – | form fields `username`, `password` → `{access_token}` |
| GET | `/auth/me` | user | current user |
| POST | `/auth/password-reset/request` | – | send one-time reset email (SMTP required) |
| POST | `/auth/password-reset/confirm` | – | confirm reset with token and new password |
| GET | `/events` | – | list (`?upcoming=true&skip=0&limit=20`) |
| GET | `/events/{id}` | – | details incl. `spots_left` |
| POST | `/events/{id}/register` | user | `{full_name, phone?, notes?}` |
| GET | `/registrations/me` | user | my registrations (`?status_filter=confirmed`) |
| GET | `/registrations/{id}` | user | one of my registrations |
| DELETE | `/registrations/{id}` | user | cancel my registration |
| POST | `/events` | organizer | create event |
| PATCH / DELETE | `/events/{id}` | owner/organizer | edit / delete own event |
| GET | `/events/{id}/registrations` | owner/organizer | attendee list for own event |

All times are UTC. Send `Authorization: Bearer <token>`.
