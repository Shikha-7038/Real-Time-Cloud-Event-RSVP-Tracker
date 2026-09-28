"""
test_api.py
Purpose: Automated tests for the Option B (FastAPI + SQLAlchemy) backend,
mirroring the Option A test suite, including the critical multi-threaded
concurrency test that proves the atomic conditional-write capacity gate
in rsvp_service.py actually prevents overbooking under real concurrent
load.

Run with:  pytest -v   (from backend/)
"""

import os
import tempfile
import threading

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
os.environ["SECRET_KEY"] = "test-secret"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.services import rsvp_service

client = TestClient(app)


def _register(role="attendee", email=None, name="Test User"):
    email = email or f"{name.lower().replace(' ', '')}@example.com"
    resp = client.post("/api/register", json={"name": name, "email": email, "password": "password123", "role": role})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_event(organizer_token, capacity=2, **overrides):
    payload = {
        "event_name": "Cloud Computing Workshop", "event_date": "2027-01-15",
        "start_time": "10:00", "maximum_capacity": capacity, "venue": "Auditorium A",
    }
    payload.update(overrides)
    resp = client.post("/api/events", json=payload, headers=_auth(organizer_token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# 1. Registration ------------------------------------------------------------
def test_user_registration():
    data = _register(role="attendee")
    assert data["user"]["role"] == "attendee"
    assert "token" in data


# 2. Duplicate registration rejected ------------------------------------------
def test_duplicate_registration_rejected():
    _register(email="dup@example.com")
    resp = client.post("/api/register", json={"name": "Dup", "email": "dup@example.com", "password": "password123", "role": "attendee"})
    assert resp.status_code == 409


# 3. Login success / failure --------------------------------------------------
def test_login_success_and_failure():
    _register(email="login@example.com")
    ok = client.post("/api/login", json={"email": "login@example.com", "password": "password123"})
    assert ok.status_code == 200
    bad = client.post("/api/login", json={"email": "login@example.com", "password": "wrongpass"})
    assert bad.status_code == 401


# 4. Organizer creates event ---------------------------------------------------
def test_organizer_creates_event():
    org = _register(role="organizer", email="org1@example.com")
    event = _create_event(org["token"])
    assert event["status"] == "PUBLISHED"


# 5. Attendee cannot create event ----------------------------------------------
def test_attendee_cannot_create_event():
    att = _register(role="attendee", email="att-noaccess@example.com")
    resp = client.post("/api/events", json={
        "event_name": "Should Fail", "event_date": "2027-01-15", "start_time": "10:00", "maximum_capacity": 5,
    }, headers=_auth(att["token"]))
    assert resp.status_code == 403


# 6. Event retrieval -------------------------------------------------------------
def test_event_retrieval():
    org = _register(role="organizer", email="org2@example.com")
    event = _create_event(org["token"])
    resp = client.get(f"/api/events/{event['event_id']}")
    assert resp.status_code == 200
    assert resp.json()["event_name"] == "Cloud Computing Workshop"


# 7. Valid RSVP -------------------------------------------------------------------
def test_valid_rsvp():
    org = _register(role="organizer", email="org3@example.com")
    event = _create_event(org["token"], capacity=10)
    att = _register(role="attendee", email="att3@example.com")
    resp = client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(att["token"]))
    assert resp.status_code == 200
    assert resp.json()["status"] == "GOING"


# 8. Duplicate RSVP -> upsert, not a duplicate row ---------------------------------
def test_duplicate_rsvp_updates_not_duplicates():
    org = _register(role="organizer", email="org4@example.com")
    event = _create_event(org["token"], capacity=10)
    att = _register(role="attendee", email="att4@example.com")
    client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(att["token"]))
    client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "MAYBE"}, headers=_auth(att["token"]))
    resp = client.get(f"/api/events/{event['event_id']}/rsvps", headers=_auth(org["token"]))
    rsvps = resp.json()
    assert len(rsvps) == 1
    assert rsvps[0]["status"] == "MAYBE"


