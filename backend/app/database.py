"""
database.py
Purpose: SQLAlchemy engine/session setup. Reads DATABASE_URL from the
environment - defaults to a local SQLite file for development, but
pointing it at a Supabase/Postgres connection string
(postgresql://user:pass@host:5432/dbname) is a ONE-LINE change with
zero code changes elsewhere. This is what "Option B - cloud database"
looks like in practice: the ORM layer is database-agnostic.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./event_rsvp.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

if DATABASE_URL.startswith("sqlite"):
    # WAL mode lets concurrent readers proceed while a writer holds a
    # transaction, which is what makes the multi-threaded RSVP concurrency
    # test (and real concurrent usage) behave well against SQLite. Has no
    # effect on Postgres/Supabase, which handles this natively.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency - yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
