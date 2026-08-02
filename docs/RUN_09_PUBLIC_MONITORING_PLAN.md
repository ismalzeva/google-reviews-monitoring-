# RUN_09 — PUBLIC MONITORING & REVIEW ANALYTICS

Status: IN PROGRESS
Mulai: 2026-08-02
Kontrak: `GRM_PUBLIC_MONITORING_SKILL.md` (skill `grm-public-monitoring-review-analytics`)

## Arah

RUN_09 lama (live Google activation) DIGANTI. Fokus baru: **GRM Monitor** — monitoring & analytics review publik TANPA login Google Business Profile. GRM Manage (OAuth/Pub/Sub/direct reply) tetap nonaktif (`reply_enabled=false`, auto-reply OFF).

Pipeline: `Public Location Discovery → Public Review Collection → Raw Data Preservation → Normalization → Deduplication → Review Versioning → Geographic Enrichment → AI Analysis → Category Classification → Period Aggregation → Location Aggregation → Pattern Detection → Priority Scoring → Dashboard → Export`

> **STATUS: COMPLETED_WITH_LIMITATIONS (2026-08-02)** — detail lengkap di `completion-reports/RUN_09_public_monitoring.md`. Semua gate B–J hijau (Gate J 43/43). Commit: `feat: complete RUN_09 public review monitoring and geographic analytics`.

## Audit hasil (2026-08-02)

Sudah ada:
- `ReviewSourceAdapter` (ABC) + `MockReviewAdapter` (Bubur Fay)
- `services/discovery.py`: search_places + verify_candidate → LocationCandidate (rating, review_count, google_maps_uri, business_status)
- `services/review_service.py`: normalize_review, upsert_review (unique tenant+source+source_review_name), versioning
- `services/analysis_service.py`: ReviewAnalysis (sentiment, topics, urgency, reputation_risk)
- `services/sync_service.py`: sync_reviews (BUTUH gbp_location_id — bukan public path)
- Dashboard intelligence (gate I): summary, priority, outlet-comparison, management-summary
- Import service (CSV)

Gap terhadap kontrak:
1. **Geographic fields**: Outlet/LocationCandidate tidak punya `province`, `city_regency`, `district`; Outlet tidak punya `maps_url`, `business_rating`, `business_review_count`, `source` → MIGRASI
2. **Review fields**: tidak ada `owner_reply_text`, `owner_reply_date`, `source_url` → MIGRASI
3. **Public adapter**: belum ada `PublicReviewSourceAdapter` interface → MockPublicReviewAdapter
4. **Public sync**: sync_reviews butuh gbp_location_id → perlu `sync_public_reviews` pakai `public_place_id`
5. **Dashboard filter global** (period/city/district/branch/category/rating/sentiment/urgency/source/has_reply/rating_only) belum ada
6. **Review explorer + export CSV/XLSX** belum ada
7. **Reviewer masking** di layer presentasi belum ada

## Implementasi

### Phase 0 — Stabilisasi (DONE)
- [x] Fix gate H8: test `pilot_outlet_limit_default_1` terkontaminasi `GRM_PILOT_MAX_OUTLETS=3` dari .env → unset sementara di test. H8 52/52 OK.

### Phase 1 — Migrasi DB (IN PROGRESS)
- Outlet: +province, +city_regency, +district, +maps_url, +business_rating, +business_review_count, +source
- LocationCandidate: +province, +city_regency, +district, +needs_geographic_resolution
- Review: +owner_reply_text, +owner_reply_date, +source_url

### Phase 2 — Geographic Enrichment
- `services/geo_service.py`: reverse geocode lat/lon → province/city/district via OSM Nominatim; gagal → `unknown` + `needs_geographic_resolution=true`. Jangan mengarang.

### Phase 3 — Public Adapter & Sync
- `app/adapters/public_review_source_adapter.py`: ABC `PublicReviewSourceAdapter` (list_reviews_by_place_id)
- `app/adapters/mock_public_review_adapter.py`: MockPublicReviewAdapter, source='public_scraping', provenance lengkap
- `services/sync_service.py`: +`sync_public_reviews(tenant_id, business_id, outlet_ids, source='public_scraping')` — pakai `public_place_id`, upsert dengan source_review_name unik, owner reply disimpan
- Route: POST `/api/public/discover` (nama/Maps URL/Place ID → kandidat) → POST `/api/public/sync` (pilih lokasi → sync publik)

### Phase 4 — Dashboard & Analytics
- Filter global di query params: period (7/30/90d, month, custom, comparison), province, city_regency, district, branch, category, rating, sentiment, urgency, source, has_reply, rating_only
- Per-category aggregation (multi-label, critical categories)
- Review explorer endpoint + UI tabel
- Export: CSV + XLSX (PDF = limitation)
- Reviewer masking: nama direduksi (`Budi S***`) di semua output

### Phase 5 — Quality Gate & Regression
- `tests/gate_j.py` (public monitoring): discovery input, dedup, branch verify, old/closed excluded, public sync, geographic enrichment, rating-only, multi-label, dashboard filters, tenant isolation, masking, export, source labeling
- Regression: Gate B, C, D, E, F, G, H8, I semua hijau

### Phase 6 — Report & Commit
- `completion-reports/RUN_09_public_monitoring.md` (format §18)
- Commit: `feat: complete RUN_09 public review monitoring and geographic analytics`

## Safety (kontrak §15)
- OAuth tidak diperlukan untuk GRM Monitor
- `reply_enabled=false`, auto-reply OFF, direct reply nonaktif
- Harjamukti excluded (old_or_closed)
- Tidak ada fallback diam-diam production → mock
- Tidak ada review palsu saat vendor gagal
