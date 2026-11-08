"""Router manajemen user (RBAC)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    actor: User = Depends(require_permission(Permission.USER_CREATE)),
    db: Session = Depends(get_db),
) -> User:
    exists = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username sudah dipakai")

    user = User(
        username=body.username,
        full_name=body.full_name,
        role=body.role.value,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    audit.record(
        db,
        action="user.create",
        actor_type="user",
        actor_id=actor.username,
        object_type="user",
        object_id=str(user.id),
        payload={"username": user.username, "role": user.role},
    )
    return user


@router.get("", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_permission(Permission.USER_READ)),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.execute(select(User).order_by(User.id)).scalars().all())


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    _: User = Depends(require_permission(Permission.USER_READ)),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User tidak ditemukan")
    return user