# 9. RSVP status updates GOING -> MAYBE -> GOING ------------------------------------
def test_rsvp_status_updates():
    org = _register(role="organizer", email="org5@example.com")
    event = _create_event(org["token"], capacity=10)
    att = _register(role="attendee", email="att5@example.com")
    h = _auth(att["token"])
    r1 = client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=h).json()
    assert r1["counts"]["GOING"] == 1
    r2 = client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "MAYBE"}, headers=h).json()
    assert r2["counts"]["GOING"] == 0 and r2["counts"]["MAYBE"] == 1
    r3 = client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=h).json()
    assert r3["counts"]["GOING"] == 1


# 10. Cancel RSVP -----------------------------------------------------------------
def test_cancel_rsvp():
    org = _register(role="organizer", email="org6@example.com")
    event = _create_event(org["token"], capacity=10)
    att = _register(role="attendee", email="att6@example.com")
    h = _auth(att["token"])
    client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=h)
    resp = client.request("DELETE", f"/api/events/{event['event_id']}/rsvp", headers=h)
    assert resp.status_code == 200
    assert resp.json()["cancelled"] is True


# 11. Registration deadline enforced ------------------------------------------------
def test_registration_deadline_enforced():
    org = _register(role="organizer", email="org7@example.com")
    event = _create_event(org["token"], capacity=10, registration_deadline="2000-01-01T00:00:00")
    att = _register(role="attendee", email="att7@example.com")
    resp = client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(att["token"]))
    assert resp.status_code == 409


# 12. Capacity enforcement -> waitlist -----------------------------------------------
def test_capacity_enforcement_waitlists_overflow():
    org = _register(role="organizer", email="org8@example.com")
    event = _create_event(org["token"], capacity=1)
    a1 = _register(role="attendee", email="att8a@example.com")
    a2 = _register(role="attendee", email="att8b@example.com")
    r1 = client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(a1["token"]))
    r2 = client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(a2["token"]))
    assert r1.json()["status"] == "GOING"
    assert r2.json()["status"] == "WAITLISTED"
    event_after = client.get(f"/api/events/{event['event_id']}").json()
    assert event_after["status"] == "FULL"


# 13. THE concurrency / race-condition test -----------------------------------------
def test_concurrent_last_seat_requests_are_race_condition_safe():
    """Fires 10 real threads at a capacity-1 event, each calling the
    service layer's submit_rsvp() directly (its own DB session per
    thread, exactly like independent API requests would each get their
    own session). Exactly ONE must win GOING; the rest WAITLISTED -
    proving the atomic conditional UPDATE in rsvp_service.py holds under
    genuine concurrent load, not just sequential calls."""
    org = _register(role="organizer", email="org9@example.com")
    event = _create_event(org["token"], capacity=1)
    event_id = event["event_id"]

    user_ids = []
    for i in range(10):
        att = _register(role="attendee", email=f"racer{i}@example.com", name=f"Racer{i}")
        user_ids.append(att["user"]["user_id"])

    results = []
    lock = threading.Lock()

    def attempt(user_id):
        db = SessionLocal()
        try:
            res = rsvp_service.submit_rsvp(db, event_id, user_id, "GOING")
            with lock:
                results.append(res["status"])
        except Exception as e:
            with lock:
                results.append(f"ERROR:{e}")
        finally:
            db.close()

    threads = [threading.Thread(target=attempt, args=(uid,)) for uid in user_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    going_count = results.count("GOING")
    waitlisted_count = results.count("WAITLISTED")
    assert going_count == 1, f"Expected exactly 1 GOING, got {going_count}: {results}"
    assert waitlisted_count == 9, f"Expected 9 WAITLISTED, got {waitlisted_count}: {results}"


# 14. Waitlist promotion (FIFO) on cancellation --------------------------------------
def test_waitlist_promotion_on_cancellation():
    org = _register(role="organizer", email="org10@example.com")
    event = _create_event(org["token"], capacity=1)
    a1 = _register(role="attendee", email="att10a@example.com")
    a2 = _register(role="attendee", email="att10b@example.com")
    client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(a1["token"]))
    client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(a2["token"]))
    resp = client.request("DELETE", f"/api/events/{event['event_id']}/rsvp", headers=_auth(a1["token"]))
    assert resp.json()["promoted_user_id"] == a2["user"]["user_id"]


# 15. Announcement creation ------------------------------------------------------------
def test_announcement_creation():
    org = _register(role="organizer", email="org11@example.com")
    event = _create_event(org["token"])
    resp = client.post(f"/api/events/{event['event_id']}/announcements",
                        json={"title": "Venue Updated", "message": "New room: B12"}, headers=_auth(org["token"]))
    assert resp.status_code == 201


