"""
rsvp_service.py
Purpose: RSVP business logic with race-condition-safe capacity control.

THE RACE CONDITION (project brief section 9 & 26):
    if current_going < capacity:   # READ
        insert RSVP as GOING       # WRITE
Two concurrent requests can both pass the read before either writes,
overbooking the event.

THE FIX - ATOMIC CONDITIONAL UPDATE (the pattern the brief explicitly asks
for, and the one that is portable between SQLite and a real Postgres/
Supabase database with zero code changes):
    UPDATE events
    SET going_count = going_count + 1
    WHERE event_id = :id AND going_count < maximum_capacity

This single SQL statement combines the check and the increment into one
atomic operation - the database engine itself serializes concurrent
UPDATEs against the same row, so only as many requests as there are
free seats can ever succeed. `db.execute(...).rowcount` tells us whether
THIS request won a seat (rowcount == 1) or not (rowcount == 0), with no
window for a race between the check and the write. This is the same
technique as a Firestore transaction's `update()` with a precondition,
or a DynamoDB conditional write with `ConditionExpression`.
"""

import uuid
from datetime import datetime
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Event, RSVP, Waitlist, Notification


class RSVPError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex}"


def _notify(db: Session, user_id: str, event_id: str, notif_type: str, message: str):
    db.add(Notification(
        notification_id=_new_id("ntf_"), user_id=user_id, event_id=event_id,
        type=notif_type, message=message, read=False, created_at=datetime.utcnow(),
    ))


def get_counts(db: Session, event_id: str) -> dict:
    rows = db.query(RSVP.status, RSVP).filter(RSVP.event_id == event_id).all()
    counts = {"GOING": 0, "MAYBE": 0, "NOT_GOING": 0, "WAITLISTED": 0}
    for status, _ in rows:
        counts[status] = counts.get(status, 0) + 1
    return counts


def submit_rsvp(db: Session, event_id: str, user_id: str, desired_status: str) -> dict:
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise RSVPError("Event not found", 404)
    if event.status in ("CANCELLED", "COMPLETED"):
        raise RSVPError(f"Cannot RSVP to a {event.status.lower()} event", 409)
    if event.registration_deadline and datetime.utcnow().isoformat() > event.registration_deadline:
        raise RSVPError("Registration deadline has passed", 409)

    existing = db.query(RSVP).filter(RSVP.event_id == event_id, RSVP.user_id == user_id).first()
    was_going = existing is not None and existing.status == "GOING"
    final_status = desired_status
    now = datetime.utcnow()

    if desired_status == "GOING" and not was_going:
        # THE ATOMIC CAPACITY GATE - see module docstring.
        result = db.execute(
            update(Event)
            .where(Event.event_id == event_id, Event.going_count < Event.maximum_capacity)
            .values(going_count=Event.going_count + 1)
        )
        final_status = "GOING" if result.rowcount == 1 else "WAITLISTED"
    elif desired_status != "GOING" and was_going:
        # Freeing a seat - atomic decrement (guarded at 0 so it never goes negative).
        db.execute(
            update(Event)
            .where(Event.event_id == event_id, Event.going_count > 0)
            .values(going_count=Event.going_count - 1)
        )

    if existing:
        existing.status = final_status
        existing.updated_at = now
        rsvp_id = existing.rsvp_id
    else:
        rsvp_id = _new_id("rsvp_")
        db.add(RSVP(rsvp_id=rsvp_id, event_id=event_id, user_id=user_id,
                     status=final_status, responded_at=now, updated_at=now))

    # Keep event.status (PUBLISHED/FULL) in sync for display purposes.
    db.flush()
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event.going_count >= event.maximum_capacity and event.status == "PUBLISHED":
        event.status = "FULL"
    elif event.going_count < event.maximum_capacity and event.status == "FULL":
        event.status = "PUBLISHED"

    # Waitlist bookkeeping
    if final_status == "WAITLISTED":
        wl = db.query(Waitlist).filter(Waitlist.event_id == event_id, Waitlist.user_id == user_id).first()
        if wl:
            wl.status = "WAITING"
            wl.joined_at = now
        else:
            db.add(Waitlist(waitlist_id=_new_id("wl_"), event_id=event_id, user_id=user_id,
                             joined_at=now, status="WAITING"))
    else:
        db.query(Waitlist).filter(
            Waitlist.event_id == event_id, Waitlist.user_id == user_id, Waitlist.status == "WAITING"
        ).update({"status": "CANCELLED"})

    _notify(db, user_id, event_id, "RSVP_CONFIRMATION",
            f"Your RSVP has been recorded as {final_status} for '{event.event_name}'.")

    db.commit()
    return {
        "rsvp_id": rsvp_id, "event_id": event_id, "user_id": user_id,
        "status": final_status, "counts": get_counts(db, event_id),
    }


