# Real-Time Cloud-Based Event Planning & RSVP Tracker

A web application where organizers create events and attendees RSVP as **Going**, **Maybe** or **Not Going**. RSVP counts update **instantly in every open browser** through WebSockets, event capacity is enforced even under simultaneous requests, and overflow attendees are placed on an automatic waitlist.

## Features

**Organizer**
- Register and log in with an organizer role
- Create, update and cancel events (date, time, venue or online link, maximum capacity, registration deadline)
- Live dashboard: Going / Maybe / Not Going / Waitlisted counts, seats left and capacity utilization
- Post announcements that appear instantly on the event page
- View the attendee list and RSVP growth analytics for their own events

**Attendee**
- Register and log in with an attendee role
- Browse upcoming events and view event details
- RSVP Going, Maybe or Not Going, change the response later, or cancel it
- See live counts and announcements without refreshing the page
- Automatically waitlisted when the event is full, and promoted (first come, first served) when a seat opens

**System**
- Real-time updates over WebSockets with automatic reconnection
- Race-condition-safe capacity control
- Role-based access control, token authentication, rate limiting
- In-app notifications for RSVP confirmation, waitlist promotion, announcements and cancellations
- Automatic interactive API documentation

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, React Router |
| Backend | Python, FastAPI, Uvicorn |
| Database | SQLAlchemy ORM with SQLite (PostgreSQL compatible) |
| Real-time | WebSockets |
| Authentication | Signed expiring tokens (JWT style), PBKDF2 password hashing |
| Testing | pytest, FastAPI TestClient |

## Architecture

```
React app (browser)
   |  HTTP (REST)                     ^  WebSocket push
   v                                  |
FastAPI  -->  RSVP service  -->  SQLAlchemy  -->  SQLite / PostgreSQL
   |
   +-- WebSocket manager: tracks connections per event, broadcasts updates
```

1. A user clicks **Going**. The browser sends `POST /api/events/{id}/rsvp`.
2. The RSVP service checks capacity and saves the response in a single database operation.
3. The server reads the fresh counts and broadcasts them to every browser connected to that event.
4. All viewers see the new numbers immediately.

## How Real-Time Updates Work

Each event page opens a WebSocket to `/ws/events/{event_id}`. The server keeps the open connections for each event and sends a message whenever an RSVP is created, changed or cancelled, or an announcement is posted. The React hook (`src/hooks/useEventSocket.js`) reconnects automatically with increasing delay if the connection drops. The organizer dashboard covers many events at once, so it refreshes on a short 5-second timer instead.

## Concurrency Control

If capacity is checked and the RSVP is saved in two separate steps, two people clicking at the same moment can both take the last seat. This project combines the check and the update into one atomic statement:

```sql
UPDATE events
SET going_count = going_count + 1
WHERE event_id = :id AND going_count < maximum_capacity
```

The database processes these one at a time. If one row changes, the user got a seat. If zero rows change, the event was full and the user is waitlisted. A test starts 10 threads competing for a single seat and confirms exactly one gets **Going** and nine are waitlisted.

## Database Schema

| Table | Purpose |
|---|---|
| `users` | Accounts with role: organizer, attendee or admin |
| `events` | Event details, `maximum_capacity`, `going_count`, status |
| `rsvps` | One RSVP per user per event (unique constraint) |
| `waitlist` | Ordered queue of waiting attendees |
| `announcements` | Organizer messages per event |
| `notifications` | In-app notifications per user |

## Roles and Permissions

| Action | Attendee | Organizer | Admin |
|---|:---:|:---:|:---:|
| Register, log in, browse events | Yes | Yes | Yes |
| RSVP, update or cancel own RSVP | Yes | Yes | Yes |
| Create an event | No | Yes | Yes |
| Edit or cancel an event | No | Own events | Any |
| View attendee list and analytics | No | Own events | Any |
| Post announcements | No | Own events | Any |

## API Overview

