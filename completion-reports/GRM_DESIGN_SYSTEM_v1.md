# GRM DESIGN SYSTEM — v1.0 (Identitas Visual GRM)

Status: **selesai & deployed**
Tanggal: 2026-08-03
Skill: `grm-owner-dashboard-design-system` (ACTIVE)

## Tujuan

Redesign UI GRM → kualitas SaaS kelas dunia dengan **identitas visual GRM sendiri** — bukan clone Google Business Profile (tanpa logo/ikon/warna/font/nama menu Google).

## Design System

- **Tokens** (`app/static/css/design.css`): Primary Orange `#ff7a00` · Accent Blue · Success Green · Warning Amber · Error Red · Neutral Gray · Background Off White `#faf9f7`; radius (8/12/16px), shadow halus, spacing scale, tipografi modern sans-serif (Page/Section/Card/Body/Caption).
- **Komponen**: buttons (primary/secondary/success/danger), inputs (label atas, focus state), cards, tables (sticky header, hover), badges, empty/loading/error state, alert.
- **Layout**: **Sidebar** (Logo G → Menu → Developer Tools → User) + **Header** (App → +Outlet → Brand → Logout) + content area; responsive (mobile: sidebar jadi topbar horizontal, KPI 2 kolom).

## Dashboard (hierarki baru — AI Advisor fokus)

1. Header Outlet (nama, rating, review, baru minggu ini, sync terakhir + Sync/Tambah)
2. 🚨 **Prioritas Hari Ini** (hero: masalah + bukti + kutipan + PIC + tindakan pertama)
3. **AI Advisor — Prioritas Perbaikan** (fokus utama, border top orange): semua issue lengkap Outlet·Masalah·Bukti·Saran·PIC·Status·Confidence·Priority
4. KPI (Rating rata-rata, Review, Positif, Negatif)
5. Tren Rating + Distribusi Rating
6. Sentimen dari Waktu ke Waktu + Aspek Teratas
7. Performa Outlet (Terbaik/Perlu Perhatian, keluhan/pujian)
8. Rekap Rating Terendah & Tertinggi
9. Review Terbaru

## Identity (bukan GMB)

- Brand GRM (logo mark G orange), nama menu sendiri, warna orange khas GRM
- Tidak ada teks/aset/menu Google Business Profile (Gate U teruji)

## Quality Gate U

- Tests: **8 PASS / 0 FAIL** — layout sidebar+header, design.css loaded, hierarki (hero→advisor→kpi), AI Advisor fokus, identity (bukan clone GMB), responsive, 5 halaman render

## Regression B–U

- Result: **ALL PASS** (94s) · Gate P disesuaikan ke hierarki baru (advisor di atas)
- DB live aman 438→438

## Deployment

- Restart PID-specific · health 200 · `/static/css/design.css` 200 · dashboard render live (sidebar+hero+advisor)

## Screenshot

- Desktop: `/home/ubuntu/.hermes/cache/screenshots/browser_screenshot_a1dfb507d1244e5c93b5f54a3b737c51.png`
- Mobile: responsive diverifikasi (media query 860px, KPI 2 kolom)

## Commit

- `<commit>` (diisi setelah commit) · working tree: `<tree>`