def cancel_rsvp(db: Session, event_id: str, user_id: str) -> dict:
    existing = db.query(RSVP).filter(RSVP.event_id == event_id, RSVP.user_id == user_id).first()
    if existing is None:
        raise RSVPError("No RSVP found for this event", 404)

    was_going = existing.status == "GOING"
    db.delete(existing)
    db.query(Waitlist).filter(
        Waitlist.event_id == event_id, Waitlist.user_id == user_id, Waitlist.status == "WAITING"
    ).update({"status": "CANCELLED"})

    promoted_user_id = None
    if was_going:
        # Free the seat atomically, then try to promote the FIFO-next waitlisted user.
        db.execute(
            update(Event)
            .where(Event.event_id == event_id, Event.going_count > 0)
            .values(going_count=Event.going_count - 1)
        )
        db.flush()
        promoted_user_id = _promote_from_waitlist(db, event_id)

    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event.going_count < event.maximum_capacity and event.status == "FULL":
        event.status = "PUBLISHED"

    db.commit()
    return {"cancelled": True, "promoted_user_id": promoted_user_id, "counts": get_counts(db, event_id)}


def _promote_from_waitlist(db: Session, event_id: str):
    """FIFO promotion, itself using the same atomic conditional increment -
    so promotion is exactly as race-condition-safe as a normal RSVP."""
    event = db.query(Event).filter(Event.event_id == event_id).first()

    result = db.execute(
        update(Event)
        .where(Event.event_id == event_id, Event.going_count < Event.maximum_capacity)
        .values(going_count=Event.going_count + 1)
    )
    if result.rowcount == 0:
        return None  # no free seat after all

    next_in_line = (
        db.query(Waitlist)
        .filter(Waitlist.event_id == event_id, Waitlist.status == "WAITING")
        .order_by(Waitlist.joined_at.asc())
        .first()
    )
    if next_in_line is None:
        # No one waiting - undo the increment we just made.
        db.execute(
            update(Event).where(Event.event_id == event_id, Event.going_count > 0)
            .values(going_count=Event.going_count - 1)
        )
        return None

    rsvp = db.query(RSVP).filter(RSVP.event_id == event_id, RSVP.user_id == next_in_line.user_id).first()
    if rsvp:
        rsvp.status = "GOING"
        rsvp.updated_at = datetime.utcnow()
    next_in_line.status = "PROMOTED"

    _notify(db, next_in_line.user_id, event_id, "WAITLIST_PROMOTION",
            f"A spot opened up for '{event.event_name}' - you're now GOING!")
    return next_in_line.user_id


def list_event_rsvps(db: Session, event_id: str):
    from app.models import User
    rows = (
        db.query(RSVP, User)
        .join(User, User.user_id == RSVP.user_id)
        .filter(RSVP.event_id == event_id)
        .order_by(RSVP.updated_at.desc())
        .all()
    )
    return [
        {"rsvp_id": r.rsvp_id, "event_id": r.event_id, "user_id": r.user_id, "status": r.status,
         "responded_at": r.responded_at, "updated_at": r.updated_at, "name": u.name, "email": u.email}
        for r, u in rows
    ]