Interactive documentation is available at `http://localhost:8000/docs` while the backend runs.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/register` | Create an account |
| POST | `/api/login` | Log in and receive a token |
| POST | `/api/events` | Create an event (organizer) |
| GET | `/api/events` | List events (`?upcoming=true` for future events) |
| GET | `/api/events/{id}` | Event details |
| GET | `/api/events/{id}/counts` | Public live counts (no personal data) |
| PUT / DELETE | `/api/events/{id}` | Update / cancel an event (owner) |
| POST / DELETE | `/api/events/{id}/rsvp` | Create or update / cancel own RSVP |
| GET | `/api/events/{id}/rsvps` | Attendee list (owner) |
| GET | `/api/rsvps/me` | Current user's RSVPs |
| GET | `/api/events/{id}/analytics` | Analytics (owner) |
| POST / GET | `/api/events/{id}/announcements` | Post (owner) / read announcements |
| GET | `/api/notifications` | Current user's notifications |
| PUT | `/api/notifications/{id}/read` | Mark a notification as read |
| WS | `/ws/events/{id}` | Live counts and announcements |

Errors return JSON with an appropriate status code: 400, 401, 403, 404, 409, 429 or 500.

## Getting Started

### Prerequisites
- Python 3.10 or newer
- Node.js 18 or newer

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # macOS/Linux: cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

Backend: `http://localhost:8000`, API docs: `http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server forwards `/api` and `/ws` to the backend, so no extra configuration is needed locally.

### 3. Try it

1. Register an **Organizer** and create an event with capacity 2 and a future date.
2. In a second browser or an incognito window, register an **Attendee** and open the event.
3. Click **Going** and watch the counts change live in both windows.
4. Register more attendees until the event is full. The next one is waitlisted.
5. Cancel a "Going" RSVP and the first waitlisted attendee is promoted automatically.
6. As the organizer, post an announcement and watch it appear on the open event page.

## Configuration

Copy `backend/.env.example` to `backend/.env`.

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Secret used to sign tokens. Set a long random value. | dev value |
| `TOKEN_TTL_SECONDS` | Token lifetime | `86400` |
| `DATABASE_URL` | Database connection string | `sqlite:///./event_rsvp.db` |
| `CORS_ORIGIN` | Allowed frontend origin | `*` |
| `RATE_LIMIT_PER_MINUTE` | Requests per minute per IP | `120` |

To use PostgreSQL, install a driver (`pip install psycopg2-binary`) and set `DATABASE_URL=postgresql://user:password@host:5432/dbname`. When the frontend is hosted separately from the backend, set `VITE_API_BASE` and `VITE_WS_BASE` in `frontend/.env` (see `frontend/.env.example`). Never commit real secrets. `.env` is listed in `.gitignore`.

## Testing

```bash
cd backend
python -m pytest -v
```

The 24 automated tests cover registration and login, duplicate accounts, role restrictions, event creation and access control, RSVP create / update / cancel, duplicate-RSVP prevention, registration deadline, capacity and waitlist, waitlist promotion, announcements, notifications, analytics, invalid tokens, the 10-thread race-condition test, and a WebSocket test that confirms live counts are pushed after an RSVP.

## Security

- Passwords are hashed with PBKDF2-HMAC-SHA256 and never stored in plain text
- Signed tokens that expire; tampered or expired tokens are rejected
- Role checks are enforced on the server for every protected action
- Organizers can only modify or view data for their own events
- Generic login error message so registered emails are not revealed
- Per-IP rate limiting (HTTP 429)
- Secrets come from environment variables, not source code
- Unexpected errors return a generic message; details are only logged on the server

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI app, CORS, rate limiting, error handling
│   │   ├── database.py             Database engine and session
│   │   ├── models.py               ORM models
│   │   ├── schemas.py              Request / response validation
│   │   ├── security.py             Tokens, password hashing, role checks
│   │   ├── websocket_manager.py    Connection tracking and broadcasts
│   │   ├── routers/                auth, events, rsvp, announcements, notifications, analytics
│   │   └── services/               rsvp_service.py, analytics_service.py
│   ├── tests/test_api.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/                  Home, Login, Register, dashboards, EventDetail
│   │   ├── hooks/useEventSocket.js
│   │   └── api.js
│   ├── package.json
│   └── vite.config.js
├── docs/screenshots/
└── README.md
```

## Limitations

- No email or SMS notifications; notifications are stored in the database and available through the API
- The frontend has no notifications page or event-edit screen yet (both are supported by the API)
- No attendee invitation links; events are open to any registered attendee
- WebSocket broadcasting runs inside a single server process; running several instances would need a shared message layer such as Redis

## Future Improvements

- Deploy the backend, frontend and PostgreSQL database to a cloud provider
- Managed authentication (Supabase Auth or Firebase Auth)
- Email notifications, QR-code check-in and calendar (`.ics`) export
- Invitation links with tokens
- Redis pub/sub for multi-instance real-time updates
- CI with GitHub Actions to run tests on every push

## Author

**Shikha** - MCA, Chitkara University
