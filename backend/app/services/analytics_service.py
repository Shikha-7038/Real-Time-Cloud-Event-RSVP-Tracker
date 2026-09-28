"""analytics_service.py - organizer analytics computation (FastAPI/SQLAlchemy version)."""

from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import Event, RSVP, Waitlist


def get_event_analytics(db: Session, event_id: str):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        return None

    status_counts = {"GOING": 0, "MAYBE": 0, "NOT_GOING": 0, "WAITLISTED": 0}
    for status, count in db.query(RSVP.status, func.count(RSVP.rsvp_id)).filter(
        RSVP.event_id == event_id
    ).group_by(RSVP.status):
        status_counts[status] = count

    total_responses = sum(status_counts.values())
    capacity = event.maximum_capacity or 0
    going = status_counts["GOING"]

    growth_rows = (
        db.query(func.date(RSVP.responded_at).label("day"), func.count(RSVP.rsvp_id))
        .filter(RSVP.event_id == event_id)
        .group_by("day")
        .order_by("day")
        .all()
    )
    growth = [{"date": str(day), "count": count} for day, count in growth_rows]

    waitlist_count = db.query(func.count(Waitlist.waitlist_id)).filter(
        Waitlist.event_id == event_id, Waitlist.status == "WAITING"
    ).scalar()

    return {
        "event_id": event_id,
        "total_responses": total_responses,
        "going": status_counts["GOING"],
        "maybe": status_counts["MAYBE"],
        "not_going": status_counts["NOT_GOING"],
        "waitlisted": status_counts["WAITLISTED"],
        "waitlist_size": waitlist_count,
        "maximum_capacity": capacity,
        "available_seats": max(0, capacity - going),
        "capacity_utilization_pct": round((going / capacity) * 100, 2) if capacity else 0,
        "rsvp_growth_over_time": growth,
    }
