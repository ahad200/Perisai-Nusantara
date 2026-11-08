# CLAUDE.md — Perisai Nusantara (PN-X)

Konteks & aturan untuk Claude Code saat mengerjakan repo ini. Dokumen produk:
`docs/PRD-PN-X-v1.2.md`. Baca PRD sebelum menambah fitur besar.

## Apa ini
Prototipe **platform pertahanan siber defensif** (SOC + SOAR + multi-agent) untuk
lingkungan pengembangan dengan **data simulasi**. Semua integrasi perangkat nyata
(EDR, firewall) diwakili **mock adapter**. Murni defensif — operasi ofensif/hack-back
berada **di luar ruang lingkup** (PRD §4.2).

## Aturan Inti (PRD §A.5) — WAJIB
1. Agen LLM **tidak boleh** memanggil adapter eksekusi langsung. Hanya `app/soar/` yang boleh.
2. Semua keputusan auto/approval wajib lewat `app/soar/autonomy.py` yang membaca
   **konfigurasi** Matriks Otonomi (PRD §7), bukan hardcode.
3. Setiap perubahan state penting (aksi, approval, perubahan aturan/playbook, login)
   wajib menulis `AuditEntry` (hash chain — lihat `app/audit/`).
4. Data log yang masuk ke prompt LLM wajib dibungkus sebagai **data tidak tepercaya**,
   dan output LLM wajib divalidasi dengan skema Pydantic.
5. **Tidak ada panggilan HTTP ke layanan eksternal** dari backend. Enrichment hanya
   dari tabel mirror lokal.
6. Aset tanpa kritikalitas diperlakukan sebagai **K1** (fail-safe).
7. Setiap fitur baru disertai test (pytest). Matriks Otonomi wajib punya test untuk
   **semua kombinasi** severity × kritikalitas.
8. Semua adapter di prototipe adalah **mock** yang hanya mencatat aksi.
9. Frontend wajib mengikuti **PRD Lampiran C**: design tokens, IBM Plex Sans/Mono,
   tema gelap grafit, warna severity hanya untuk severity, tanpa pola anti-slop (C.5).
   Bangun komponen dasar + halaman `/dev/components` sebelum membangun halaman.

## Struktur
```
backend/app/
  core/        config, database, security (JWT/TOTP/bcrypt), rbac
  models/      SQLAlchemy (PRD §12)
  schemas/     Pydantic request/response
  audit/       hash chain + verifikasi
  api/         router FastAPI per domain
  ingest/      normalisasi event ke skema umum (M3)
  simulator/   armada aset + baseline historis + skenario serangan (M3)
  intel/       IoC, impor STIX 2.1, mirror enrichment lokal, siklus hidup (M4)
  detection/   aturan Sigma/threshold + pencocokan IoC -> Alert, pemetaan ATT&CK (M5);
               ELANG-1 IsolationForest anomali + penjelasan fitur (M6)
  correlation/ soar/ adapters/ agents/ reports/  (milestone berikutnya)
backend/tests/   pytest
frontend/        Vue 3 (M2)
```

## Konvensi
- Python 3.12 (produksi/Docker). Lokal diuji di 3.14 memakai **SQLite**; produksi PostgreSQL 16.
- Test memakai SQLite in-memory (lihat `tests/conftest.py`), tanpa perlu Docker.
- Migrasi: Alembic. Tabel dibuat di milestone yang memakainya (PRD §A.3 aturan urutan).
- Audit: hash = SHA-256 atas `(prev_hash, timestamp, actor, action, object, payload_hash)`.
  Entri **tidak pernah** di-update/hapus. Tidak ada role yang boleh mengubah audit.

## Status Milestone (PRD §A.3)
- [x] **M1** — Fondasi backend: Docker Compose, FastAPI, PostgreSQL, Alembic,
      `User` & `AuditEntry`, auth JWT + TOTP (MFA), RBAC, audit hash chain + verifikasi.
- [x] **M2** — Fondasi frontend (Vue 3, design tokens, `/dev/components`, login+MFA, i18n,
      layout sidebar/header, halaman Pengguna & Audit terhubung API).
- [x] **M3** — Aset (K1/K2/K3) + Event, ingest + normalisasi, simulator (baseline ≥14 hari +
      skenario brute force/T1110, beaconing/T1071, ransomware/T1486), halaman inventaris aset
      & penjelajah event + pemicu simulator (dev, role purple_team/platform_admin).
- [x] **M4** — Threat intel: model `IoC` + siklus hidup (kedaluwarsa/whitelist/false-positive),
      impor STIX 2.1, tabel `EnrichmentRecord` (mirror WHOIS/GeoIP/reputasi lokal, data contoh),
      halaman IoC (impor, detail + enrichment, aksi siklus hidup). Enrichment **hanya** mirror
      lokal — tanpa egress (§A.5 no.5).
- [x] **M5** — Deteksi: model `DetectionRule` + `Alert`, mesin Sigma/threshold + **pencocokan IoC→event**,
      pemetaan **ATT&CK** (T1110/T1486/T1036/T1071/…), **antrian alert** dengan shortcut keyboard
      (j/k navigasi, a assign, e eskalasi, x tutup FP). Analis T1–T3 kini punya izin triase.
- [x] **M6** — ELANG-1: IsolationForest (implementasi mandiri, tanpa dependensi) dilatih dari
      baseline M3; deteksi anomali jaringan (beaconing C2) dengan **skor + fitur penyebab**
      (z-score terhadap baseline) di detail alert. Terintegrasi ke `/detection/run`.
- [ ] M7 — Incident + korelasi + case management.
- [ ] M8 — SOAR + Matriks Otonomi + approval/timeout/eskalasi + rollback + dry-run.
- [ ] M9 — Dashboard Situasi/Eksekutif + coverage ATT&CK + audit UI + ELANG-6 laporan.
- [ ] M10 — (F2) Agen LLM (Ollama) + AttributionHypothesis.

## Menjalankan
```bash
# Lokal (test)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/pytest -q

# Stack penuh
docker compose up --build        # API di http://localhost:8000/docs
docker compose exec api python -m app.seed          # user demo per role
docker compose exec api python -m app.simulator all # aset + baseline 14h + semua serangan
```

Simulator (data simulasi) — lihat `app/simulator/`:
```bash
python -m app.simulator seed-assets        # tanam armada aset K1/K2/K3
python -m app.simulator baseline --days 14 # baseline historis bersih
python -m app.simulator attack all         # bruteforce + beaconing + ransomware
```
Atau dari UI: login sebagai `purple_team` → halaman **Event** → "Jalankan skenario"
(endpoint `POST /dev/simulate`, hanya non-produksi).
