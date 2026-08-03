# RUN_M3 — PILOT CUSTOMER READINESS (GRM v0.9)

Status: **selesai & deployed — siap pilot customer**
Tanggal: 2026-08-03
Base: M2.1 (d3e699e) — dashboard FINAL

## Tujuan

GRM siap dipakai customer pertama — production readiness, TANPA fitur baru
(tidak ada AI/dashboard/analytics/menu/database baru).

## Task yang Dikerjakan

1. **Landing page** (`/`): Apa itu GRM, cara kerja, 3 langkah, button Login.
   Redirect ke `/dashboard/` jika sudah login.
2. **Onboarding guide** (`/guide`): 4 langkah — Tambah Outlet → Sinkronisasi →
   Buka AI Advisor → Lakukan Tindakan.
3. **Help/FAQ** (`/help`): 5 FAQ sederhana (durasi sync, review belum muncul,
   Incremental Sync, Prioritas Hari Ini, arti PIC).
4. **Copywriting**: audit — tidak ada istilah teknis (API/OAuth/Postman/
   endpoint/JSON/scraping/.env) di halaman public (Gate Q teruji).
5. **Empty states**: "Belum ada outlet aktif", "Belum ada review", "Tidak ada
   masalah", "Sync terakhir: belum".
6. **Loading states**: "Memuat…", "Mencari…", "Menunggu…", "Sinkronisasi…".
7. **Error states ramah**: tanpa stack trace (Gate N & Q teruji).
8. **Polishing**: icon/spacing/typography rapi (CSS konsisten).
9. **About** (`/about`): versi 0.9.0, build 0.9.0, deployment date 2026-08-03,
   provider, mode.

## Quality Gate Q

- File: `tests/gate_q.py` · Tests: **11 PASS / 0 FAIL**
- Cakupan: landing render + redirect setelah login, guide, help, about,
  copywriting tanpa istilah teknis, empty states (outlet/review/dashboard),
  loading state, error tanpa stack trace

## Regression B–Q

- Result: **ALL PASS** (83s, runner non-interaktif + proteksi DB)
- Exit codes: B=0 C=0 D=0 E=0 F=0 G=0 H8=0 I=0 J=0 K=0 L=0 M=0 N=0 O=0 P=0 Q=0
- **DB live aman: 100 → 100**

## Deployment

- Restart PID-specific (run/grm.pid) · health 200
- Halaman public: `/` 200, `/guide` 200, `/help` 200, `/about` 200

## Screenshot

- Landing: `/home/ubuntu/.hermes/cache/screenshots/browser_screenshot_340e45007e4f4c5f9411bdd936178e6b.png`

## Tag

- `v0.9-pilot-release` (GRM v0.9 Pilot Release)

## Commit

- `247aafe` feat: pilot customer readiness pages (RUN_M3) · working tree: clean
