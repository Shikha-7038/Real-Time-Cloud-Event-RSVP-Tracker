"""models.py - SQLAlchemy ORM models (identical schema to the Option A
SQLite build, now expressed as models so they work against Postgres/
Supabase unchanged)."""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"
    user_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # organizer | attendee | admin
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (CheckConstraint("role IN ('organizer','attendee','admin')"),)


class Event(Base):
    __tablename__ = "events"
    event_id = Column(String, primary_key=True)
    organizer_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    event_name = Column(String, nullable=False)
    description = Column(String)
    event_type = Column(String)
    event_date = Column(String, nullable=False, index=True)  # ISO date
    start_time = Column(String, nullable=False)
    end_time = Column(String)
    venue = Column(String)
    online_link = Column(String)
    maximum_capacity = Column(Integer, nullable=False)
    registration_deadline = Column(String)
    status = Column(String, nullable=False, default="PUBLISHED")
    # Denormalized counter used ONLY for the atomic conditional-write capacity
    # gate in rsvp_service.submit_rsvp() - see that file's docstring for why.
    going_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','PUBLISHED','FULL','COMPLETED','CANCELLED')"),
    )


class RSVP(Base):
    __tablename__ = "rsvps"
    rsvp_id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    status = Column(String, nullable=False)  # GOING | MAYBE | NOT_GOING | WAITLISTED
    responded_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_rsvp_event_user"),
        CheckConstraint("status IN ('GOING','MAYBE','NOT_GOING','WAITLISTED')"),
    )


class Waitlist(Base):
    __tablename__ = "waitlist"
    waitlist_id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, nullable=False, default="WAITING")  # WAITING | PROMOTED | CANCELLED

    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_waitlist_event_user"),)


class Announcement(Base):
    __tablename__ = "announcements"
    announcement_id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    notification_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.event_id"))
    type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
