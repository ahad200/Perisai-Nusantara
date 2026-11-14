# Prototipe Platform Perisai Pertahanan Cyber Nusantara X (PN-X) Angkatan Darat

Prototipe **platform pertahanan siber adaptif** (SOC + SOAR + multi-agent MATA ELANG).
Dokumen produk: [`docs/PRD-PN-X-v1.2.md`](docs/PRD-PN-X-v1.2.md).

> **Proyek independen** untuk keperluan kompetisi/riset, **bukan produk resmi TNI AD**.
> Konteks militer dipakai sebagai skenario rancangan.
>
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
git clone https://github.com/ahad200/Perisai-Nusantara.git
cd Perisai-Nusantara
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

### 6. Alur demo (8 langkah)
Mulai dari data bersih: **`reset-demo.bat`** (atau `python -m app.demo --reset` di folder
`backend`). Setelah menjalankan skenario, alert dan insiden **tidak** muncul sendiri:
jalankan **Antrian Alert → Jalankan deteksi**, lalu **Insiden → Jalankan korelasi**.

| # | Login | Langkah | Hasil yang diharapkan |
|---|---|---|---|
| 1 | `operator` | **Event → Jalankan skenario**, centang target `app-logistik-01`, klik **Brute force (T1110)** lalu **Beaconing C2 (T1071)**. Jalankan deteksi | Alert aturan threshold `PNX-BF-001` (T1110) + alert **ELANG-1** `PNX-ELANG1-001` (T1071) dengan skor & fitur penyebab di detail alert |
| 2 | `operator` | Jalankan korelasi, buka insiden `app-logistik-01` | **Satu insiden** berisi T1110 + T1071, linimasa kasus, dan **alur OODA** |
| 3 | `operator` | **Jalankan skenario**, centang `ws-staff-01` (K3) **dan** `cmd-core-01` (K1), klik **Enkripsi massal (T1486)**. Deteksi → korelasi → di detail tiap insiden klik **Jalankan playbook** | K3: `isolate_host` **auto**. K1: semua langkah **menunggu approval Commander**; hitungan approval di command bar bertambah (sinkron ≤ 60 dtk) |
| 4 | `operator` | Buka **SOAR** | Tidak ada tombol Setujui. Lewat API pun ditolak **403** (`soar:approve` hanya milik Commander) |
| 5 | `commander` | **SOAR** → pada approval `cmd-core-01`, **ketik `cmd-core-01`**, klik **Setujui** | Tombol Setujui baru aktif setelah nama aset cocok (dicek juga di backend). Aksi tereksekusi (mock) |
| 6 | `operator` | **SOAR** → buka run `ws-staff-01` → **Rollback** | Isolasi host & blokir IP dibatalkan; aksi yang tak reversibel (forensik) dilewati |
| 7 | `auditor` | **Audit → Verifikasi integritas**. Ubah satu baris (perintah di bawah), verifikasi lagi | Awalnya utuh; setelah diubah **gagal** dan menunjuk nomor entri yang rusak |
| 8 | `commander` | **Situasi** (peta segmen per host) → detail insiden → **Buat laporan** → **Laporan** → unduh PDF | Peta segmen urut kritikalitas; PDF laporan insiden (status DRAF) |

Uji tamper langkah 7 (jalankan di folder `backend`; kembalikan nilainya setelah demo):
```bat
.venv\Scripts\python -c "import sqlite3; c=sqlite3.connect('pnx_dev.db'); print(c.execute('SELECT id, actor_id FROM audit_entries WHERE id=10').fetchone()); c.execute(\"UPDATE audit_entries SET actor_id='penyusup' WHERE id=10\"); c.commit()"
```
Untuk mengembalikan: ganti `'penyusup'` dengan nilai `actor_id` asli yang tercetak, atau
jalankan `reset-demo.bat`.

Perintah skenario dari terminal (folder `backend`):
```bat
.venv\Scripts\python -m app.simulator targets
.venv\Scripts\python -m app.simulator attack bruteforce --target app-logistik-01
.venv\Scripts\python -m app.simulator attack beaconing  --target app-logistik-01
.venv\Scripts\python -m app.simulator attack ransomware --target ws-staff-01 --target cmd-core-01
```
Tanpa `--target`, tiap skenario memakai target bawaan (`app-logistik-01`, `ws-staff-03`,
`ws-staff-05`).

