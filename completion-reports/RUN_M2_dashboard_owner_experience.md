# RUN_M2 — DASHBOARD SIMPLIFICATION & OWNER EXPERIENCE

Status: **selesai & deployed**
Tanggal: 2026-08-02
Base: RUN_M1 (1e70e76) — self-service onboarding

## Tujuan

Dashboard berubah dari teknis → owner restoran: dalam 15 detik owner tahu
kondisi outlet, masalah terbesar, siapa PIC, dan tindakan pertama.

## Yang Diubah (UI/UX/hierarchy ONLY)

- **DB / API / AI Advisor logic / Apify / discovery / sync / analytics / normalization: TIDAK diubah.**
- `templates/base.html` (+ sinkron `app/templates/base.html`): menu utama
  **Dashboard · Outlet · AI Advisor · Reviews · Settings**; menu teknis
  (Discovery, Kandidat, Audit, Intelijen, Review Sources, Sync History, Import,
  Pub/Sub, Onboarding) dipindah ke **⚙️ Developer Tools — hanya tampil untuk
  role `superadmin`**.
- `dashboard/index.html` (owner view):
  - Header outlet: nama, rating, jumlah review, **review baru minggu ini**,
    tanggal sync terakhir, tombol **Sync Sekarang** + **+ Tambah Outlet**
  - Summary cards: Review (30 hari), Positif, Netral, Negatif
  - **Ringkasan Hari Ini**: N masalah · N apresiasi · prioritas utama
  - **AI Advisor card** (format terkunci: Outlet/Masalah/Bukti/Saran/PIC), Top 3 terurut
  - Daftar outlet ringkas (multi-outlet)
- `dashboard/outlets.html`: nama, rating, review, sync terakhir + tombol
  **Sinkronisasi** (pakai progress polling) + **Dashboard**
- `dashboard/reviews.html`: tab **Positif / Netral / Negatif** + filter 30 hari
  (pakai API explorer existing)
- `dashboard/settings.html`: Profile, Integrasi, Logout
- Design: bersih, minimalis, mobile-friendly (meta viewport + grid/flex responsive)

## Data Live (smoke)

`/dashboard/` render dengan Bubur Fay Bekasi: ⭐4.5, 438 review, sync terakhir
2026-08-03, Ringkasan Hari Ini + Prioritas Perbaikan tampil. Semua halaman
200: `/dashboard/`, `/dashboard/outlets`, `/dashboard/reviews`,
`/dashboard/settings`, `/dashboard/advisor`.

## Quality Gate O

- File: `tests/gate_o.py` · Tests: **11 PASS / 0 FAIL**
- Cakupan: layout render (nav + konten owner), mobile render (viewport), menu
  role (superadmin lihat Developer Tools; viewer tidak), advisor card, summary
  card, dashboard performance (<3s), outlets/reviews/settings pages,
  advisor page contract tidak berubah

## Regression B–O

- Result: **ALL PASS** (80s, runner non-interaktif + proteksi DB)
- Exit codes: B=0 C=0 D=0 E=0 F=0 G=0 H8=0 I=0 J=0 K=0 L=0 M=0 N=0 O=0
- **DB live aman: 100 → 100**

## Deployment

- Restart PID-specific (run/grm.pid) · health 200 · semua halaman owner 200

## Screenshot

- Desktop: `/home/ubuntu/.hermes/cache/screenshots/browser_screenshot_0d4627282dca4201a8d35eb2320b5b39.png`
- Mobile: tool browser tidak mendukung viewport resize; mobile-friendly
  diverifikasi via Gate O `test_mobile_render` (meta viewport + responsive grid/flex).

## Commit

- `f854266` feat: simplify dashboard for owner experience (RUN_M2) · working tree: clean
