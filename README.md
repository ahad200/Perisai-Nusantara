# Prototipe Platform Perisai Pertahanan Cyber Nusantara X (PN-X) Angkatan Darat

Prototipe **platform pertahanan siber adaptif** (SOC + SOAR + multi-agent MATA ELANG).
Dokumen produk: [`docs/PRD-PN-X-v1.2.md`](docs/PRD-PN-X-v1.2.md).

> Murni **defensif**, berjalan dengan **data simulasi**. Operasi ofensif/hack-back di luar
> ruang lingkup (PRD §4.2). Semua adapter perangkat nyata diwakili **mock**.

## Status

**M1 — Fondasi backend** (selesai): FastAPI + PostgreSQL + Alembic, model `User` &
`AuditEntry`, auth **JWT + TOTP (MFA)**, **RBAC** 9 role, dan **audit hash chain**
dengan endpoint verifikasi integritas. Roadmap lengkap M1–M10 di [`CLAUDE.md`](CLAUDE.md).

## Mulai cepat

### Test lokal (tanpa Docker, SQLite)
```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Linux/mac: .venv/bin/pip
.venv/Scripts/pytest -q
```

### Stack penuh (Docker)
```bash
cp backend/.env.example backend/.env       # atur SECRET_KEY untuk non-dev
docker compose up --build
# API & Swagger: http://localhost:8000/docs
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed  # user demo per role (cetak secret TOTP)
```

## Arsitektur ringkas (M1)

| Komponen | Isi |
|---|---|
| `backend/app/core` | config, database, security (JWT/TOTP/bcrypt), RBAC |
| `backend/app/models` | `User`, `AuditEntry` (PRD §12) |
| `backend/app/audit` | layanan hash chain + verifikasi integritas |
| `backend/app/api` | router: `auth`, `users`, `audit` |
| `backend/tests` | pytest: auth, RBAC, hash chain + uji tamper |

## Prinsip keamanan yang sudah ditegakkan di M1
- **Audit immutable**: entri audit tak pernah di-update/hapus; setiap entri merantai
  hash entri sebelumnya (`prev_hash`). Endpoint `/audit/verify` mendeteksi tamper &
  menunjuk posisi entri yang rusak.
- **Pemisahan tugas (SoD)**: `auditor` read-only; tidak ada role yang bisa mengubah
  audit; `platform_admin` kelola user tapi tak bisa sentuh audit log.
- **MFA (TOTP)** per akun, **RBAC** di setiap endpoint.
