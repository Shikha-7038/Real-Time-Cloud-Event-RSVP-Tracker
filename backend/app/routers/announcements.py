"""announcements.py - /api/events/{id}/announcements"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event, RSVP, Announcement
from app.schemas import AnnouncementCreate, AnnouncementOut
from app.security import get_current_user, CurrentUser
from app.services.rsvp_service import _notify
from app.websocket_manager import manager

router = APIRouter(prefix="/api/events", tags=["announcements"])


@router.post("/{event_id}/announcements", response_model=AnnouncementOut, status_code=201)
async def create_announcement(event_id: str, payload: AnnouncementCreate,
                               user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("organizer", "admin"):
        raise HTTPException(403, "Only organizers can post announcements")
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise HTTPException(404, "Event not found")
    if user.role != "admin" and event.organizer_id != user.user_id:
        raise HTTPException(403, "You can only announce on your own events")

    ann = Announcement(announcement_id=f"ann_{uuid.uuid4().hex}", event_id=event_id,
                        title=payload.title, message=payload.message, created_at=datetime.utcnow())
    db.add(ann)

    recipients = db.query(RSVP.user_id).filter(
        RSVP.event_id == event_id, RSVP.status.in_(["GOING", "MAYBE"])
    ).distinct()
    for (uid,) in recipients:
        _notify(db, uid, event_id, "ORGANIZER_ANNOUNCEMENT", f"{payload.title}: {payload.message}")

    db.commit()
    db.refresh(ann)

    # Push the announcement live to anyone with the event page open.
    await manager.broadcast(event_id, {"type": "announcement", "title": payload.title, "message": payload.message})
    return ann


@router.get("/{event_id}/announcements", response_model=list[AnnouncementOut])
def list_announcements(event_id: str, db: Session = Depends(get_db)):
    return db.query(Announcement).filter(Announcement.event_id == event_id).order_by(
        Announcement.created_at.desc()
    ).all()
