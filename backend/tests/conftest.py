"""Fixtures pytest. Memakai SQLite in-memory (StaticPool) — tanpa Docker/Postgres.

Lifespan app TIDAK dijalankan (TestClient dipakai tanpa context manager), sehingga
tidak ada create_all ke DB nyata; tabel dibuat pada engine uji lewat fixture.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  registrasi model ke metadata
from app.core.database import Base, get_db
from app.core.rbac import Role
from app.core.security import hash_password
from app.main import app
from app.models.user import User


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def SessionFactory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def db_session(SessionFactory) -> Iterator[Session]:
    s = SessionFactory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client(SessionFactory) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[Session]:
        db = SessionFactory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    # Tanpa `with` → lifespan tidak dijalankan (lihat docstring modul).
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(SessionFactory) -> Callable[..., User]:
    """Factory membuat user langsung di DB (bootstrap, tanpa perlu admin lebih dulu)."""

    def _make(
        username: str,
        role: Role,
        password: str = "Password123!",
        *,
        mfa_enabled: bool = False,
        totp_secret: str | None = None,
    ) -> User:
        db = SessionFactory()
        try:
            user = User(
                username=username,
                full_name=f"Test {username}",
                role=role.value,
                hashed_password=hash_password(password),
                mfa_enabled=mfa_enabled,
                totp_secret=totp_secret,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            db.expunge(user)
            return user
        finally:
            db.close()

    return _make


def login(client: TestClient, username: str, password: str, otp_code: str | None = None) -> dict:
    resp = client.post(
        "/auth/login",
        json={"username": username, "password": password, "otp_code": otp_code},
    )
    return resp.json() | {"_status": resp.status_code}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
