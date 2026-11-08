"""Engine SQLAlchemy, SessionLocal, Base, dan dependency get_db."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    # Diperlukan agar SQLite bisa dipakai lintas thread (TestClient / uvicorn).
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Base deklaratif untuk seluruh model."""


def get_db() -> Iterator[Session]:
    """Dependency FastAPI: satu Session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
