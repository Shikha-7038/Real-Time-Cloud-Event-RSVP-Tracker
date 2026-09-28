"""
rsvp.py - /api/events/{id}/rsvp and the /ws/events/{id} WebSocket route.

This is the real-time centerpiece: every successful RSVP write
immediately broadcasts the new counts to every browser with that
event's WebSocket open - genuine push, not polling.
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import Event, RSVP
from app.schemas import RSVPRequest
from app.security import get_current_user, CurrentUser, verify_token
from app.services import rsvp_service
from app.services.rsvp_service import RSVPError
from app.websocket_manager import manager

router = APIRouter(prefix="/api", tags=["rsvp"])
ws_router = APIRouter(tags=["realtime"])


async def _broadcast_counts(event_id: str):
    """Re-fetch live counts on a fresh session and push to all subscribers.
    Kept as its own DB read (not reusing the request's session) so the
    broadcast reflects the just-committed state cleanly."""
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.event_id == event_id).first()
        if event is None:
            return
        counts = rsvp_service.get_counts(db, event_id)
        await manager.broadcast(event_id, {
            "type": "counts_update",
            "event_id": event_id,
            "going": counts["GOING"], "maybe": counts["MAYBE"], "not_going": counts["NOT_GOING"],
            "waitlisted": counts["WAITLISTED"],
            "available_seats": max(0, event.maximum_capacity - counts["GOING"]),
            "event_status": event.status,
        })
    finally:
        db.close()


@router.post("/events/{event_id}/rsvp")
async def create_or_update_rsvp(event_id: str, payload: RSVPRequest,
                                 user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        result = rsvp_service.submit_rsvp(db, event_id, user.user_id, payload.status)
    except RSVPError as e:
        raise HTTPException(e.status_code, e.message)
    await _broadcast_counts(event_id)  # <-- push update to every connected client
    return result


@router.put("/events/{event_id}/rsvp")
async def update_rsvp(event_id: str, payload: RSVPRequest, user: CurrentUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    return await create_or_update_rsvp(event_id, payload, user, db)


@router.delete("/events/{event_id}/rsvp")
async def delete_rsvp(event_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        result = rsvp_service.cancel_rsvp(db, event_id, user.user_id)
    except RSVPError as e:
        raise HTTPException(e.status_code, e.message)
    await _broadcast_counts(event_id)
    return result


@router.get("/events/{event_id}/rsvps")
def get_event_rsvps(event_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise HTTPException(404, "Event not found")
    if user.role != "admin" and event.organizer_id != user.user_id:
        raise HTTPException(403, "You can only view RSVPs for your own events")
    return rsvp_service.list_event_rsvps(db, event_id)


@router.get("/rsvps/me")
def get_my_rsvps(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(RSVP, Event)
        .join(Event, Event.event_id == RSVP.event_id)
        .filter(RSVP.user_id == user.user_id)
        .order_by(Event.event_date.asc())
        .all()
    )
    return [
        {"rsvp_id": r.rsvp_id, "event_id": r.event_id, "status": r.status,
         "event_name": e.event_name, "event_date": e.event_date, "venue": e.venue, "event_status": e.status}
        for r, e in rows
    ]


@ws_router.websocket("/ws/events/{event_id}")
async def event_websocket(websocket: WebSocket, event_id: str):
    """Clients connect here to receive live RSVP count updates for one
    event, pushed the instant anyone RSVPs - the WebSocket analogue of a
    Firestore onSnapshot() listener. No auth required (counts are public/
    PII-free), matching the public /events/{id}/counts REST endpoint."""
    await manager.connect(event_id, websocket)
    try:
        while True:
            # We don't expect client->server messages, but must keep
            # awaiting receive() to detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(event_id, websocket)
