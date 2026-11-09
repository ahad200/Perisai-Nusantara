"""Konfigurasi aplikasi (pydantic-settings).

SECRET_KEY wajib di-set di lingkungan non-dev. Default hanya untuk dev/test.
Tidak ada konfigurasi yang mengizinkan egress ke layanan eksternal (PRD §A.5 no.5).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Identitas
    app_name: str = "Perisai Nusantara (PN-X)"
    environment: str = "dev"  # dev | staging | prod

    # Database. Default dev memakai SQLite agar bisa jalan tanpa Docker.
    # Produksi: postgresql+psycopg://user:pass@db:5432/pnx
    database_url: str = "sqlite:///./pnx_dev.db"

    # Keamanan / JWT
    secret_key: str = "dev-insecure-change-me-0000000000000000"  # WAJIB diganti di prod
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    mfa_token_ttl_minutes: int = 5  # token sementara antara password & OTP

    # TOTP
    totp_issuer: str = "PN-X"

    # Sovereign LLM (M10, F2). Default "stub": deterministik, offline, tanpa jaringan
    # (etos "semua adapter mock"). "ollama": LLM lokal open-weight — HANYA loopback
    # (air-gapped, egress diblokir, FR-404 / §A.5 no.5). Tak ada opsi host eksternal.
    llm_provider: str = "stub"  # stub | ollama
    llm_model: str = "llama3.1:8b"
    llm_base_url: str = "http://127.0.0.1:11434"  # wajib loopback — dijaga di agents/llm.py
    llm_timeout_seconds: int = 30

    @property
    def is_prod(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_prod and settings.secret_key.startswith("dev-insecure-change-me"):
        raise RuntimeError(
            "SECRET_KEY default tidak boleh dipakai di produksi. Set env SECRET_KEY."
        )
    return settings
