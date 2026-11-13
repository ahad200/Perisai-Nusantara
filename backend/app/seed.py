"""Seed data demo: satu user per role (PRD §3). Jalankan: `python -m app.seed`.

Hanya untuk lingkungan pengembangan/prototipe. Password default WAJIB diganti.
"""
from __future__ import annotations

from sqlalchemy import select

from app import audit
from app.core.database import Base, SessionLocal, engine
from app.core.rbac import Role
from app.core.security import hash_password
from app.models.user import User

DEFAULT_PASSWORD = "ChangeMe123!"


def seed_users(db) -> list[str]:
    """Buat satu user demo per role (idempoten). Kembalikan username yang baru dibuat."""
    created: list[str] = []
    for role in Role:
        username = role.value  # username = nama role untuk demo
        existing = db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if existing:
            continue
        user = User(
            username=username,
            full_name=f"Demo {role.value}",
            role=role.value,
            hashed_password=hash_password(DEFAULT_PASSWORD),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        audit.record(
            db,
            action="user.create",
            actor_type="system",
            actor_id="seed",
            object_type="user",
            object_id=str(user.id),
            payload={"username": user.username, "role": user.role, "seed": True},
        )
        created.append(username)
    return created


def seed() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        created = seed_users(db)
        print("User demo dibuat:" if created else "Tidak ada user baru (semua sudah ada).")
        for u in created:
            print(f"  - {u} / {DEFAULT_PASSWORD}")
        print("\nGanti password default sebelum dipakai di lingkungan nyata.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
