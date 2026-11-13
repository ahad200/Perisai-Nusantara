# PN-X Frontend

Konsol SOC: Vue 3 + Vite + TypeScript + Pinia + vue-router + vue-i18n + Tailwind.
Mengikuti **PRD Lampiran C**: tema grafit gelap, IBM Plex Sans/Mono, warna severity hanya
untuk severity, tanpa pola anti-slop (C.5).

> **Juri/penguji di Windows:** cukup ikuti [README utama](../README.md#menjalankan-di-windows-untuk-juri--penguji)
> (`setup-windows.bat` lalu `start-windows.bat`). Bagian di bawah untuk pengembang.

## Jalankan (dev)
Backend harus hidup lebih dulu di `:8000` (lihat README utama).

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173  (proxy /api -> :8000)
npm run dev -- --host   # juga bisa diakses dari perangkat lain di LAN
```

Login dengan akun demo (diisi oleh `python -m app.demo` di backend). Password semua akun
`ChangeMe123!`:

| Username | Role |
|---|---|
| `operator` | Analis SOC: triase, insiden, eksekusi playbook, simulator, agen AI |
| `commander` | Supervisi: approval SOAR, laporan, pengguna, audit |
| `intel` | Threat intel + validasi atribusi |
| `auditor` | Read-only: audit + verifikasi hash chain |

## Skrip
| Perintah | Fungsi |
|---|---|
| `npm run dev` | Dev server + proxy API |
| `npm run build` | Typecheck (vue-tsc) + build produksi |
| `npm run preview` | Pratinjau hasil build |
| `npm run typecheck` | Pengecekan tipe saja |

## Halaman
Situasi (COP + peta segmen per host), Antrian Alert (shortcut `j`/`k`/`a`/`e`/`x`), Insiden
(detail + alur OODA + Analisis AI), SOAR (approval, run, rollback, break-glass), Aset, Event
(+ pemicu simulator), Threat Intel, Coverage ATT&CK, Eksekutif, Laporan, Pengguna, Audit, dan
`/dev/components` (galeri komponen, hanya mode dev).

## Struktur
```
src/
  components/ui/       komponen dasar (badge, panel, tabel, modal, OodaFlow, SegmentMap, BrandMark, ...)
  components/layout/   sidebar berkelompok, command bar (postur + antrian), layout
  views/               halaman
  stores/auth.ts       Pinia: login, MFA, sesi
  lib/                 api client, rbac mirror, waktu, tema, opsStatus, tipe API
  i18n/                id/en
  router/              rute + guard auth & permission
  style.css            design tokens + Tailwind
public/brand/          lambang (varian gelap/terang) + favicon
```
