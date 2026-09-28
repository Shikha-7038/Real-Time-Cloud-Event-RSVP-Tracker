"""events.py - /api/events CRUD"""

import uuid
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event, RSVP
from app.schemas import EventCreate, EventUpdate, EventOut
from app.security import get_current_user, require_role, CurrentUser
from app.services.rsvp_service import get_counts
from app.services.rsvp_service import _notify

router = APIRouter(prefix="/api/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=201)
def create_event(payload: EventCreate, user: CurrentUser = Depends(require_role("organizer", "admin")),
                  db: Session = Depends(get_db)):
    if payload.end_time and payload.end_time < payload.start_time:
        raise HTTPException(400, "end_time must be after start_time")
    event = Event(
        event_id=f"evt_{uuid.uuid4().hex}", organizer_id=user.user_id, event_name=payload.event_name,
        description=payload.description, event_type=payload.event_type, event_date=payload.event_date,
        start_time=payload.start_time, end_time=payload.end_time, venue=payload.venue,
        online_link=payload.online_link, maximum_capacity=payload.maximum_capacity,
        registration_deadline=payload.registration_deadline, status=payload.status or "PUBLISHED",
        going_count=0,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("", response_model=list[EventOut])
def list_events(upcoming: bool = False, db: Session = Depends(get_db)):
    q = db.query(Event)
    if upcoming:
        today = date.today().isoformat()
        q = q.filter(Event.status.in_(["PUBLISHED", "FULL"]), Event.event_date >= today)
        return q.order_by(Event.event_date.asc()).all()
    return q.order_by(Event.event_date.desc()).all()


@router.get("/{event_id}/counts")
def get_event_counts(event_id: str, db: Session = Depends(get_db)):
    """Public, PII-free live counts - polled/subscribed to by any visitor."""
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise HTTPException(404, "Event not found")
    counts = get_counts(db, event_id)
    return {
        "going": counts["GOING"], "maybe": counts["MAYBE"], "not_going": counts["NOT_GOING"],
        "waitlisted": counts["WAITLISTED"], "available_seats": max(0, event.maximum_capacity - counts["GOING"]),
    }


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise HTTPException(404, "Event not found")
    return event


@router.put("/{event_id}", response_model=EventOut)
def update_event(event_id: str, payload: EventUpdate, user: CurrentUser = Depends(require_role("organizer", "admin")),
                  db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise HTTPException(404, "Event not found")
    if user.role != "admin" and event.organizer_id != user.user_id:
        raise HTTPException(403, "You can only edit your own events")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}")
def cancel_event(event_id: str, user: CurrentUser = Depends(require_role("organizer", "admin")),
                  db: Session = Depends(get_db)):
    """Soft-delete: mark CANCELLED, preserve history for analytics/audit."""
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise HTTPException(404, "Event not found")
    if user.role != "admin" and event.organizer_id != user.user_id:
        raise HTTPException(403, "You can only cancel your own events")

    event.status = "CANCELLED"
    event.updated_at = datetime.utcnow()
    attendee_ids = [r.user_id for r in db.query(RSVP.user_id).filter(RSVP.event_id == event_id).distinct()]
    for uid in attendee_ids:
        _notify(db, uid, event_id, "EVENT_CANCELLED", f"'{event.event_name}' has been cancelled by the organizer.")
    db.commit()
    return {"message": "Event cancelled", "event_id": event_id}
