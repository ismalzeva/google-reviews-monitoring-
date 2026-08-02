# COMPLETION REPORT — RUN_10: Production Public Review Adapter

Status: **completed_with_limitations**
Tanggal: 2026-08-02
Base: RUN_09 (commit 533c054)
Kontrak: RUN_10 directive + `GRM_PUBLIC_MONITORING_SKILL.md`

## Ringkasan

Adapter produksi pertama untuk review publik nyata: **OutscraperPublicReviewAdapter**. Provider runtime config, sync incremental + pagination, sync statistics, export metadata, dan fix shell warning `rtk-functions.sh`. Apify = fallback berikutnya (interface extensible). MScrape/Playwright TIDAK diimplementasikan.

## Adapter

- `OutscraperPublicReviewAdapter` — `app/adapters/outscraper_public_review_adapter.py`
- Menerima Place ID (Maps URL di-parse di layer API → place_id)
- limit, sort order (`sort` param), pagination via `offset`
- timeout (`PUBLIC_REVIEW_TIMEOUT`), retry exponential backoff (`PUBLIC_REVIEW_MAX_RETRIES`, 2^n)
- rate-limit handling (429/5xx → retry; error normalized `OutscraperError{message, status_code, retryable, payload}`)
- raw payload preservation (per-review vendor payload + `_collected_at` + `_provider` → ReviewRawPayload)
- source label `outscraper`, collected_at, provenance
- deterministic fallback ID: `hash_` + sha256(place_id|author|timestamp|rating|text)[:32]` saat vendor ID hilang
- incremental `since` filter (tz-aware perbandingan datetime)

## Provider Configuration

Env baru:
- `PUBLIC_REVIEW_PROVIDER` = mock | outscraper (default mock)
- `OUTSCRAPER_API_KEY` (wajib untuk mode outscraper)
- `PUBLIC_REVIEW_TIMEOUT` (30)
- `PUBLIC_REVIEW_MAX_RETRIES` (3)
- `PUBLIC_REVIEW_PAGE_SIZE` (100)
- `PUBLIC_REVIEW_MAX_REVIEWS` (0 = unlimited)

Aturan:
- Production mode TIDAK fallback diam-diam ke mock → `build_public_review_adapter()` raise ValueError
- API key hilang → ValueError jelas ("OUTSCRAPER_API_KEY belum diset...")
- API key TIDAK pernah di-log / di-commit (hanya env)
- Mock tetap tersedia untuk test

## Live/Stub Status

- **STUB**: semua test memakai HTTP stubs (`unittest.mock.patch` pada `requests.get`) + fixture Outscraper payload
- **LIVE: BELUM** — `OUTSCRAPER_API_KEY` belum tersedia di server; tidak ada klaim live sync
- Mode aktif di server tetap `mock` sampai key disediakan

## Pagination Status

- ✅ Adapter: pagination via `offset` (loop sampai page < page_size)
- ✅ Sync: loop `offset += len(reviews)` hingga adapter return []
- ✅ Test: `test_pagination` (240 review → 3 halaman)

## Incremental Sync Status

- ✅ Sync menghitung `since` = newest review date per outlet
- ✅ Adapter memfilter `since` (tz-aware)
- ✅ `full_sync=True` untuk full refresh (update detection)
- ✅ Test: `test_incremental_since_filter`

## Normalization

Mapping Outscraper → internal: review_id→source_review_id, review_rating→rating, review_text→review_text, review_datetime_utc/timestamp→review_date, owner_answer→owner_reply_text, owner_answer_datetime_utc/timestamp→owner_reply_date, author_title→reviewer_name_masked, plus place name/address/city/state/district di fetch_location.

Aturan:
- jangan mengarang kecamatan/kota — `district`/`city` dari provider atau geo_service; tidak ada → unknown + flag
- rating-only valid (review_text="")
- review tanpa ID vendor → deterministic hash
- dedup aman antar-cabang: `source_review_name = public:{outlet.id}:{place_id}:{review_id}` (cross-branch safe)
- review update → version history (ReviewVersion v2)

## Test Gate K

- File: `tests/gate_k.py`
- Tests: **32 PASS / 0 FAIL**
- Cakupan: adapter contract, valid place ID, valid Maps URL, missing API key, timeout, retry, rate limit, malformed payload, empty result, pagination, incremental sync, rating-only, owner reply, reviewer masking, source labeling, raw payload preservation, deterministic fallback ID, duplicate prevention, review update/versioning, geographic unknown, tenant isolation, no silent mock fallback, sync statistics, previous data retained on failure, export filter metadata, Harjamukti excluded, direct reply disabled, auto-reply OFF

## Regression B–K

- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS
- Gate F: PASS
- Gate G: PASS
- Gate H8: PASS (52/52)
- Gate I: PASS (77/77)
- Gate J: PASS (43/43)
- Gate K: PASS (32/32)

## Export Metadata Status

- ✅ CSV: baris `# key: value` (rentang_waktu, kota_kabupaten, kecamatan, cabang, kategori, rating, sentimen, urgensi, sumber, generated_at) sebelum header
- ✅ XLSX: sheet "Export Info" (metadata) + sheet "Public Reviews" (data)
- ✅ Test: `test_export_csv_has_filter_metadata`, `test_export_xlsx_has_info_sheet`
- PDF: bukan prioritas RUN_10 (tetap limitation)

