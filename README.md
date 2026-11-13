# Prototipe Platform Perisai Pertahanan Cyber Nusantara X (PN-X) Angkatan Darat

Prototipe **platform pertahanan siber adaptif** (SOC + SOAR + multi-agent MATA ELANG).
Dokumen produk: [`docs/PRD-PN-X-v1.2.md`](docs/PRD-PN-X-v1.2.md).

> Murni **defensif**, berjalan dengan **data simulasi**. Operasi ofensif/hack-back di luar
> ruang lingkup (PRD §4.2). Semua adapter perangkat nyata diwakili **mock**. Tidak ada
> panggilan ke layanan eksternal, dan agen AI memakai stub LLM offline secara default.

---

## Menjalankan di Windows (untuk juri & penguji)

### 1. Prasyarat (sekali saja)
| Perangkat lunak | Versi | Catatan |
|---|---|---|
| [Python](https://www.python.org/downloads/) | 3.12 atau lebih baru | Saat install, **centang "Add python.exe to PATH"** |
| [Node.js](https://nodejs.org/) | 20 LTS atau lebih baru | Pilihan default installer sudah cukup |
| [Git](https://git-scm.com/download/win) | bebas | Atau unduh ZIP dari GitHub (**Code → Download ZIP**) |

Kebutuhan mesin: RAM ≥ 4 GB, ruang disk ±1 GB, dan internet **hanya saat setup** (unduh
paket Python & npm). Setelah itu aplikasi berjalan sepenuhnya offline.

### 2. Unduh kode
```bat
git clone <URL-repo-ini>
cd perisai-nusantara
```

### 3. Setup (sekali saja, ±3–5 menit)
Double-click **`setup-windows.bat`**, atau jalankan dari Command Prompt:
```bat
setup-windows.bat
```
Skrip ini membuat virtualenv Python, memasang dependensi backend & frontend, menyalin
`backend\.env.example` menjadi `backend\.env`, lalu **mengisi data demo**: 4 akun per
role, 11 aset (K1/K2/K3), baseline 14 hari, 3 skenario serangan simulasi (brute force
T1110, beaconing C2 T1071, ransomware T1486), alert, insiden, dan playbook SOAR.

### 4. Nyalakan aplikasi
Double-click **`start-windows.bat`**. Dua jendela akan terbuka (**PN-X Backend** dan
**PN-X Frontend**), lalu browser membuka **http://localhost:5173**.

| Alamat | Isi |
|---|---|
| http://localhost:5173 | Aplikasi (UI) |
| http://localhost:8000/docs | Dokumentasi API (Swagger) |

Untuk mematikan, tutup kedua jendela tersebut.

### 5. Login (akun demo)
Password semua akun: **`ChangeMe123!`**

| Username | Role | Coba fitur ini |
|---|---|---|
| `operator` | Analis SOC | Situasi, antrian alert (`j`/`k`, `a`, `e`, `x`), insiden + **alur OODA**, jalankan playbook / dry-run, simulator serangan (halaman **Event**), agen AI |
| `commander` | Supervisi | **Setujui/tolak approval** SOAR (aksi K1 menunggu Commander), break-glass, laporan, kelola pengguna, audit |
| `intel` | Threat intel | IoC & impor STIX, **validasi hipotesis atribusi** ELANG-3 |
| `auditor` | Audit (read-only) | Log audit + **verifikasi hash chain** |

Model ini memisahkan tugas: yang mengeksekusi tidak bisa menyetujui aksinya sendiri, dan
tidak ada role yang bisa mengubah audit.

**Skenario demo singkat:** login `operator` → **Situasi** → klik host bertanda di *Peta
segmen jaringan* → lihat *Alur investigasi (OODA)* di detail insiden → logout, login
`commander` → **SOAR** → setujui approval → kembali ke insiden: fase *Act* terisi.

### Akses dari perangkat lain di WiFi/LAN yang sama
```bat
start-windows.bat lan
```
Buka `http://<IP-laptop>:5173` dari perangkat lain. Alamatnya tertera sebagai
**Network** di jendela *PN-X Frontend*. Jika Windows Firewall bertanya, pilih **Allow**.
Backend tetap hanya mendengarkan di `127.0.0.1`; frontend meneruskan `/api` ke backend.

> Mode ini memakai password demo dan `SECRET_KEY` bawaan, jadi **hanya untuk jaringan
> tepercaya** (ruang presentasi/lab). Jangan dibuka ke internet publik.

### Mengembalikan data demo
Double-click **`reset-demo.bat`**. Semua data dihapus lalu diisi ulang ke kondisi awal.
Hanya untuk lingkungan demo; skrip ini menolak berjalan di `ENVIRONMENT=prod`.

### Jika ada masalah
| Gejala | Solusi |
|---|---|
| `Python tidak ditemukan` / `'python' is not recognized` | Install ulang Python dan centang **Add to PATH**, lalu buka Command Prompt baru |
| `Node.js tidak ditemukan` | Install Node.js LTS, lalu buka Command Prompt baru |
| Halaman terbuka tapi **login gagal** | Jendela *PN-X Backend* tertutup atau error. Jalankan ulang `start-windows.bat` |
| `address already in use` / port 8000 atau 5173 terpakai | Tutup aplikasi lain yang memakai port itu, atau tutup jendela PN-X lama |
| Browser terbuka sebelum server siap | Tunggu beberapa detik lalu refresh (F5) |
| Data terasa berantakan setelah banyak dicoba | Jalankan `reset-demo.bat` |

<details>
<summary><b>Menjalankan manual (tanpa skrip .bat)</b></summary>

```bat
REM Backend (jendela 1)
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python -m app.demo
.venv\Scripts\uvicorn app.main:app --port 8000

REM Frontend (jendela 2)
cd frontend
npm ci
npm run dev
```
</details>

---

## Untuk pengembang

### Test (tanpa Docker, SQLite in-memory)
```bat
cd backend
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\pytest -q
```
Di Linux/macOS ganti `.venv\Scripts\` menjadi `.venv/bin/`.

### Stack penuh (Docker, PostgreSQL 16)
```bash
cp backend/.env.example backend/.env       # atur SECRET_KEY untuk non-dev
docker compose up --build                  # API & Swagger: http://localhost:8000/docs
docker compose exec api python -m app.demo # isi data demo
```

### Perintah data
| Perintah (di folder `backend`) | Fungsi |
|---|---|
| `python -m app.demo` | Isi data demo lengkap. Aman dijalankan ulang (simulator dilewati bila event sudah ada) |
| `python -m app.demo --reset` | Hapus semua data lalu isi ulang (bukan untuk prod) |
| `python -m app.seed` | Hanya akun demo per role |
| `python -m app.simulator all` | Hanya aset + baseline 14 hari + semua skenario serangan |

## Arsitektur ringkas
| Komponen | Isi |
|---|---|
| `backend/app/core` | config, database, security (JWT/TOTP/bcrypt), RBAC 4 role |
| `backend/app/audit` | audit hash chain + verifikasi integritas |
| `backend/app/simulator`, `ingest` | armada aset, baseline historis, skenario serangan, normalisasi event |
| `backend/app/intel` | IoC, impor STIX 2.1, mirror enrichment lokal |
| `backend/app/detection` | aturan Sigma/threshold, pencocokan IoC, ATT&CK, ELANG-1 (IsolationForest) |
| `backend/app/correlation` | korelasi alert → insiden, case management, alur OODA |
| `backend/app/soar` | playbook, **Matriks Otonomi** (konfigurasi), approval/timeout/eskalasi, rollback, dry-run, adapter mock |
| `backend/app/reports` | dashboard Situasi/Eksekutif, coverage ATT&CK, ELANG-6 Reporter + PDF |
| `backend/app/agents` | ELANG-2/3/6: sandbox prompt, grounding klaim, validasi skema, LLM lokal |
| `frontend/` | Vue 3 + Vite + Tailwind, design tokens (PRD Lampiran C), i18n id/en |

Status milestone lengkap ada di [`CLAUDE.md`](CLAUDE.md) dan PRD §A.3.

## Prinsip keamanan
- **Audit immutable**: entri audit tidak pernah di-update/hapus. Setiap entri merantai hash
  entri sebelumnya, dan `/audit/verify` menunjuk posisi entri yang rusak.
- **Pemisahan tugas**: eksekusi ⟂ persetujuan ⟂ validasi atribusi ⟂ audit.
- **MFA (TOTP)** per akun, **RBAC** di setiap endpoint.
- **Tanpa egress**: enrichment dari mirror lokal; LLM hanya stub offline atau Ollama loopback.
- Agen AI **tidak pernah** memanggil adapter eksekusi; semua aksi lewat SOAR + Matriks Otonomi.
