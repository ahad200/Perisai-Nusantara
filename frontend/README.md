# PN-X Frontend (M2)

Konsol SOC — Vue 3 + Vite + TypeScript + Pinia + vue-router + vue-i18n + Tailwind.
Mengikuti **PRD Lampiran C** (tema grafit gelap, IBM Plex, warna severity hanya untuk
severity, tanpa pola anti-slop C.5).

## Jalankan (dev)

Backend M1 harus hidup lebih dulu (mis. `docker compose up` di root → API :8000).

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxy /api -> :8000)
```

Login dengan user demo (jalankan seed backend): username = nama role, password `ChangeMe123!`.
Contoh: `platform_admin`, `auditor`, `analyst_t1`.

## Skrip
| Perintah | Fungsi |
|---|---|
| `npm run dev` | Dev server + proxy API |
| `npm run build` | Typecheck (vue-tsc) + build produksi |
| `npm run preview` | Pratinjau hasil build |
| `npm run typecheck` | Pengecekan tipe saja |

## Yang sudah ada (M2)
- **Design tokens** (CSS variables) + Tailwind, tema gelap/terang, IBM Plex Sans/Mono.
- **Komponen dasar**: Button, SeverityBadge, StatusBadge, Panel, TextInput, Modal,
  DataTable, SkeletonRow, EmptyState, AppClock (WIB/UTC).
- **Halaman `/dev/components`** — galeri semua komponen + state (C.6).
- **Layout aplikasi**: sidebar (menu menyesuaikan role), header (jam WIB/UTC, toggle
  tema & bahasa, sign out).
- **Login + MFA (TOTP)** dua langkah, JWT disimpan di localStorage.
- **i18n** id/en.
- Halaman contoh terhubung API nyata: **Pengguna** (`GET /users`) & **Audit**
  (`GET /audit` + tombol verifikasi hash chain), lengkap dengan state loading/empty/error.

## Struktur
```
src/
  components/ui/       komponen dasar
  components/layout/   sidebar, header, layout
  views/               halaman (login, situasi, pengguna, audit, /dev/components)
  stores/auth.ts       Pinia: login, MFA, sesi
  lib/                 api client, rbac mirror, waktu, tema
  i18n/                id/en
  router/              rute + guard auth & permission
  style.css            design tokens + Tailwind
```
