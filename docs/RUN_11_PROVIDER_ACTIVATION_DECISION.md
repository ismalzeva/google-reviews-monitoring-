# RUN_11 — PROVIDER ACTIVATION DECISION

Status: **BLOCKED** (keputusan dibuat; live belum)
Tanggal: 2026-08-02
Konteks: RUN_11 tetap BLOCKED karena credential belum tersedia. Dokumen ini
menentukan jalur aktivasi GRM Monitor non-login tercepat. **Tidak ada provider
baru yang diimplementasikan berdasarkan dokumen ini.**

## Konteks

- Arsitektur GRM Monitor non-login selesai (RUN_09–RUN_10): discovery → sync → analytics
- `PublicReviewSourceAdapter` interface siap; `OutscraperPublicReviewAdapter` sudah
  diimplementasikan & diuji (Gate K 32/32, Gate L 23/23)
- Satu-satunya blocker live: `OUTSCRAPER_API_KEY` belum tersedia
- OAuth tidak diperlukan; direct reply disabled; auto-reply OFF; Harjamukti excluded

## Perbandingan Provider

| Dimensi | Outscraper | Apify (Google Maps Reviews Scraper) | Internal Playwright/Selenium |
|---|---|---|---|
| Biaya awal | ~$0 (pay-as-you-go; free trial kecil) | ~$0 (Apify free tier ±5 USD kredit/bulan) | ~$0 (VPS + CloakBrowser sudah ada) |
| Biaya per 100 review | ±$0.50–0.70 | ±$0.10–0.30 | $0 (waktu dev) |
| Biaya per 1.000 review | ±$5–7 | ±$0.60–2.50 | $0 (tapi maintenance tinggi) |
| API key | Ya, `sk-...` (instant dari dashboard) | Ya, Apify API token `apify_...` (instant) | Tidak |
| Kemudahan setup | **Sangat mudah** — HTTP API; adapter SUDAH jadi | Sedang — buat actor task + RunActor API + polling dataset | Kompleks — stealth, fingerprint, parsing DOM |
| Pagination | Offset-based (didukung, teruji) | Actor internal (output array; dataset) | Manual scroll/infinite — fragile |
| Stabilitas | Tinggi (SaaS, SLA) | Tinggi (managed) | Rendah (Google sering ubah DOM) |
| CAPTCHA/blocking risk | Rendah (vendor handle) | Rendah–sedang (actor pakai stealth) | **Tinggi** — IP VPS bisa diblokir |
| Maintenance | Rendah | Rendah–sedang (versi actor) | **Tinggi** (kontinu) |
| Data fields | Lengkap (id, author, rating, text, timestamp, owner reply, likes, place detail) | Lengkap (text, rating, date, reviewer, place; owner reply bervariasi per versi actor) | Terbatas dari DOM (rating, text, author, date, kadang owner reply) |
| Legal/terms risk | Sedang (third-party scraping; vendor handle) | Sedang (third-party scraping) | **Tertinggi** (scraping langsung Google Maps) |
| Waktu implementasi | **~0 hari** (adapter siap; tinggal key + live verify) | 0.5–1 hari (adapter baru + polling) | 2–5 hari + debugging kontinu |
| Kecocokan PublicReviewSourceAdapter | **Sempurna** — sudah diimplementasi & diuji | Baik — implementasi baru mudah | Bisa, tapi fragile |

## Rekomendasi

- **Provider utama: Outscraper** — adapter sudah siap dan teruji; jalur tercepat
  hanya dengan menyediakan `OUTSCRAPER_API_KEY`. Tidak ada implementasi tambahan.
- **Fallback: Apify (Google Maps Reviews Scraper)** — jika key Outscraper sulit
  diperoleh, Apify API token mudah diaktifkan; implementasi adapter baru
  ±0.5–1 hari. Biaya per review lebih rendah.
- **Internal scraper: hanya eksperimen / fallback terakhir** — bukan pilihan
  produksi karena stabilitas rendah, risiko block/CAPTCHA tinggi, maintenance
  besar, dan risiko legal tertinggi.

## Estimasi Biaya Pilot

- **Pilot 100 review**: Outscraper ±$0.50–0.70 · Apify ±$0.10–0.30 · Internal $0
- **1.000 review**: Outscraper ±$5–7 · Apify ±$0.60–2.50 · Internal $0 (+dev time)
- Catatan: harga indikatif per 2026; verifikasi di dashboard vendor saat aktivasi.

## Credential yang Dibutuhkan

- **Outscraper**: `OUTSCRAPER_API_KEY` (env, chmod 600, JANGAN di commit/chat/log)
- **Apify (jika fallback)**: `APIFY_API_TOKEN` (env, aturan sama)
- Tidak ada credential Google/OAuth — GRM Monitor non-login.

## Risiko

1. **Legal/ToS**: scraping Google Maps via third-party tetap risiko ToS; vendor
   yang menangani eksekusi, tapi mitigasi = batasi volume, jangan jual dataset
   mentah, tampilkan insight bukan eksploitasi identitas (sudah di desain).
2. **Biaya tak terduga**: batasi dengan `PUBLIC_REVIEW_MAX_REVIEWS=100` saat
   pilot; aktifkan cost alert di vendor bila tersedia.
3. **Kualitas data**: validasi manual ≥10 review terhadap Google Maps sebelum
   mempercayai pipeline (checklist RUN_11).
4. **Place ID placeholder**: `ChIJ0-depok-margonda-001` adalah contoh mock —
   wajib discovery nyata + verifikasi sebelum live sync.

## Langkah Aktivasi (jalur tercepat = Outscraper)

1. Dapatkan `OUTSCRAPER_API_KEY` dari https://app.outscraper.com (set lokal, jangan via chat)
2. Set `.env`: `PUBLIC_REVIEW_PROVIDER=outscraper`, `OUTSCRAPER_API_KEY=...`,
   `PUBLIC_REVIEW_PAGE_SIZE=50`, `PUBLIC_REVIEW_MAX_REVIEWS=100`; `chmod 600 .env`
3. Restart app → verifikasi `configured_provider=outscraper`
4. `POST /api/public/discover {"query":"Bubur Fay","city":"Depok"}` (discovery NYATA)
5. Verifikasi Place ID asli + Maps URL + nama/alamat/kota/rating terhadap Google Maps
6. `POST /api/public/verify` (satu outlet aktif; JANGAN Harjamukti)
7. `POST /api/public/sync` → catat received/inserted/updated/skipped/failed/pages/duration
8. Sync kedua (idempotency) + incremental
9. Validasi manual ≥10 review (rating/teks/tanggal/owner reply/masking/source/duplicate/rating-only/geo)
10. Validasi dashboard + export; buat live audit record
11. Gate L + regression B–L
12. Update RUN_11 status → `completed` / `completed_with_limitations`
- Jika Outscraper tidak tersedia → langkah sama dengan Apify (implementasi
  `ApifyPublicReviewAdapter` + token + polling dataset).

## Keputusan Go/No-Go

- **Outscraper: GO** (saat key tersedia; 0 hari implementasi tambahan)
- **Apify: GO sebagai fallback** (0.5–1 hari implementasi; token mudah)
- **Internal scraper: NO-GO untuk produksi** (eksperimen saja)

RUN_11 tetap **BLOCKED** sampai salah satu provider live benar-benar berhasil
di-verifikasi. Dokumen ini TIDAK mengubah status.
