# CLAUDE.md — Perisai Nusantara (PN-X)

Konteks & aturan untuk Claude Code saat mengerjakan repo ini. Dokumen produk:
`docs/PRD-PN-X-v1.2.md`. Baca PRD sebelum menambah fitur besar.

## Apa ini
Prototipe **platform pertahanan siber defensif** (SOC + SOAR + multi-agent) untuk
lingkungan pengembangan dengan **data simulasi**. Semua integrasi perangkat nyata
(EDR, firewall) diwakili **mock adapter**. Murni defensif — operasi ofensif/hack-back
berada **di luar ruang lingkup** (PRD §4.2).

## RBAC — model 4-role (PRD §3)
Permission-based (`require_permission`), bukan route per-role. Empat role hasil
konsolidasi dari sembilan persona, menjaga pemisahan tugas (eksekusi ⟂ persetujuan ⟂
validasi atribusi ⟂ audit):
- **`operator`** — kerja tangan SOC: `sim:run`, `alert:triage`, `detect:run/manage`,
  `incident:manage`, `soar:execute`, `agent:run`, `report:generate`. **Tak** menyetujui.
- **`commander`** — supervisi & admin: `soar:approve/manage`, `report:approve/manage`,
  `user:*`, `asset:manage`, `audit:read/verify`, `agent:run`. **Tak** `soar:execute`/`sim:run`.
- **`intel`** — `intel:manage`, `agent:run`, `attribution:validate` (satu-satunya).
- **`auditor`** — read-only: `audit:read`, `audit:verify`.

Sumber kebenaran: `backend/app/core/rbac.py` (enum `Role` + `ROLE_PERMISSIONS`) &
`frontend/src/lib/rbac.ts`. Tak ada role yang bisa mengubah audit.

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
  correlation/ korelasi alert -> Insiden (per entitas) + case management (M7)
  soar/        playbook + Matriks Otonomi (config) + approval/timeout/eskalasi +
               rollback + dry-run + adapter mock + notifikasi in-app (M8)
  reports/     metrik Situasi/Eksekutif + coverage ATT&CK (teknik prioritas) +
               ELANG-6 Reporter (template deterministik) + penulis PDF tanpa
               dependensi + jadwal laporan (M9)
  agents/      ELANG-2/3/6 (Sovereign LLM): sandbox prompt (data tak tepercaya +
               deteksi injection) + grounding klaim (rujuk ID) + validasi skema +
               klien LLM (stub offline default / Ollama loopback-only) (M10, F2)
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
      & penjelajah event + pemicu simulator (dev, role operator).
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
      **Gerbang arah anti-FP**: selain skor IF ≥ 0.60, temuan wajib menyimpang ke arah
      mencurigakan (CV interval/payload lebih rendah, atau volume lebih tinggi) ≥
      `min_suspicious_z` (5σ). Aktivitas *lebih rendah* dari baseline bukan sinyal C2.
      Kalibrasi 30 seed×durasi: normal maks ~3.6σ, beaconing min ~10.6σ. Baseline bersih
      wajib nol temuan (lihat `test_clean_baseline_has_no_false_positive`).
- [x] **M7** — Insiden + korelasi + case management: model `Incident` + `IncidentNote`,
      mesin korelasi alert->insiden per entitas (host/aset) dengan `correlation_key`
      idempotent, agregasi **teknik ATT&CK** + severity tertinggi, siklus respons
      (open/investigating/contained/closed), **linimasa kasus** (catatan + jejak
      status/penugasan), halaman Insiden + detail. Role operator/commander
      punya `incident:manage`.
- [x] **M8** — SOAR: model `Playbook`/`PlaybookRun`/`ActionExecution`/`Approval`/
      `Notification`/`BreakGlass`; **Matriks Otonomi** (§7) dari konfigurasi
      `autonomy_matrix.json` (bukan hardcode); keputusan auto/approval = severity ×
      kritikalitas; **approval + timeout** (approval terkonsolidasi ke Commander;
      High×K2 timeout→AUTO; K1 tanpa auto); **rollback** (FR-304); **dry-run** (FR-306);
      adapter **mock** (§A.5 no.8); notifikasi in-app; **break-glass** (§7 no.3);
      halaman SOAR (approval, run, rollback, break-glass) + "jalankan playbook" dari
      detail insiden. Matriks teruji untuk **semua** kombinasi severity×kritikalitas.
- [x] **M9** — Situasi & pelaporan: **dashboard Situasi (COP)** (postur, insiden
      aktif/severity, approval tertunda, kesehatan sumber data, tren 24 jam, peta
      segmen), **dashboard Eksekutif** (KPI MTTD/MTTR/FP rate/coverage + pembanding
      periode + tren harian), **Coverage ATT&CK** (matriks taktik × teknik prioritas
      + gap analysis, metrik tervalidasi), halaman **Audit** (M2, verifikasi hash
      chain), **ELANG-6 Reporter** template deterministik (harian/mingguan/bulanan/
      insiden/eksekutif/kepatuhan) dengan **ekspor PDF** (penulis PDF mandiri, tanpa
      dependensi) + **jadwal** (run-due). Laporan lahir `draft`, wajib **disetujui
      manusia** sebelum kirim eksternal. Role commander: `report:approve`+`manage`.
- [x] **M10** — (F2) **Agen LLM Sovereign**: `AttributionHypothesis` + agen
      **ELANG-3** (hipotesis atribusi + confidence + bukti ber-ID + alternatif),
      **ELANG-6** (ringkasan insiden), **ELANG-2** (threat hunting). Klien LLM:
      **stub deterministik offline** default; **Ollama loopback-only** (egress guard,
      FR-404). Kontrol §11 ditegakkan: data lapangan **tak tepercaya** (dibungkus +
      deteksi prompt-injection), output **divalidasi skema Pydantic**, klaim
      **grounded** (wajib rujuk ID event/alert; yang mengarang dibuang), agen **tak
      pernah** memanggil adapter (§A.5 no.1), severity final tetap dari rule engine.
      Label **Tervalidasi** hanya `intel` (`attribution:validate`). Panel
      "Analisis AI" di detail insiden. Audit aktor=agen.

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
Atau dari UI: login sebagai `operator` → halaman **Event** → "Jalankan skenario"
(endpoint `POST /dev/simulate`, hanya non-produksi).