## Shell Warning Resolution

- File: `/home/ubuntu/.hermes/scripts/rtk-functions.sh`
- **Akar masalah**: `.bashrc` line 78 mendefinisikan `alias ls='ls --color=auto'`. Saat interactive shell (`bash -ic`/`bash -lic`) me-source rtk-functions.sh, bash melakukan **alias expansion saat parse** → baris `ls() { ... }` menjadi `ls --color=auto () { ... }` → `syntax error near unexpected token '('`
- `bash -n` PASS & `bash -c source` OK karena alias tidak aktif di konteks itu
- **Fix (terisolasi)**: tambah `unalias ls tree find ... 2>/dev/null || true` di awal file
- Verifikasi: `bash -ic` dan `bash -lic` → 0 syntax error
- Tidak mengubah environment global; hanya file rtk-functions.sh

## Sync Statistics

- Response sync: `provider`, `sync_status` (ok/partial_failure), `locations_*`, `reviews_received/inserted/created/updated/skipped/unchanged`, `rating_only_reviews`, `duplicates_skipped`, `error_summary` (tanpa secret/raw vendor error sensitif — hanya message)
- `/api/public/locations`: `configured_provider`, per-outlet `provider`, `last_sync`, `sync_status`, `reviews_inserted/updated/skipped`, `error_count`

## Limitations

1. **Live sync belum diverifikasi** — API key Outscraper belum tersedia; adapter + stub tests selesai, status jujur `completed_with_limitations`
2. **Apify fallback belum diimplementasikan** — arsitektur siap (interface + provider config)
3. **PDF export belum** (bukan prioritas RUN_10)
4. **Sort order** — `sort` param dipassing ke provider; tidak ada pilihan UI sort
5. **Raw vendor error di UI** — hanya `error` message (tidak sensitif); payload lengkap tersimpan di ReviewRawPayload
6. **`updateIfExists`/async Outscraper belum dipakai** — sync mode saja (offset pagination)

## Safety

- OAuth required: **false**
- Direct reply: **disabled** (`reply_enabled=false`)
- Auto-reply: **OFF**
- `reply_enabled`: false
- Harjamukti: **excluded** (old_or_closed, 0 review)
- API key: env only, never logged
- No silent fallback production→mock

## Commit Hash

`b48453f` — feat: add RUN_10 production public review adapter

## Working Tree Status

Clean (git status kosong)

## Konfirmasi

- RUN_11 **belum dimulai**
- GRM Manage (OAuth/Pub/Sub/direct reply) tetap nonaktif
