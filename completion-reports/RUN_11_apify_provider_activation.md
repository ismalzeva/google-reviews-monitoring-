# COMPLETION REPORT — RUN_11: Apify Provider Activation

Status: **completed_with_limitations** (adapter + stub tests selesai; live BELUM)
RUN_11 keseluruhan: **tetap BLOCKED** sampai `APIFY_API_TOKEN` dipasang lokal dan live pilot dijalankan
Tanggal: 2026-08-02
Source of truth: skill `grm-apify-public-review-provider`

## Ringkasan

`ApifyPublicReviewAdapter` diimplementasikan dan diuji penuh dengan HTTP stubs.
Outscraper adapter TIDAK dihapus; provider abstraction dijaga; dashboard dan
analytics engine TIDAK berubah. Token Apify belum tersedia → live belum dijalankan.

## Adapter

- `app/adapters/apify_public_review_adapter.py` — `ApifyPublicReviewAdapter`
- Mengimplementasikan `PublicReviewSourceAdapter` (fetch_location, list_reviews_by_place_id)
- Tambahan: `discover()` (discovery actor), `health_check()`
- Flow: `POST /v2/acts/{actorId}/runs` → poll status → `defaultDatasetId` → `GET /v2/datasets/{id}/items`
- Actor ID encoding slash → tilde (`compass~google-maps-reviews-scraper`)
- Run cache per (place_id, since): satu actor run per sync; pagination dataset internal + window offset/limit
- Retry 429/transient 5xx (exponential backoff); 401/403 TIDAK di-retry (AUTH_FAILED)
- Placeholder Place ID (`ChIJ0-[slug]-###`) ditolak (`PLACEHOLDER_REJECTED`)
- `seen_ids` no-progress guard di dataset pagination
- Deterministic fallback review ID (`hash_` + sha256) saat Actor tidak memberi ID/URL
- Reviewer name masking; foto profil reviewer TIDAK disimpan; token TIDAK pernah di-log/error

## Actors (schema diverifikasi langsung dari Apify Store 2026-08-02)

### Review: `compass/google-maps-reviews-scraper`
- Input: `startUrls[{url}]`, `placeIds[]`, `maxReviews`, `reviewsSort`, `reviewsStartDate`, `reviewsFilterString`
- Output: `text`, `textTranslated`, `publishAt`, `publishedAtDate` (ISO), `likesCount`, `reviewId`, `reviewUrl`, `stars` (1-5), `responseFromOwnerDate`, `responseFromOwnerText`, `reviewImageUrls`, `reviewOrigin`, `name`, `reviewerId`, `reviewerUrl`, `reviewerNumberOfReviews`, `reviewerPhotoUrl`, `isLocalGuide`, `title`, `placeId`, `address`, `location` (lat/lng), `categories`, `totalScore`, `permanentlyClosed`, `temporarilyClosed`, `reviewsCount`

### Discovery: `compass/crawler-google-places`
- Input: `searchStringsArray`, `maxCrawledPlacesPerSearch` (+ lokasi)

## Provider Configuration

Env baru (`.env.example`, tanpa secret):
- `PUBLIC_REVIEW_PROVIDER=apify` (diizinkan: mock | outscraper | apify)
- `APIFY_API_TOKEN` (wajib untuk mode apify; fail-safe ValueError jika kosong; NO silent fallback)
- `APIFY_REVIEW_ACTOR_ID=compass/google-maps-reviews-scraper`
- `APIFY_DISCOVERY_ACTOR_ID=compass/crawler-google-places`
- `APIFY_TIMEOUT_SECONDS=180`, `APIFY_POLL_INTERVAL_SECONDS=3`, `APIFY_MAX_RETRIES=3`
- `APIFY_MAX_REVIEWS=100`, `APIFY_MAX_PLACES=10`
- Opsional: `APIFY_REVIEW_TASK_ID`, `APIFY_DISCOVERY_TASK_ID` (production)

## Gap Analysis (Actor → GRM internal)

