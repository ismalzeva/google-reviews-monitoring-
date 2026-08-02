# COMPLETION REPORT — RUN_09: Public Monitoring & Review Analytics

Status: **completed_with_limitations**
Tanggal: 2026-08-02
Kontrak: `GRM_PUBLIC_MONITORING_SKILL.md` (skill `grm-public-monitoring-review-analytics`)

## Ringkasan

RUN_09 lama (live Google activation) diganti sesuai skill: **GRM Monitor** — monitoring & analytics review publik TANPA login Google Business Profile. GRM Manage (OAuth/Pub/Sub/direct reply) tetap nonaktif.

Pipeline diimplementasikan: `Public Location Discovery → Public Review Collection → Raw Data Preservation → Normalization → Deduplication → Review Versioning → Geographic Enrichment → AI Analysis (rule-based) → Category Classification → Period Aggregation → Location Aggregation → Pattern Detection → Priority Scoring → Dashboard → Export`

## Adapters

- `PublicReviewSourceAdapter` (ABC) — `app/adapters/public_review_source_adapter.py`
- `MockPublicReviewAdapter` — `app/adapters/mock_public_review_adapter.py` (dataset Bubur Fay: 2 lokasi, 17 review, rating-only, owner reply; label source `mock`)
- Adapter produksi (Outscraper/Apify/MScrape/Playwright) **belum** diimplementasikan — gap untuk RUN berikutnya (limitation)

## Input

- Nama bisnis (`Bubur Fay`)
- Nama bisnis + kota/kabupaten (`Bubur Fay`, `Depok`)
- Google Maps URL (termasuk `place_id:` dan format hex `!3m5!1s`)
- Place ID langsung
- Unknown place → 404 jujur (tanpa data palsu)

## Process

1. `/api/public/discover` — cari kandidat publik, normalisasi, dedup (by place_id), tampilkan kandidat existing + baru
2. `/api/public/verify` — verifikasi pemilik (owner_confirmed → Outlet; old_or_closed → excluded; Harjamukti excluded)
3. `/api/public/sync` — `sync_public_reviews()`: fetch publik by `public_place_id` (tanpa OAuth/gbp_location_id), upsert dengan unique `tenant+source+source_review_name`, owner reply disimpan, location metadata (rating/review count/maps_url) di-refresh, geo enrichment (OSM Nominatim → province/city_regency/district; gagal → `unknown` + `needs_geographic_resolution`)
4. Post-sync: analisis rule-based per review teks (sentiment, topics, urgency, reputation risk)
5. Analytics: executive summary, per-category (12-taxonomy multi-label + kritis), per-branch, per-geography (kota/kabupaten ≠ kecamatan), period trend, review explorer, priority insights
6. Export CSV + XLSX (PDF = limitation)

## Output

- Dashboard modules: summary, categories, branches, geography, period, explorer, priority (semua `GET /api/public/analytics/*`)
- Filter global: rentang waktu (7/30/90 hari, bulan YYYY-MM, custom start/end, comparison `compare=1`), provinsi, kota/kabupaten, kecamatan, cabang, kategori, rating, sentimen, urgensi, sumber, has_reply, rating_only, text_only
- Export: CSV + XLSX dengan kolom lengkap (tanggal, cabang, kota/kabupaten, kecamatan, rating, sentimen, kategori, urgensi, review, owner reply status, sumber, reviewer masked, rating_only)
- Reviewer masking aktif di semua output (explorer, export, priority)
- Source labeling eksplisit (`mock`, `public_scraping`)

## Dashboard Filters

- Rentang waktu: ✅ (days, month, custom, comparison)
- Kota/Kabupaten: ✅ (`city_regency`)
- Kecamatan: ✅ (`district`)
- Cabang: ✅ (`outlet_id`)
- Kategori: ✅ (`category`, multi-label via topics)
- Rating/Sentimen/Urgensi/Sumber/has_reply/rating_only: ✅

## Quality Gate

- Tests: **43** (Gate J — `tests/gate_j.py`)
- Result: **43 PASS / 0 FAIL**

