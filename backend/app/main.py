"""Entrypoint FastAPI PN-X (M1)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api import (
    routes_assets,
    routes_audit,
    routes_auth,
    routes_events,
    routes_intel,
    routes_sim,
    routes_users,
)
from app.core.config import get_settings
from app.core.database import Base, engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Di dev/test, buat tabel otomatis agar bisa jalan tanpa Alembic.
    # Di produksi gunakan: `alembic upgrade head`.
    if not settings.is_prod:
        import app.models  # noqa: F401  (registrasi model ke metadata)

        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Platform Pertahanan Siber Adaptif — prototipe (data simulasi). M1–M4.",
    lifespan=lifespan,
)

app.include_router(routes_auth.router)
app.include_router(routes_users.router)
app.include_router(routes_audit.router)
app.include_router(routes_assets.router)
app.include_router(routes_events.router)
app.include_router(routes_intel.router)
app.include_router(routes_sim.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "version": __version__}
