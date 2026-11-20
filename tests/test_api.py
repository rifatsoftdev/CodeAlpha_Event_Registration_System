from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.model.models import User
from app.security import hash_password


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    
    with Session() as db:
        db.add(User(username="org", hashed_password=hash_password("password1"), is_organizer=True))
        db.commit()
    yield TestClient(app)

    app.dependency_overrides.clear()


def auth(client, username, password="password1", signup=True):
    if signup:
        assert client.post("/auth/signup", json={
            "username": username, "email": f"{username}@example.test", "password": password,
        }).status_code == 201
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_event(client, headers, capacity=1, days=1):
    start = datetime.now(timezone.utc) + timedelta(days=days)
    r = client.post("/events", headers=headers, json={
        "title": "Meetup", "location": "Dhaka", "capacity": capacity,
        "start_time": start.isoformat(), "end_time": (start + timedelta(hours=2)).isoformat()})
    assert r.status_code == 201, r.text
    return r.json()


def test_public_list_and_detail(client):
    org = auth(client, "org", signup=False)
    ev = make_event(client, org, capacity=5)
    assert len(client.get("/events").json()) == 1
    detail = client.get(f"/events/{ev['id']}").json()
    assert detail["spots_left"] == 5


def test_register_requires_auth(client):
    assert client.post("/events/1/register", json={"full_name": "x"}).status_code == 401


def test_full_flow(client):
    org = auth(client, "org", signup=False)
    ev = make_event(client, org, capacity=1)
    bob, amy = auth(client, "bob"), auth(client, "amy")
    url = f"/events/{ev['id']}/register"

    r = client.post(url, headers=bob, json={"full_name": "Bob"})
    assert r.status_code == 201
    reg_id = r.json()["id"]
    assert client.get(f"/events/{ev['id']}").json()["spots_left"] == 0
    assert client.post(url, headers=bob, json={"full_name": "Bob"}).status_code == 400   # duplicate
    assert client.post(url, headers=amy, json={"full_name": "Amy"}).status_code == 400   # full

    assert client.delete(f"/registrations/{reg_id}", headers=amy).status_code == 404     # not hers
    assert client.delete(f"/registrations/{reg_id}", headers=bob).json()["status"] == "cancelled"
    assert client.get("/registrations/me", headers=bob).json()[0]["status"] == "cancelled"
    assert client.post(url, headers=amy, json={"full_name": "Amy"}).status_code == 201   # spot freed
    assert client.post(url, headers=bob, json={"full_name": "Bob"}).status_code == 400   # full again


def test_event_owner_permissions(client):
    org = auth(client, "org", signup=False)
    bob = auth(client, "bob")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    body = {"title": "N", "location": "X", "capacity": 5,
            "start_time": start.isoformat(), "end_time": (start + timedelta(hours=1)).isoformat()}
    assert client.post("/events", json=body).status_code == 401
    assert client.post("/events", headers=bob, json=body).status_code == 403
    ev = make_event(client, org)
    assert client.get(f"/events/{ev['id']}/registrations", headers=bob).status_code == 403
    assert client.get(f"/events/{ev['id']}/registrations", headers=org).status_code == 200
    assert client.patch(f"/events/{ev['id']}", headers=org, json={"capacity": 10}).json()["capacity"] == 10
    assert client.patch(f"/events/{ev['id']}", headers=bob, json={"title": "Not yours"}).status_code == 403
    assert client.delete(f"/events/{ev['id']}", headers=bob).status_code == 403
    assert client.delete(f"/events/{ev['id']}", headers=org).status_code == 204


def test_validation(client):
    org = auth(client, "org", signup=False)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    event_response = client.post("/events", headers=org, json={
        "title": "Good event", "location": "X", "capacity": 5,
        "start_time": start.isoformat(), "end_time": (start + timedelta(hours=1)).isoformat()})
    assert event_response.status_code == 201
    event_id = event_response.json()["id"]

    assert client.patch(f"/events/{event_id}", headers=org, json={"start_time": None}).status_code == 422
    assert client.patch(f"/events/{event_id}", headers=org, json={"description": None}).status_code == 422

    r = client.post("/events", headers=org, json={
        "title": "Bad", "location": "X", "capacity": 5,
        "start_time": start.isoformat(), "end_time": (start - timedelta(hours=1)).isoformat()})
    assert r.status_code == 422


def test_capacity_cannot_drop_below_confirmed_registrations(client):
    org = auth(client, "org", signup=False)
    attendee = auth(client, "attendee")
    event = make_event(client, org, capacity=2)
    registration = client.post(
        f"/events/{event['id']}/register",
        headers=attendee,
        json={"full_name": "Attendee"},
    )
    assert registration.status_code == 201
    assert client.patch(
        f"/events/{event['id']}", headers=org, json={"capacity": 0}
    ).status_code == 422
    assert client.patch(
        f"/events/{event['id']}", headers=org, json={"capacity": 1}
    ).json()["spots_left"] == 0


def test_signup_duplicate_username(client):
    first = client.post("/auth/signup", json={"username": "same", "email": "same@example.test", "password": "password1"})
    second = client.post("/auth/signup", json={"username": "same", "email": "same@example.test", "password": "password1"})
    assert first.status_code == 201
    assert second.status_code == 409


def test_rejects_blank_registration_name(client):
    org = auth(client, "org", signup=False)
    attendee = auth(client, "attendee")
    event = make_event(client, org)
    response = client.post(
        f"/events/{event['id']}/register",
        headers=attendee,
        json={"full_name": "   "},
    )
    assert response.status_code == 422
