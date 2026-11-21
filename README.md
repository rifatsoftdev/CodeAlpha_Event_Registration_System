# EventHub — Event Registration System

Python 3.10+ · FastAPI · SQLAlchemy 2.0 · JWT auth

## Docker setup

Install Docker, then create your local environment file and set a strong secret key. For example, generate one with Python:
```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Put the generated value in `.env` as `SECRET_KEY=...`. Set `APP_BASE_URL=http://localhost:3000`. For password recovery, also fill in the SMTP settings in `.env`.

Build and start the container:
```bash
docker build -t eventhub .
docker volume create eventhub-data
docker run -d --name eventhub --restart unless-stopped \
  --env-file .env \
  -e DATABASE_URL=sqlite:////data/events.db \
  -p 3000:3000 \
  -v eventhub-data:/data \
  eventhub
```

Open **http://localhost:3000** for the event list, **http://localhost:3000/login** to sign in, or **http://localhost:3000/register** to create an account. Attendees can register for events and manage their registrations from **http://localhost:3000/dashboard**. Organizer accounts can publish and manage events and view attendee lists.

View logs with `docker logs -f eventhub`. Stop the app with `docker stop eventhub`; start it again with `docker start eventhub`. The named volume keeps the SQLite database when the container is replaced.

The site includes event search, registration cancellation, organizer event create/edit/delete, event and attendee status, and password reset. Password reset emails need SMTP configuration in `.env`.

Create or promote an organizer account interactively from the project directory:
```bash
docker exec -it eventhub python create_organizer.py
```
The script asks for the username, email, and password without displaying the password as you type. If that username already belongs to an attendee, it asks before promoting the account.

API docs are at **http://localhost:3000/docs**; the health endpoint is **http://localhost:3000/health**.

SQLite is the default. For PostgreSQL: `export DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/events`
(and install `psycopg2-binary`). Set a unique, random `SECRET_KEY` and `DATABASE_URL` in production. Tables are created on startup; use database migrations for schema changes after deployment.

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
