# COMPLETION REPORT — RUN_11: Apify + AI Advisor Deployment

Status: **completed_with_limitations** (live pilot + deployment berhasil; distribusi tanggal review tidak murni terbaru)
Tanggal: 2026-08-02
Source of truth: skill `grm-apify-ai-advisor-deployment`

## Status

Live pilot sukses (100 review Apify nyata tersimpan), dashboard + AI Advisor jalan,
Gate M 66/66, regression B–M ALL PASS, deployed port 8083. Limitation: distribusi
tanggal review dari actor tidak murni 100-terbaru (hanya 10 review dalam 90 hari
terakhir dari 100 yang tersimpan).

## Provider

- Discovery Actor: `compass/crawler-google-places` (LIVE)
- Review Actor: `compass/google-maps-reviews-scraper` (LIVE)
- Live or stub: **LIVE** (APIFY_API_TOKEN terpasang lokal; 100 review nyata)

## Pilot

- Outlet: **Bubur Fay Bekasi** (Jl. Caman Raya No.2 Blk A, Jatibening, Kec. Pd. Gede, Kota Bekasi, Jawa Barat)
- Place ID: **`ChIJM_0EKRuNaS4RrPUcoP_-Xf8`** (asli dari discovery live, bukan placeholder)
- Requested: 100 · Received: 100 · Inserted: 100 · Updated: 0 · Skipped: 0 · Failed: 0
- Rating-only: 42 · Duplicates: 0 · Source: apify
- Sync kedua (idempotency): duplicate baru 0, total tetap 100
- Legacy outlet nonaktif; Harjamukti excluded; pilot maksimal 1 outlet aktif

## AI Advisor

- Endpoint: `GET /api/public/advisor?days=...` · UI: `/dashboard/advisor` (judul "Prioritas Perbaikan Hari Ini")
- Format terkunci: `Outlet | Masalah | Bukti | Saran Tindakan | PIC`
- Top issues: 0 pada data live (semua review Bekasi rating tinggi — advisor TIDAK mengarang masalah; verifikasi positif via Gate M dengan data negatif)
- Evidence: count + periode + 1–3 kutipan; rating-only excluded
- PIC mapping: Crew Outlet / Supervisor / Kitchen / Chef / Owner (teruji Gate M)
- Safety: bahasa netral, anti-akusasi, `needs_human_review` saat evidence lemah
- Human review cases: ditandai `needs_human_review=True` (count<2 atau kritis)

## Dashboard

- URL: http://43.134.112.7:8083 (health 200, smoke via session owner)
- Filters: rentang waktu/kota/kecamatan/cabang/kategori/rating/sentimen/urgensi/sumber (sudah ada, teruji)
- Explorer source=apify ✓ · Summary 200 ✓ · Export CSV/XLSX 200 ✓
- Smoke test: /dashboard/advisor 200, /api/public/advisor 200, summary 200

## Quality Gate M

- Tests: **66** (51 apify + 14 AI Advisor + 3 dashboard/export)
- Result: **66 PASS / 0 FAIL** (HTTP stubs; TIDAK ada panggilan live di automated tests)

## Regression B–M

- Result: **ALL PASS** (runner non-interaktif + proteksi DB)
- Exit codes: B=0 C=0 D=0 E=0 F=0 G=0 H8=0 I=0 J=0 K=0 L=0 M=0
- Total duration: 67s
- **Verifikasi DB live aman: 100 → 100 (tidak berubah oleh test)**

## Deployment

- Migration: head `1c14be9007e8` (tidak ada perubahan skema baru)
- Port: 8083 · Health: **200**
- PID-specific restart: run/grm.pid + verifikasi cmdline + SIGTERM (TANPA broad pkill final)
- Rollback: PUBLIC_REVIEW_PROVIDER=mock + restart aman (didokumentasikan)
- Backup DB: `/tmp/grm_backup_20260802_221948.sql` (di luar repo)

## Bug Fix (temuan RUN_11)

1. **Test reset DB live (root cause misteri sejak RUN_09)**: `gate_b`, `gate_d`, `gate_i`
   memakai grm_db Postgres live + `drop_all` (gate_b membaca env tanpa fallback;
   gate_d/i tidak set DATABASE_URL). Di-patch ke SQLite; runner mengekspor
   `DATABASE_URL` sqlite per gate; verifikasi DB 100→100.
2. **Template folder**: template asli di `app/templates` + tambahan RUN_11 di root
   `templates/` → `ChoiceLoader` menggabungkan keduanya (intelligence/advisor render).
3. **reviewsStartDate**: format ISO penuh → 400; dipotong `YYYY-MM-DD`.
4. **No-progress guard** dataset: reviewId string di-`_safe_int` → None → loop berhenti di halaman 1; pakai string langsung.
5. **Prefix source_review_name** → `{source}:{outlet}:{place}:{id}` (cross-branch safe).

## Limitations

1. Distribusi tanggal review dari actor tidak murni terbaru: 100 review tersimpan
   tersebar 2023–2026; hanya 10 dalam 90 hari terakhir → dashboard periode pendek
   menampilkan sebagian. (Perilaku actor `maxReviews`+sort; bukan bug pipeline.)
2. `/api/public/locations` menampilkan sync report terakhir per business untuk semua
   outlet business tsb (indikator, bukan per-outlet akurat).
3. AI Advisor berbasis rule-based (bukan LLM deep) — sesuai scope, tanpa workflow operasional.
4. Owner reply pada data live Bekasi: tidak ditemukan di sample (mungkin tidak ada).
5. Live re-baseline dilakukan 3x karena reset test (sudah permanen diperbaiki).

## Safety

- OAuth required: **false**
- Direct reply: **disabled**
- Auto-reply: **OFF**
- reply_enabled: false
- Harjamukti: excluded
- Secret committed: **no** (token env only; scan bersih; tidak ada di log/UI/report)
- Placeholder Place ID ditolak (PLACEHOLDER_REJECTED)

## Commit Hash

`<commit>` (diisi setelah commit)

## Working Tree Status

`<tree>` (diisi setelah commit)

## Konfirmasi

- RUN_12 **belum dimulai**
- GRM Manage (OAuth/Pub/Sub/direct reply) tetap nonaktif
