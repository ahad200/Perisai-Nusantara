# Migrasi PN-X ke Data Asli — Runbook Bertahap

> Status dokumen: panduan teknis. PN-X adalah **prototipe defensif berdata simulasi**
> (PRD §4.2). Dokumen ini merinci cara menyambungkannya ke data & perangkat asli
> **tanpa melanggar pagar pengaman** yang sudah dirancang: tetap air-gapped (§A.5 no.5),
> audit immutable (§A.5 no.3), agen LLM tak pernah memanggil adapter (§A.5 no.1).
>
> **Aturan emas:** aktifkan **data masuk (read-only) dulu**, baru **aksi keluar** —
> dan aksi keluar hanya dengan otorisasi resmi + pengujian lab. Jangan lompat.

---

## Peta seam (titik sambung)

| Lapisan | File kunci | Status prototipe | Jadi asli dengan |
|---|---|---|---|
| Ingest event | `app/ingest/service.py` → `ingest_events()` | diisi `app/simulator/` | ganti sumber jadi collector asli |
| Normalisasi | `app/ingest/normalize.py` → `_NORMALIZERS` | 4 sumber contoh | tambah/sesuaikan fungsi per format log |
| Inventaris aset | model `Asset` | `simulator seed-assets` | seed aset nyata (CMDB) |
| Deteksi/korelasi/intel/dashboard/agen | — | **siap** | otomatis ikut data asli |
| Aksi respons | `app/soar/adapters.py` → `MockAdapter` | mock (hanya mencatat) | implementasi adapter nyata (risiko tinggi) |
| Enrichment | tabel mirror lokal | data contoh | isi mirror dari feed satu-arah |
| LLM | `app/agents/llm.py`, config `llm_provider` | `stub` offline | `ollama` loopback-only |
| Auth/secret | `app/core/config.py` | mode dev | MFA on, ganti `SECRET_KEY`, HTTPS |

---

## Fase 0 — Pengerasan platform (prasyarat, sebelum data apa pun)

Tanpa ini, "produksi" tidak sah berapa pun bagusnya datanya.

1. **Secret & environment.** Set env:
   - `ENVIRONMENT=prod` (mengaktifkan guard: app menolak start bila `SECRET_KEY` masih default — lihat `config.get_settings()`).
   - `SECRET_KEY=<64+ byte acak dari secret manager>`.
   - `DATABASE_URL=postgresql+psycopg://<user>:<pass>@<host>:5432/pnx`.
2. **MFA.** TOTP sudah ada (`app/core/security.py`). Aktifkan untuk semua akun; cabut akun demo seed; ganti password default `ChangeMe123!`.
3. **Transport.** Taruh API di belakang reverse-proxy TLS (nginx/caddy) internal. Tidak ada port terbuka ke internet.
4. **Egress lockdown.** Pastikan host backend tak punya rute keluar (firewall/namespace). LLM wajib loopback (`llm_base_url=http://127.0.0.1:11434`). Ini menegakkan §A.5 no.5 di lapisan jaringan, bukan sekadar kode.
5. **Backup & retensi DB** (termasuk tabel audit — append-only, jangan pernah di-prune lewat DELETE).

---

## Fase 1 — Data masuk (SOC read-only) — AMAN, prioritas pertama

Semua event masuk lewat **satu pintu**:

```python
# app/ingest/service.py
ingest_events(db, records, scenario=None, action="event.ingest", actor_type="system", actor_id="<collector>")
# records: Iterable[tuple[source_type: str, raw: dict, ts: datetime]]
```

Sekarang pintu ini diisi `app/simulator/`. Untuk data asli, **ganti sumbernya** — sisanya (deteksi, korelasi, dashboard) tak berubah.

### 1a. Sesuaikan normalisasi

`app/ingest/normalize.py` memetakan `raw` mentah → `NormalizedEvent` seragam (ECS/OCSF-inspired). Menambah sumber = menambah satu fungsi murni ke `_NORMALIZERS`. Contoh sumber Windows Security log:

