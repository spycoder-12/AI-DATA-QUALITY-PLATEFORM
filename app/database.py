"""Database layer (SQLAlchemy 2). Works with SQLite (default) or PostgreSQL.

The connection string comes from ``DATABASE_URL`` - no credentials in code.
The engine can be re-configured at runtime (used by tests).
"""
from __future__ import annotations

import logging
from typing import Iterator, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

log = logging.getLogger("aidq.db")


class Base(DeclarativeBase):
    pass


engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker] = None


def configure(database_url: str) -> Engine:
    """(Re)create the engine + session factory for ``database_url``."""
    global engine, SessionLocal
    if engine is not None:
        engine.dispose()
    kwargs = {"pool_pre_ping": True, "future": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(database_url, **kwargs)
    if database_url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _):          # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    return engine


def init_db() -> None:
    from app import models  # noqa: F401  (register tables)
    if engine is None:
        raise RuntimeError("Database engine is not configured.")
    Base.metadata.create_all(bind=engine)


def check_connection() -> Tuple[bool, str]:
    if engine is None:
        return False, "not configured"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:  # noqa: BLE001
        log.warning("Database check failed: %s", type(exc).__name__)
        return False, "unreachable"


def get_db() -> Iterator[Session]:
    if SessionLocal is None:
        raise RuntimeError("Database engine is not configured.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