## Regression

- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS
- Gate F: PASS
- Gate G: PASS
- Gate H8: **52/52 PASS** (fix: test `pilot_outlet_limit_default_1` terkontaminasi `GRM_PILOT_MAX_OUTLETS=3` dari .env → unset sementara)
- Gate I: PASS
- Gate J: **43/43 PASS**

## Limitations

1. **Adapter publik produksi belum ada** — hanya MockPublicReviewAdapter. Live scraping (Outscraper/Apify/MScrape/Playwright) adalah gap RUN berikutnya.
2. **Pagination adapter** — mock tidak punya pagination; `limit` parameter di-support interface tapi belum dipakai sync.
3. **PDF export belum tersedia** — CSV/XLSX sudah jalan; PDF ditandai limitation (sesuai §12).
4. **Filter info pada export** — nama file ber-timestamp, source ada per-row; metadata filter lengkap (periode/kota/district/cabang/kategori) belum ditulis ke file export.
5. **Category inference bergantung analysis rule-based** — kualitas klasifikasi sebatas keyword; LLM analysis (deep) belum dijalankan untuk public path.
6. **XLSX butuh `openpyxl`** — sudah di-install di venv, tapi belum masuk requirements.txt.
7. **Test client `session_transaction` tidak reliable untuk ganti user** — tenant isolation test memakai jalur login/logout nyata (bukan bug aplikasi; verified).
8. **Kandidat `old_or_closed` tidak dibuat sebagai Outlet** — hanya status candidate; konsisten dengan kebijakan exclude.

## Scraping Limitation

- Semua data review publik saat ini dari **mock dataset** (deterministik, label `mock`)
- Tidak ada scraping live Google Maps
- CAPTCHA/rate-limit handler: fail-safe via rollback per outlet + error dict di SyncReport; retry manual via re-POST sync (idempotent)

## Source Status

- `public_scraping` (outlet default source) + `mock` (review adapter label) — keduanya eksplisit
- Mock tidak pernah dipresentasikan sebagai official Google API

## No-Login Status

- ✅ GRM Monitor bekerja tanpa Google OAuth / tanpa `gbp_location_id`

## Direct Reply Status

- Disabled — `reply_enabled=false` di semua outlet; tidak ada endpoint publikasi balasan

## Auto-Reply Status

- OFF (`is_auto_reply_enabled()` = false; GRM_PILOT_MODE default true)

## Excluded Locations

- Bubur Fay Harjamukti (`ChIJ0-harjamukti-old-006`, CLOSED_PERMANENTLY) — verified `old_or_closed`, tidak pernah sync

## Migration

- `1c14be9007e8` — add public monitoring geographic fields (outlets.province/city_regency/district/maps_url/business_rating/business_review_count/source/needs_geographic_resolution; location_candidates.province/city_regency/district/needs_geographic_resolution; reviews.owner_reply_text/owner_reply_date/source_url)

## File Baru/Diubah

- `app/adapters/public_review_source_adapter.py` (baru)
- `app/adapters/mock_public_review_adapter.py` (baru)
- `app/services/geo_service.py` (baru)
- `app/services/public_analytics.py` (baru)
- `app/routes/public.py` (baru)
- `app/services/sync_service.py` (+sync_public_reviews, +post-sync analysis)
- `app/services/review_service.py` (normalize: owner reply + source_url)
- `app/services/discovery.py` (_ensure_outlet: geo/maps/rating)
- `app/models/entities.py` (kolom baru)
- `tests/gate_j.py` (baru)
- `tests/gate_h8.py` (fix env contaminasi)
- `app/__init__.py` (register public blueprint)
- `migrations/versions/1c14be9007e8_*.py` (baru)

## Commit Hash

`533c054` — feat: complete RUN_09 public review monitoring and geographic analytics

## Working Tree Status

Clean (git status kosong)

## Konfirmasi

- RUN berikutnya **belum dimulai**. GRM Manage (OAuth/Pub/Sub/direct reply) tetap nonaktif sampai instruksi eksplisit.