### Menjalankan di macOS / Linux
Prasyarat sama (Python 3.12+, Node.js 20+). Dari folder repo:
```bash
# Setup (sekali saja)
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env
.venv/bin/python -m app.demo          # isi data demo; --reset untuk mengulang dari nol
cd ../frontend && npm ci

# Nyalakan (dua terminal)
cd backend  && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev -- --port 5173
```
Lalu buka http://localhost:5173. Pada perintah di bagian lain README, ganti
`.venv\Scripts\` menjadi `.venv/bin/`.

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
| `python -m app.simulator attack <bruteforce\|beaconing\|ransomware> [--target HOST ...]` | Satu skenario, opsional ke host tertentu (ulangi `--target` untuk serentak) |
| `python -m app.simulator targets` | Daftar host target beserta kritikalitas |

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

## Batasan prototipe (apa adanya)
Agar klaim presentasi sesuai dengan yang benar-benar berjalan:

| Area | Kondisi di prototipe ini |
|---|---|
| Agen ELANG-2/3/6 | Default memakai **stub deterministik offline** (`stub-sovereign`, terlihat di panel hipotesis), bukan LLM. Jalur **Ollama loopback** sudah ada (`LLM_PROVIDER=ollama`) tetapi belum divalidasi dengan model nyata |
| ELANG-1 | IsolationForest (implementasi mandiri) dilatih ulang dari event baseline setiap deteksi. Data latih dipilih dari event berlabel `baseline`; untuk data asli, event latih perlu diberi label yang sama saat ingest |
| ELANG-4 | Mesin SOAR + Matriks Otonomi. Playbook dijalankan operator dari detail insiden (bukan otomatis saat alert muncul) |
| ELANG-5 (Deceiver), ELANG-7 (Trainer), YARA | **Belum dibangun** (roadmap F2/F3 di PRD) |
| Deteksi "Sigma" | Subset Sigma dalam JSON (selection + kesetaraan field), belum mengimpor berkas YAML Sigma. Brute force & ransomware memakai aturan **threshold** |
| Korelasi | Per host/aset. Serangan lintas host belum digabung menjadi satu kampanye |
| Adapter respons | Semua **mock**: aksi dan rollback hanya dicatat; status aset di inventaris tidak berubah |
| Timeout approval | Diproses lewat tombol **Proses timeout** / endpoint, belum ada penjadwal otomatis |
| Audit | Hash chain SHA-256 mendeteksi perubahan entri. Belum ada kunci rahasia/anchoring eksternal, jadi pihak yang bisa menulis seluruh database dapat menghitung ulang rantai |

## Atribusi & lisensi
Kode PN-X dirilis dengan lisensi [MIT](LICENSE). Komponen pihak ketiga tetap berlisensi
masing-masing:

| Komponen | Lisensi |
|---|---|
| FastAPI, SQLAlchemy, Alembic, Pydantic, pydantic-settings, PyJWT, pyotp, pytest | MIT |
| Uvicorn, HTTPX | BSD-3-Clause |
| bcrypt, python-multipart | Apache-2.0 |
| psycopg 3 (driver PostgreSQL, hanya jalur Docker) | LGPL-3.0 |
| Vue, Vue Router, Pinia, Vue I18n, Vite, @vitejs/plugin-vue, Tailwind CSS, PostCSS, Autoprefixer, vue-tsc | MIT |
| TypeScript | Apache-2.0 |
| Font IBM Plex Sans & IBM Plex Mono (via Fontsource) | SIL Open Font License 1.1 |

Data & referensi:
- **MITRE ATT&CK®**: ID & nama teknik/taktik. © The MITRE Corporation. This work is
  reproduced and distributed with the permission of The MITRE Corporation.
- **STIX™ 2.1** (OASIS Open): format impor IoC.
- **Isolation Forest**: algoritma dari Liu, Ting & Zhou (2008), diimplementasikan ulang
  tanpa pustaka ML.
- **Model AI**: tidak ada model AI pihak ketiga yang dibundel atau dipanggil secara default.
  Jika `LLM_PROVIDER=ollama` diaktifkan, [Ollama](https://ollama.com) (MIT) dan model
  pilihan (default konfigurasi `llama3.1:8b`, Llama 3.1 Community License) dipasang terpisah
  oleh pengguna dan tunduk pada lisensinya.
- Data demo sepenuhnya fiktif. Alamat IP memakai blok dokumentasi RFC 5737 dan domain
  `example.net` (RFC 2606).
