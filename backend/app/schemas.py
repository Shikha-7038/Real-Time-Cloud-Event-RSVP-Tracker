"""schemas.py - Pydantic models for request validation and response shaping."""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime


# --- Auth ---
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)
    role: str = "attendee"

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        if v not in ("organizer", "attendee"):
            raise ValueError("role must be 'organizer' or 'attendee'")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    user_id: str
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    token: str
    user: UserOut


# --- Events ---
class EventCreate(BaseModel):
    event_name: str
    description: Optional[str] = None
    event_type: Optional[str] = None
    event_date: str
    start_time: str
    end_time: Optional[str] = None
    venue: Optional[str] = None
    online_link: Optional[str] = None
    maximum_capacity: int = Field(gt=0)
    registration_deadline: Optional[str] = None
    status: Optional[str] = "PUBLISHED"


class EventUpdate(BaseModel):
    event_name: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[str] = None
    event_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    venue: Optional[str] = None
    online_link: Optional[str] = None
    maximum_capacity: Optional[int] = None
    registration_deadline: Optional[str] = None
    status: Optional[str] = None


class EventOut(BaseModel):
    event_id: str
    organizer_id: str
    event_name: str
    description: Optional[str]
    event_type: Optional[str]
    event_date: str
    start_time: str
    end_time: Optional[str]
    venue: Optional[str]
    online_link: Optional[str]
    maximum_capacity: int
    registration_deadline: Optional[str]
    status: str

    class Config:
        from_attributes = True


# --- RSVP ---
class RSVPRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v):
        if v not in ("GOING", "MAYBE", "NOT_GOING"):
            raise ValueError("status must be GOING, MAYBE, or NOT_GOING")
        return v


class RSVPCounts(BaseModel):
    GOING: int = 0
    MAYBE: int = 0
    NOT_GOING: int = 0
    WAITLISTED: int = 0


class RSVPResult(BaseModel):
    rsvp_id: str
    event_id: str
    user_id: str
    status: str
    counts: RSVPCounts


class PublicCounts(BaseModel):
    going: int
    maybe: int
    not_going: int
    waitlisted: int
    available_seats: int


# --- Announcements ---
class AnnouncementCreate(BaseModel):
    title: str
    message: str


class AnnouncementOut(BaseModel):
    announcement_id: str
    event_id: str
    title: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Notifications ---
class NotificationOut(BaseModel):
    notification_id: str
    user_id: str
    event_id: Optional[str]
    type: str
    message: str
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- Analytics ---
class GrowthPoint(BaseModel):
    date: str
    count: int


class AnalyticsOut(BaseModel):
    event_id: str
    total_responses: int
    going: int
    maybe: int
    not_going: int
    waitlisted: int
    waitlist_size: int
    maximum_capacity: int
    available_seats: int
    capacity_utilization_pct: float
    rsvp_growth_over_time: List[GrowthPoint]
