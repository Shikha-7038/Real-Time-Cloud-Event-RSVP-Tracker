"""analytics.py - /api/events/{id}/analytics"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event
from app.schemas import AnalyticsOut
from app.security import get_current_user, CurrentUser
from app.services.analytics_service import get_event_analytics

router = APIRouter(prefix="/api/events", tags=["analytics"])


@router.get("/{event_id}/analytics", response_model=AnalyticsOut)
def event_analytics(event_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise HTTPException(404, "Event not found")
    if user.role != "admin" and event.organizer_id != user.user_id:
        raise HTTPException(403, "You can only view analytics for your own events")
    return get_event_analytics(db, event_id)
