# Real-Time Cloud-Based Event Planning & RSVP Tracker — Option B (Cloud-Ready)

This is the **Option B** build from the project brief: **React** frontend, **FastAPI** backend, a database layer that's a one-line swap to **Supabase Postgres**, and genuine **WebSocket** real-time updates (no polling). It reuses and hardens the same business logic proven out in the Option A (Flask/SQLite) build, now expressed with an ORM and true push updates.

> **On "Firebase/Supabase Auth" and a live Firestore/Supabase database:** those require *your own* cloud project credentials, which I don't have. This build uses the same JWT-token auth model Supabase Auth uses internally, and a SQLAlchemy database layer that runs on local SQLite today and points at a real Supabase Postgres connection string with a one-line `.env` change — no code changes. See "Going Fully Cloud" below for exactly what to do when you have your own Supabase/Render/Vercel accounts.

## What changed vs. the Option A (Flask/SQLite) build
| | Option A | Option B (this) |
|---|---|---|
| Backend framework | Flask | **FastAPI** |
| ORM | raw SQL | **SQLAlchemy** (Postgres-ready) |
| Frontend | plain HTML/JS | **React** (Vite) |
| Real-time mechanism | polling every 4–6s | **WebSockets** — instant push |
| Capacity race-condition fix | `BEGIN IMMEDIATE` transaction | **atomic conditional `UPDATE ... WHERE going_count < capacity`** (portable to Postgres) |
| API docs | manual | **automatic** — FastAPI serves interactive docs at `/docs` |

## Architecture
```
React (Vite, port 5173) ──HTTP──▶ FastAPI (port 8000) ──▶ SQLAlchemy ──▶ SQLite (dev) / Postgres-Supabase (prod)
                         ──WS───▶ /ws/events/{id}  (live RSVP counts + announcements, pushed instantly)
```

## Real-Time: How the WebSocket Push Actually Works
1. A browser on the event page opens `ws://.../ws/events/{event_id}` (`frontend/src/hooks/useEventSocket.js`).
2. The server tracks every open connection per event (`backend/app/websocket_manager.py`).
3. The instant anyone submits/cancels an RSVP, `backend/app/routers/rsvp.py` re-reads the live counts and calls `manager.broadcast(event_id, ...)`.
4. Every browser watching that event receives the new counts **immediately** — verified in `tests/test_api.py::test_websocket_receives_live_count_update` and by a live smoke test during development (a WebSocket client received the pushed update the moment a separate REST call submitted an RSVP).
5. The hook auto-reconnects with exponential backoff if the connection drops.

This is the direct analogue of a Firestore `onSnapshot()` listener or Supabase Realtime channel — swapping to either later means replacing this one hook and the `websocket_manager.py` broadcast call; nothing else in the app needs to change.

## The Concurrency Fix (Option B version)
Same problem as Option A (two simultaneous "last seat" requests could both pass a `count < capacity` check before either writes), fixed here with an **atomic conditional UPDATE** — a single SQL statement that combines the check and the increment so the database itself serializes it:
```sql
UPDATE events SET going_count = going_count + 1
WHERE event_id = :id AND going_count < maximum_capacity
```
If the statement affects 0 rows, that request lost the race and the user is waitlisted instead — with **zero window** for two requests to both "win." This pattern works identically on SQLite (used here) and Postgres/Supabase (used in production) with no code changes. See `backend/app/services/rsvp_service.py` and the 10-thread concurrency test in `backend/tests/test_api.py`.

## Local Setup

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit SECRET_KEY at minimum
uvicorn app.main:app --reload --port 8000
```
- API docs (auto-generated): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. Vite's dev proxy (`vite.config.js`) forwards `/api` and `/ws` to the backend on port 8000 automatically — no CORS setup needed locally.

### Run Tests
```bash
cd backend
pytest -v
```
24 tests, including the multi-threaded concurrency test and a real WebSocket push test. All pass as of this build.

## Going Fully Cloud (when you have your own accounts)
1. **Database → Supabase Postgres:** create a Supabase project, copy its Postgres connection string, set `DATABASE_URL=postgresql://...` in `backend/.env`. Nothing else changes — `database.py` and every model already target the ORM, not raw SQLite SQL.
2. **Auth → Supabase Auth (optional):** replace `issue_token`/`verify_token`/`get_current_user` in `backend/app/security.py` with calls to Supabase's Python client (`supabase-py`); every route already depends on `get_current_user`, so route code doesn't change.
3. **Backend hosting:** deploy `backend/` to Render, Railway, or Fly.io (all have free tiers and support long-lived WebSocket connections — confirm your host's plan supports WebSockets before picking one). Set `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGIN` as environment variables there.
4. **Frontend hosting:** deploy `frontend/` to Vercel or Netlify. Set `VITE_API_BASE` and `VITE_WS_BASE` (see `frontend/.env.example`) to your deployed backend's URL.
5. **Real-time upgrade (optional):** swap the custom WebSocket hook for Supabase Realtime's Postgres change-subscription, which pushes on any DB row change without your backend needing to call `broadcast()` explicitly.

## Folder Structure
```
optionB/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, CORS, rate limiting, error handling
│   │   ├── database.py        SQLAlchemy engine (SQLite dev / Postgres prod)
│   │   ├── models.py          ORM models
│   │   ├── schemas.py         Pydantic request/response validation
│   │   ├── security.py        JWT auth + RBAC dependencies
│   │   ├── websocket_manager.py   Real-time connection tracking + broadcast
│   │   ├── routers/           auth, events, rsvp (+ WebSocket route), announcements, notifications, analytics
│   │   └── services/          rsvp_service.py (the concurrency-safe core), analytics_service.py
│   ├── tests/test_api.py      24 automated tests incl. concurrency + WebSocket
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/             Home, Login, Register, OrganizerDashboard, AttendeeDashboard, EventDetail
│   │   ├── hooks/useEventSocket.js   the real-time WebSocket hook
│   │   └── api.js
│   ├── vite.config.js
│   ├── package.json
│   └── .env.example
└── README.md
```

## Everything Else (security, RBAC, scalability, failure handling, etc.)
Carries over unchanged in substance from the Option A README — same roles/permissions table, same security posture (hashed passwords, RBAC on every mutating route, generic error messages, no hardcoded secrets), same scalability discussion. The delta specific to this build is documented above.

## Author
Shikha — MCA Student, Chitkara University
