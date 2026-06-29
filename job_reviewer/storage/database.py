"""Database connection and session management."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def get_engine(db_url: str | None = None):
    url = db_url or os.environ.get("DATABASE_URL", "sqlite:///jobs.db")
    engine = create_engine(url, echo=False)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_wal(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


_engine = None
_SessionLocal = None


def init_db(db_url: str | None = None) -> None:
    global _engine, _SessionLocal
    _engine = get_engine(db_url)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        init_db()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
