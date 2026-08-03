# GRM DASHBOARD + AI ADVISOR UX REDESIGN (v0.9.1)

Status: **selesai & deployed**
Tanggal: 2026-08-03
Skill: `grm-dashboard-ai-advisor-ux-redesign` (presentation layer only — BACKEND TIDAK DIUBAH)

## Tujuan

Dashboard kualitas SaaS modern: KPI Cards, Tren Rating, Distribusi Rating,
Review Terbaru (data asli), Top Aspek, Sentiment Over Time, Performa Outlet,
Alert & Notification. AI Advisor: kontrak dipertahankan + Evidence/Confidence/
Priority/Status.

## Yang Diubah (presentation layer)

- `app/routes/dashboard.py` — route index mengumpulkan data widget via service
  existing (executive_summary, category_breakdown, branch_breakdown,
  period_analytics, review_explorer, advisor) + distribusi rating dari DB
  (query internal, bukan API baru). **Tidak ada endpoint API baru.**
- `templates/dashboard/index.html` (+ sinkron root) — layout 8 widget:
  1. Alert & Notification (merah info/urgent, hijau jika tanpa masalah)
  2. KPI Cards (Rating rata-rata, Review, Positif, Negatif)
  3. Tren Rating (bar chart, data nyata)
  4. Distribusi Rating (5★–1★ horizontal bars)
  5. Sentimen dari Waktu ke Waktu (stacked bars, 7 hari)
  6. Aspek Teratas (top 6 kategori, bars)
  7. Performa Outlet (per outlet: rating, review, keluhan utama)
  8. Review Terbaru (5 item data asli: bintang, teks, reviewer, tanggal, cabang)
- AI Advisor card diperkaya: **Priority badge · Outlet · Confidence · Status ·
  Bukti (count+periode+kutipan) · Saran tindakan (ol) · PIC · needs_human_review**
- Tidak ada data palsu: widget kosong → placeholder ("Belum ada…" / "—").

## Tidak Diubah

Database · API endpoints · AI Advisor engine · Apify integration · Review
pipeline · Authentication.

## Quality Gate R

- File: `tests/gate_r.py` · Tests: **18 PASS / 0 FAIL**
- Cakupan: 8 widget render, advisor contract + evidence/confidence/priority/
  status, quotes dari data asli, mobile responsive, no fabricated data,
  performance (<3s), backend API unchanged
- Gate O & P diperbarui ke struktur final (bukan melemahkan — menyesuaikan
  layout redesign yang disetujui): urutan KPI → Tren → Performa → Advisor →
  Review Terbaru.

## Regression B–R

- Result: **ALL PASS** (87s, runner non-interaktif + proteksi DB)
- Exit codes: B=0 C=0 D=0 E=0 F=0 G=0 H8=0 I=0 J=0 K=0 L=0 M=0 N=0 O=0 P=0 Q=0 R=0
- **DB live aman: 100 → 100**

## Deployment

- Restart PID-specific (run/grm.pid) · health 200 · dashboard 200 (widget live render)
- API summary 200 (backend unchanged)

## Screenshot

- Desktop: `/home/ubuntu/.hermes/cache/screenshots/browser_screenshot_8756084a70c148e29ca6ed6525f42448.png`
- Mobile: tool browser tidak mendukung viewport resize; responsive grid/flex
  diverifikasi via Gate R/O (`width=device-width`, grid-template-columns).

## Commit

- `<commit>` (diisi setelah commit) · working tree: `<tree>`
