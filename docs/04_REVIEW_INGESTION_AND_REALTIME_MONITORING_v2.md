---
name: review-ingestion-and-realtime-monitoring
version: 1.0.0
type: ingestion-skill
status: active
---

# HERMES AGENT SKILL — REVIEW INGESTION & REAL-TIME MONITORING

## 1. PURPOSE

Mengambil review historis, memproses review baru, menangani review yang diperbarui, dan menjaga data tetap konsisten.

## 2. INGESTION MODES

### Mode A — Official API Initial Sync

Gunakan:

- `accounts.locations.reviews.list`;
- atau `accounts.locations.batchGetReviews` untuk beberapa lokasi.

Rules:

- pagination wajib;
- simpan `nextPageToken`;
- page size mengikuti batas API;
- order by update time bila diperlukan;
- simpan average rating dan total review count;
- jangan kehilangan rating-only reviews.

### Mode B — Real-Time Event

Gunakan My Business Notifications API dan Google Cloud Pub/Sub untuk:

- `NEW_REVIEW`;
- `UPDATED_REVIEW`.

Notification adalah trigger, bukan seluruh source record.

Setelah event:

1. validasi event;
2. ambil review terbaru dari API;
3. upsert review;
4. analisis ulang jika isi/rating berubah;
5. evaluasi ulang response route;
6. hindari balasan ganda.

### Mode C — Scheduled Reconciliation

Jalankan sinkronisasi periodik untuk:

- event yang terlewat;
- perubahan balasan;
- perubahan moderation state;
- updated review;
- total review count.

### Mode D — CSV/XLSX Import

Digunakan untuk Outscraper historical import atau fallback.

Review impor:

- boleh dianalisis;
- boleh masuk dashboard;
- tidak otomatis reply-enabled;
- harus dipetakan ke location;
- harus mempertahankan source lineage.

## 3. RAW REVIEW FIELDS

```yaml
source:
source_account_id:
source_location_id:
source_review_name:
review_id:
reviewer:
  display_name:
  is_anonymous:
  profile_photo_url:
star_rating:
comment:
create_time:
update_time:
review_reply:
  comment:
  update_time:
  review_reply_state:
  policy_violation:
review_reply_url:
review_media_items:
raw_payload_hash:
ingested_at:
```

## 4. RATING-ONLY RULE

Review tanpa komentar:

- disimpan;
- dihitung untuk rating metrics;
- dapat memicu response policy bila policy mengizinkan;
- tidak dipaksa menghasilkan topic/issue analysis;
- `has_text: false`;
- `qualitative_analysis_status: not_applicable`.

## 5. IDEMPOTENCY

Primary idempotency key:

```text
tenant_id + source + source_review_name
```

Fallback key untuk import:

```text
tenant_id + outlet_id + reviewer + rating + review_date + normalized_text_hash
```

Satu event yang dikirim berulang tidak boleh:

- membuat review ganda;
- membuat issue ganda;
- memublikasikan reply ganda;
- menghitung metrik dua kali.

## 6. UPDATE HANDLING

Jika review berubah:

- simpan previous version;
- update current review;
- set `review_updated: true`;
- jalankan analisis ulang;
- cek apakah existing reply masih relevan;
- jangan otomatis mengubah reply yang sudah dipublikasikan tanpa policy/approval;
- tandai `reply_reassessment_required` jika risiko meningkat.

## 7. REVIEW DELETION / UNAVAILABLE

Jika review tidak lagi tersedia:

- jangan hard delete historical record;
- set `source_visibility_status: unavailable`;
- simpan last seen;
- jangan menampilkan sebagai review aktif jika source tidak lagi tersedia;
- pertahankan audit trail.

## 8. PUB/SUB REQUIREMENTS

- topic tersedia;
- service account Google memiliki publish permission;
- subscription menggunakan push atau pull yang terautentikasi;
- dead-letter handling;
- retry;
- event deduplication;
- tenant/account routing;
- event timestamp validation;
- monitoring.

## 9. PROCESSING STATUS

```yaml
received
validated
normalized
deduplicated
queued_for_analysis
analyzed
response_routed
completed
failed_retryable
failed_terminal
```

## 10. IMPORT VALIDATION

CSV/XLSX:

- file type valid;
- required columns tersedia;
- rating 1–5;
- date parseable;
- outlet mapping tersedia;
- duplicate detection;
- row-level error report;
- raw file retained;
- import batch ID.

## 11. SYNC REPORT

```yaml
sync_id:
business_id:
account_id:
locations_requested:
locations_succeeded:
locations_failed:
reviews_received:
reviews_created:
reviews_updated:
reviews_unchanged:
rating_only_reviews:
duplicates_skipped:
analysis_jobs_created:
errors:
started_at:
completed_at:
```

## 12. FAILURE POLICY

Jika event masuk tetapi review fetch gagal:

- jangan membuat balasan dari event payload;
- simpan retry job;
- tampilkan failure;
- jangan tandai selesai.

Jika API unavailable:

- scheduled retry;
- exponential backoff;
- no duplicate reply;
- notify admin setelah threshold konfigurasi.

## 13. ACCEPTANCE CRITERIA

- Historical sync berhasil dengan pagination.
- Multi-location sync tidak mencampur tenant/outlet.
- Rating-only review dihitung tetapi tidak dianalisis secara palsu.
- NEW_REVIEW event menghasilkan satu review record.
- Duplicate event tidak menghasilkan duplicate processing.
- UPDATED_REVIEW mempertahankan version history.
- Import Outscraper memiliki lineage.
- Sync report tersedia.