```python
def _norm_winsec(ts: datetime, raw: dict[str, Any]) -> NormalizedEvent:
    eid = str(raw.get("EventID"))
    outcome = "failure" if eid == "4625" else "success"   # 4625=gagal, 4624=sukses
    return NormalizedEvent(
        ts=ts, source_type="winsec", category="authentication",
        action="login_failed" if outcome == "failure" else "login_success",
        outcome=outcome, host=_s(raw, "Computer"), user=_s(raw, "TargetUserName"),
        src_ip=_s(raw, "IpAddress"), raw=raw,
        message=f'{raw.get("TargetUserName","?")}@{raw.get("Computer","?")} EID {eid}',
    )

_NORMALIZERS["winsec"] = _norm_winsec
```

> Sumber tak dikenal **tidak dibuang** — dinormalisasi sebagai `category="other"`
> (fail-open untuk visibilitas, bukan untuk keputusan). Jadi data baru tetap terlihat
> walau normalizer-nya belum sempurna.

### 1b. Tulis collector (pengganti simulator)

Collector membaca log nyata dan memanggil `ingest_events()` dengan bentuk record yang sama persis seperti simulator:

```python
# app/ingest/collectors/syslog_tail.py  (contoh; baru)
from datetime import datetime, timezone
from app.ingest import ingest_events

def collect_batch(db, lines: list[str]) -> int:
    records = []
    for line in lines:
        raw = parse_line(line)                 # format log Anda -> dict
        ts = datetime.fromisoformat(raw["ts"]).astimezone(timezone.utc)
        records.append((raw["source_type"], raw, ts))   # (source_type, raw, ts)
    return ingest_events(db, records, scenario=None, action="event.ingest",
                         actor_type="system", actor_id="syslog-collector")
```

Jalankan sebagai service terjadwal (systemd timer / cron / worker) yang menarik batch
secara berkala. **Satu batch = satu AuditEntry**, jadi ribuan event tak membanjiri audit.

### 1c. Inventaris aset asli

Ganti `python -m app.simulator seed-assets` dengan impor aset nyata (CSV CMDB → model `Asset`), lengkap `hostname`, `ip`, `segment`, `criticality` (K1/K2/K3). Penautan event→aset lewat pencocokan `hostname` di `ingest_events`. **Aset tanpa kritikalitas → diperlakukan K1** (fail-safe, §A.5 no.6) — tetapkan kritikalitas eksplisit agar Matriks Otonomi akurat.

### 1d. Matikan simulator di prod

Endpoint `POST /dev/simulate` sudah non-produksi. Pastikan rute `/dev/*` & tombol "Jalankan skenario" tidak aktif saat `ENVIRONMENT=prod`.

**Setelah Fase 1:** deteksi (Sigma/threshold/IoC/ELANG-1), korelasi insiden, intel, dashboard
Situasi/Eksekutif, Coverage ATT&CK, dan agen LLM **jalan apa adanya di data asli** —
semuanya read-only. Ini sudah SOC yang berguna tanpa satu pun aksi berbahaya.

---

## Fase 2 — Intel & enrichment asli (masih read-only)

- **IoC:** impor STIX 2.1 asli (TAXII pull dilakukan **di luar** backend lalu file dibawa masuk — backend tak egress). Siklus hidup (kedaluwarsa/whitelist/FP) sudah ada.
- **Enrichment (WHOIS/GeoIP/reputasi):** isi `EnrichmentRecord` dari dump/mirror lokal yang di-refresh satu-arah. **Jangan** mengubah enrichment jadi panggilan live (melanggar §A.5 no.5).

---

## Fase 3 — Sovereign LLM asli (opsional, tetap air-gap)

