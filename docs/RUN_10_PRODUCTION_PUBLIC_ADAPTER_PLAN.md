# RUN_10 — PRODUCTION PUBLIC REVIEW ADAPTER

Status: **COMPLETED_WITH_LIMITATIONS (2026-08-02)**
Mulai: 2026-08-02
Base: RUN_09 (commit 533c054) — GRM Monitor tanpa OAuth, mock-only
Detail: `completion-reports/RUN_10_production_public_adapter.md`
Commit: `feat: add RUN_10 production public review adapter`

## Tujuan

Adapter produksi pertama untuk mengambil review publik nyata: **Outscraper**. Apify = fallback berikutnya (arsitektur extensible). MScrape/Playwright TIDAK diimplementasikan (interface tetap extensible).

## Audit & Gap Analysis

### Kontrak PublicReviewSourceAdapter (RUN_09)
- `fetch_location(place_id)` → dict lokasi ternormalisasi
- `list_reviews_by_place_id(place_id, since, limit, **kwargs)` → list dict review ternormalisasi
- source label per adapter; provenance; tidak boleh fabricate; tidak boleh silent fallback production→mock

### Schema Outscraper (Google Maps Reviews API)
Endpoint: `GET https://api.app.outscraper.com/maps/reviews-v3`
Params: query (place ID / URL / text), limit, offset, sort, async, cutoff, reviewsType, updateIfExists, language
Response: `{"data": [{"query", "name", "address", "rating", "reviews", "latitude", "longitude", "place_id", "reviews_data": [...]}]}`

Review item Outscraper → mapping internal:
| Outscraper | Internal | Catatan |
|---|---|---|
| `review_id` | source_review_id | kosong → deterministic hash |
| `review_rating` | rating | clamp 1-5 |
| `review_text` | review_text / comment | "" → rating-only |
| `review_datetime_utc` / `review_timestamp` | review_date | ISO |
| `owner_answer` | owner_reply_text | nullable |
| `owner_answer_datetime_utc` / `owner_answer_timestamp` | owner_reply_date | nullable |
| `author_title` | reviewer_name_masked | masking |
| `review_likes` / `review_img_url` dll | raw_payload | preservation |
| place `place_id` | place_id | |
| place `name` / `address` / `city` / `state` | business_name / full_address / city_regency / province | |
| place `district`/`suburb` (jika ada) | district | tidak ada → unknown |

### Gap vs RUN_09
1. Tidak ada adapter produksi → OutscraperPublicReviewAdapter (baru)
2. `sync_public_reviews` hardcode MockPublicReviewAdapter → provider config
3. Tidak ada retry/timeout/rate-limit → masuk adapter
4. Sync stats minimal → tambah provider/status/inserted/updated/skipped/failed
5. Export tanpa metadata filter → tambah metadata CSV/XLSX
6. UI status sumber → /api/public/locations + /api/public/sync response

## Implementasi

### 1. OutscraperPublicReviewAdapter (`app/adapters/outscraper_public_review_adapter.py`)
- API key dari env `OUTSCRAPER_API_KEY` (tidak pernah log)
- `fetch_location(place_id)` — limit=1, parse lokasi
- `list_reviews_by_place_id(place_id, since, limit, offset=0)` — pagination via offset
- Retry exponential backoff (PUBLIC_REVIEW_MAX_RETRIES, backoff 1s*2^n) untuk 429/5xx/timeout
- Rate-limit: 429 → retry; normalisasi error `{"error", "retryable", "status_code", "provider"}`
- Raw payload preservation (raw_payload per review + response meta)
- Deterministic fallback ID: `sha256(place_id|author|timestamp|rating|text)[:32]`
- `since` filter: skip review lebih lama dari since
- `PUBLIC_REVIEW_MAX_REVIEWS` cap

### 2. Runtime config (`app/services/public_provider.py`)
Env: PUBLIC_REVIEW_PROVIDER (mock|outscraper, default mock), OUTSCRAPER_API_KEY, PUBLIC_REVIEW_TIMEOUT (30), PUBLIC_REVIEW_MAX_RETRIES (3), PUBLIC_REVIEW_PAGE_SIZE (100), PUBLIC_REVIEW_MAX_REVIEWS (0=unlimited)
- `get_public_review_provider()`
- `build_public_review_adapter(source=None)` → provider-aware; outscraper tanpa key → ValueError jelas; provider tak dikenal → ValueError

### 3. Sync (`sync_public_reviews`)
- Ganti konstruksi adapter → `build_public_review_adapter(source)`
- Pagination loop via adapter (offset), incremental via `since` (max review date outlet)
- Stats: provider + inserted/updated/skipped/failed sudah di SyncReport; tambah response
- Provider gagal → rollback per outlet, data lama dipertahankan

### 4. UI/API status
- `/api/public/sync` response: + provider, sync_status, error_summary
- `/api/public/locations`: + provider, last_sync (SyncReport terbaru), review counts, source status (tanpa secret/raw error sensitif)

### 5. Export metadata
- CSV: baris `# key: value` di atas (filter aktif + generated_at)
- XLSX: sheet "Export Info" + sheet data
- Route export_csv/xlsx membaca `_filters()` → metadata

### 6. Shell warning `rtk-functions.sh`
- Audit: baca file, cek baris 4, cek dari mana di-source
- Perbaiki hanya jika aman & terisolasi

### 7. Gate K (`tests/gate_k.py`) — 28 test
Adapter contract, valid place ID, valid Maps URL, missing key, timeout, retry, rate limit, malformed payload, empty result, pagination, incremental sync, rating-only, owner reply, reviewer masking, source labeling, raw payload preservation, deterministic fallback ID, duplicate prevention, review update/versioning, geographic unknown, tenant isolation, no silent mock fallback, sync statistics, previous data retained on failure, export filter metadata, Harjamukti excluded, direct reply disabled, auto-reply OFF.
→ HTTP stubs (unittest.mock.patch requests.get), TIDAK panggil API produksi.

### 8. Regression + Report
- Gate B–K semua hijau, baru commit
- `completion-reports/RUN_10_production_public_adapter.md`
- Commit: `feat: add RUN_10 production public review adapter`

## Safety
- No silent fallback production→mock (raise jelas)
- API key hanya env; tidak pernah di-log/di-commit
- OAuth tidak wajib; reply_enabled=false; auto-reply OFF; Harjamukti excluded
- Stub test tidak menyentuh API produksi
