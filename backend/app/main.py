"""
main.py - FastAPI application factory. Run with:
    uvicorn app.main:app --reload --port 8000
"""

import os
import time
import logging
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.database import Base, engine
from app.routers import auth, events, rsvp, announcements, notifications, analytics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("event_rsvp")

Base.metadata.create_all(bind=engine)  # idempotent - creates tables if missing

app = FastAPI(title="Real-Time Cloud Event & RSVP Tracker (Option B)", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("CORS_ORIGIN", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Simple in-memory sliding-window rate limiter per IP ---
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "120"))
_hits = defaultdict(deque)


@app.middleware("http")
async def rate_limit_and_log(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        window = _hits[ip]
        now = time.time()
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= RATE_LIMIT:
            return JSONResponse({"error": "rate_limited", "message": "Too many requests, slow down."}, status_code=429)
        window.append(now)
    logger.info("%s %s", request.method, request.url.path)
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse({"error": "internal_server_error", "message": "Something went wrong. Please try again."},
                         status_code=500)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "event-rsvp-tracker-option-b"}


app.include_router(auth.router)
app.include_router(events.router)
app.include_router(rsvp.router)
app.include_router(rsvp.ws_router)
app.include_router(announcements.router)
app.include_router(notifications.router)
app.include_router(analytics.router)