# 16. Notification generated on RSVP ----------------------------------------------------
def test_notification_generated_on_rsvp():
    org = _register(role="organizer", email="org12@example.com")
    event = _create_event(org["token"], capacity=10)
    att = _register(role="attendee", email="att12@example.com")
    client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(att["token"]))
    resp = client.get("/api/notifications", headers=_auth(att["token"]))
    assert any(n["type"] == "RSVP_CONFIRMATION" for n in resp.json())


# 17. Unauthorized event modification rejected -------------------------------------------
def test_unauthorized_event_modification_rejected():
    org1 = _register(role="organizer", email="org13a@example.com")
    org2 = _register(role="organizer", email="org13b@example.com")
    event = _create_event(org1["token"])
    resp = client.put(f"/api/events/{event['event_id']}", json={"event_name": "Hijacked"}, headers=_auth(org2["token"]))
    assert resp.status_code == 403


# 18. Unauthorized RSVP list access rejected ----------------------------------------------
def test_unauthorized_rsvp_list_access_rejected():
    org1 = _register(role="organizer", email="org14a@example.com")
    org2 = _register(role="organizer", email="org14b@example.com")
    event = _create_event(org1["token"])
    resp = client.get(f"/api/events/{event['event_id']}/rsvps", headers=_auth(org2["token"]))
    assert resp.status_code == 403


# 19. Live counter reflects RSVP immediately -----------------------------------------------
def test_counter_updates_immediately_after_rsvp():
    org = _register(role="organizer", email="org15@example.com")
    event = _create_event(org["token"], capacity=10)
    att = _register(role="attendee", email="att15@example.com")
    before = client.get(f"/api/events/{event['event_id']}/counts").json()
    assert before["going"] == 0
    client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(att["token"]))
    after = client.get(f"/api/events/{event['event_id']}/counts").json()
    assert after["going"] == 1


# 20. Analytics calculation -------------------------------------------------------------------
def test_analytics_calculation():
    org = _register(role="organizer", email="org16@example.com")
    event = _create_event(org["token"], capacity=4)
    for i in range(2):
        att = _register(role="attendee", email=f"att16-{i}@example.com")
        client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(att["token"]))
    resp = client.get(f"/api/events/{event['event_id']}/analytics", headers=_auth(org["token"]))
    data = resp.json()
    assert data["going"] == 2
    assert data["capacity_utilization_pct"] == 50.0


# 21. Missing event returns 404, not 500 ---------------------------------------------------------
def test_missing_event_returns_404_not_500():
    resp = client.get("/api/events/does-not-exist")
    assert resp.status_code == 404


# 22. Invalid token rejected -------------------------------------------------------------------------
def test_invalid_token_rejected():
    resp = client.get("/api/notifications", headers=_auth("not-a-real-token"))
    assert resp.status_code == 401


# 23. Event cancellation notifies attendees --------------------------------------------------------------
def test_event_cancellation_notifies_attendees():
    org = _register(role="organizer", email="org17@example.com")
    event = _create_event(org["token"], capacity=10)
    att = _register(role="attendee", email="att17@example.com")
    client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(att["token"]))
    resp = client.request("DELETE", f"/api/events/{event['event_id']}", headers=_auth(org["token"]))
    assert resp.status_code == 200
    notifications = client.get("/api/notifications", headers=_auth(att["token"])).json()
    assert any(n["type"] == "EVENT_CANCELLED" for n in notifications)


# 24. WebSocket real-time push -----------------------------------------------------------------------------
def test_websocket_receives_live_count_update():
    """Connects a WebSocket client to an event, submits an RSVP over
    REST, and asserts the WebSocket receives a push with updated counts -
    proving genuine real-time delivery, not polling."""
    org = _register(role="organizer", email="org18@example.com")
    event = _create_event(org["token"], capacity=10)
    att = _register(role="attendee", email="att18@example.com")

    with client.websocket_connect(f"/ws/events/{event['event_id']}") as ws:
        client.post(f"/api/events/{event['event_id']}/rsvp", json={"status": "GOING"}, headers=_auth(att["token"]))
        message = ws.receive_json()
        assert message["type"] == "counts_update"
        assert message["going"] == 1