Set `llm_provider=ollama`, jalankan Ollama di host yang sama, `llm_base_url` wajib loopback
(`127.0.0.1`) — egress guard di `app/agents/llm.py` menolak non-loopback (FR-404). Kontrol §11
tetap aktif: data lapangan dibungkus tak-tepercaya + deteksi injection, output divalidasi
Pydantic, klaim wajib grounded (rujuk ID), **agen tak pernah memanggil adapter**, severity
final tetap dari rule engine. Output selalu **draf** → tinjauan manusia.

---

## Fase 4 — Aksi respons nyata ⚠️ RISIKO TINGGI, bertahap, perlu otorisasi

Ini satu-satunya lapisan yang benar-benar menyentuh perangkat produksi. **Jangan** aktifkan
tanpa otorisasi Mabes TNI + uji di lab terisolasi.

### 4a. Implementasi adapter nyata

Lengkapi antarmuka standar (FR-305) di samping `MockAdapter`:

```python
# app/soar/adapters.py
class EdrAdapter:
    name = "edr"
    def execute(self, action: str, params: dict) -> dict:
        if action == "isolate_host":
            return self._client.isolate(params["host"])   # panggil API EDR nyata
        ...
    def rollback(self, action: str, params: dict, prior: dict) -> dict:
        if action == "isolate_host":
            return self._client.unisolate(params["host"])
        ...
```

Pertahankan `ACTION_CATALOG` (sifat `disruptive`/`reversible`) — Matriks Otonomi
bergantung padanya.

### 4b. Urutan aktivasi (jangan dibalik)

1. **Semua dry-run** (FR-306) — lihat apa yang *akan* terjadi, nol efek.
2. **Aksi non-disruptif reversibel** dulu: `block_ip`, `add_watchlist`, `raise_logging`, `collect_forensics`.
3. **Aksi disruptif** terakhir: `isolate_host`, `disable_account`, `revoke_token` — mulai hanya untuk K3/K2, severity rendah, dengan **approval Commander wajib**.
4. Naikkan otonomi **lewat konfigurasi** `app/soar/autonomy_matrix.json` (§A.5 no.2 — bukan hardcode), per kombinasi severity × kritikalitas, satu langkah setiap kali setelah terbukti aman.

### 4c. Pagar yang sudah ada — pakai, jangan lewati

- **Matriks Otonomi (§7):** keputusan auto vs approval = severity × kritikalitas; K1 tanpa auto; High×K2 timeout→AUTO terkonsolidasi ke Commander.
- **Break-glass (§7 no.3):** jalur darurat beralasan + kedaluwarsa, tercatat audit.
- **Rollback (FR-304)** untuk tiap aksi reversibel.
- **Audit:** tiap eksekusi/approval menulis AuditEntry (rantai hash, immutable).

---

## Checklist Go / No-Go

- [ ] `ENVIRONMENT=prod`, `SECRET_KEY` kuat, Postgres, backup aktif
- [ ] MFA wajib; akun & password demo dicabut
- [ ] Reverse-proxy TLS internal; tanpa egress; LLM loopback-only
- [ ] Collector ingest jalan; normalizer per sumber diverifikasi; `/dev/*` mati
- [ ] Inventaris aset asli + kritikalitas eksplisit (hindari fail-safe K1 masal)
- [ ] Dashboard/deteksi/korelasi diverifikasi benar di data asli (periode bayangan)
- [ ] **(hanya jika diizinkan)** adapter respons: dry-run → non-disruptif → disruptif, per konfigurasi otonomi
- [ ] Verifikasi rantai audit (`/audit/verify`) hijau

---

### Prinsip yang tak boleh ditawar

1. Tetap **air-gapped** — tak ada egress dari backend (§A.5 no.5).
2. Audit **append-only** — tak ada role yang mengubah/menghapus (§A.5 no.3).
3. Agen LLM **tak pernah** memanggil adapter — hanya `app/soar/` (§A.5 no.1).
4. **Murni defensif** — tak ada aksi ofensif/hack-back (PRD §4.2), berapa pun "asli"-nya data.
