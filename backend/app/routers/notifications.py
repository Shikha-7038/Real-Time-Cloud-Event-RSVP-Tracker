"""notifications.py - /api/notifications"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification
from app.schemas import NotificationOut
from app.security import get_current_user, CurrentUser

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_my_notifications(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Notification).filter(Notification.user_id == user.user_id).order_by(
        Notification.created_at.desc()
    ).limit(100).all()


@router.put("/{notification_id}/read")
def mark_read(notification_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.notification_id == notification_id).first()
    if notif is None:
        raise HTTPException(404, "Notification not found")
    if notif.user_id != user.user_id:
        raise HTTPException(403, "Cannot modify another user's notification")
    notif.read = True
    db.commit()
    return {"message": "marked as read"}