| GRM field | Sumber Actor | Catatan |
|---|---|---|
| source | apify | source_review_name: `apify:{outlet}:{place}:{rid}` |
| source_review_id | reviewId → reviewUrl → deterministic hash | |
| rating | stars | clamp via normalize |
| review_text | text / textTranslated | "" = rating-only |
| review_date | publishedAtDate (ISO) | |
| owner_reply_text/date | responseFromOwnerText / responseFromOwnerDate | |
| source_url | reviewUrl | |
| reviewer_name_masked | name | masking |
| business_name / full_address | title / address | |
| place_id / maps_url | placeId / konstruksi `place/?q=place_id:` | |
| lat/lng | location.lat/lng | |
| province/city_regency/district | TIDAK disediakan Actor → geo enrichment/unknown | jangan mengarang |
| totalScore / reviewsCount | business_rating / business_review_count | |

## Sync

- `sync_public_reviews` provider-aware via `build_public_review_adapter` (apify termasak)
- `source_review_name` kini ber-prefix provider: `{source}:{outlet}:{place}:{rid}` (cross-branch safe)
- Incremental: `reviewsStartDate` = newest stored date (sort newest)
- Post-sync analysis rule-based tetap berjalan (tidak berubah)
- Data lama dipertahankan saat provider gagal (rollback per outlet)

## Quality Gate M

- File: `tests/gate_m.py`
- Tests: **51 PASS / 0 FAIL** (HTTP stubs; TIDAK ada panggilan API Apify live)
- Cakupan: provider apify, missing token, invalid provider, no silent fallback, token redaction, actor ID encoding, valid/placeholder URL & place, run success/failed/timeout/aborted, rate limit retry, 401 no retry, dataset retrieval, empty dataset, pagination (1500 items), repeated page guard, malformed item partial failure, rating, review text, date, rating-only, owner reply, source URL, reviewer masking, geographic unknown, deterministic fallback ID, cross-branch safe ID, initial sync, second sync idempotency, incremental sync, version history, duplicate prevention, previous data retained on failure, sync statistics, discovery by business/city, result hard limit, Harjamukti excluded, one pilot outlet enforced, OAuth not required, direct reply disabled, auto-reply OFF, reply_enabled=false, tenant isolation, no live HTTP without token, no secret in logs/UI/report

## Regression B–M

- Result: **ALL PASS** (runner non-interaktif, timeout per gate)
- Exit codes: B=0 C=0 D=0 E=0 F=0 G=0 H8=0 I=0 J=0 K=0 L=0 M=0
- Durations: total 64s (Gate M 10s, 51 tests; Gate L 11s, 26 tests; Gate K 6s, 32 tests; dll)

## Bug Fix (ditemukan Gate M)

1. Dataset pagination no-progress guard memakai `_safe_int(reviewId)` → reviewId string menjadi `None` → semua halaman terlihat "sama" dan loop berhenti di halaman 1 (1000/1500). Fix: page_ids pakai string reviewId langsung.

## Live Status

- **BELUM** — `APIFY_API_TOKEN` belum tersedia di server
- Tidak ada klaim live; semua uji stub
- Saat token dipasang lokal: ikuti skill §24 (validasi env tanpa cetak token → restart PID-specific → health check → discovery nyata Bubur Fay → verifikasi satu outlet → manual Actor test ≤10 review → GRM sync 50–100 → validasi manual ≥10 → sync kedua → incremental → dashboard/export → Gate M → regression B–M → update report)

## Safety

- OAuth required: **false**
- Direct reply: **disabled**
- Auto-reply: **OFF**
- reply_enabled: false
- Harjamukti: excluded
- GRM_PILOT_MAX_OUTLETS=1 (enforced)
- Token: env only, never logged/committed; redacted dari error
- Placeholder Place ID ditolak; tidak ada silent fallback ke mock

## Limitations

1. Live sync belum diverifikasi (token belum tersedia)
2. Input schema Actor diverifikasi dari halaman publik Apify Store; verifikasi final via manual run (skill §7 langkah 3–4) tetap diperlukan saat token ada
3. `reviewsStartDate` incremental bergantung Actor; fallback: limited newest + dedup lokal
4. Route discovery belum dialihkan ke Apify discovery actor (masih search_places mock) — discovery live via `adapter.discover()` tersedia untuk dipakai saat pilot
5. Apify Task (production) belum dipakai — direct Actor call untuk pilot

## Commit Hash

`<commit>` (diisi setelah commit)

## Working Tree Status

`<tree>` (diisi setelah commit)

## Konfirmasi

- RUN_11 keseluruhan tetap **BLOCKED** sampai token + live pilot
- RUN_12 **belum dimulai**
- GRM Manage (OAuth/Pub/Sub/direct reply) tetap nonaktif
