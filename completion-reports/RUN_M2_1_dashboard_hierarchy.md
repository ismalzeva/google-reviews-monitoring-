# RUN_M2.1 — DASHBOARD INFORMATION HIERARCHY POLISH

Status: **selesai & deployed**
Tanggal: 2026-08-02
Base: RUN_M2 (f854266) — dashboard owner

## Tujuan

Owner tahu tindakan pertama dalam ≤10 detik — hanya mengubah urutan informasi.
Tidak ada perubahan logic/DB/AI/provider/analytics/discovery.

## Urutan Dashboard (final untuk pilot customer)

1. **Header Outlet** — nama, rating, review, baru minggu ini, sync terakhir + Sync Sekarang / Tambah Outlet
2. **🚨 Prioritas Hari Ini** — section terbesar setelah header (hero):
   - Ada masalah → kartu amber: Masalah + Bukti + kutipan + PIC + Tindakan pertama (format AI Advisor terkunci)
   - Tidak ada masalah → **kartu hijau**: "✅ Tidak ada masalah prioritas hari ini."
3. **Ringkasan Hari Ini** — lebih menonjol (border kiri brand, angka besar): N masalah · N apresiasi · prioritas utama
4. **Prioritas Perbaikan (Top 3)** — format terkunci Outlet/Masalah/Bukti/Saran/PIC
5. **Review Summary** — dipindah ke bawah (Review 30 hari, Positif, Netral, Negatif)
6. **Daftar Outlet**

## Quality Gate P

- File: `tests/gate_p.py` · Tests: **7 PASS / 0 FAIL**
- Cakupan: urutan section (header→hero→ringkasan→top3→review-summary→outlet), hero section, kartu hijau saat tanpa masalah, review summary di bawah prioritas, contract advisor tidak berubah (≤3 issues), performance (<3s), ringkasan menonjol

## Regression B–P

- Result: **ALL PASS** (80s, runner non-interaktif + proteksi DB)
- Exit codes: B=0 C=0 D=0 E=0 F=0 G=0 H8=0 I=0 J=0 K=0 L=0 M=0 N=0 O=0 P=0
- **DB live aman: 100 → 100**

## Deployment

- Restart PID-specific (run/grm.pid) · health 200 · urutan 1–5 terverifikasi render live
- Data live: hero menampilkan kartu hijau (review Bekasi positif)

## Screenshot

- Desktop: `/home/ubuntu/.hermes/cache/screenshots/browser_screenshot_e09b4072f3ad49db970a86db0531aceb.png`
- Mobile: tool browser tidak mendukung viewport resize; mobile-friendly diverifikasi via Gate O `test_mobile_render` (meta viewport + responsive grid/flex).

## Commit

- `d3e699e` feat: polish dashboard information hierarchy (M2.1) · working tree: clean
