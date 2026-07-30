---
name: run-04-review-ingestion
phase: 4
---

# RUN 04 — REVIEW INGESTION & MONITORING

## Prasyarat

RUN 03 selesai dan minimal satu official location tersedia. Bila API approval belum tersedia, jalankan jalur impor Outscraper dan tandai limitation.

## Instruksi untuk Hermes

Baca:

1. `README_FIRST.md`
2. `04_REVIEW_INGESTION_AND_REALTIME_MONITORING.md`
3. `08_DATA_CONTRACTS_AND_OUTPUT_SCHEMA.md`
4. Bagian Gate D dalam `09_QUALITY_GATES_ACCEPTANCE_TESTS.md`
5. `10_COMPLETION_REPORT_TEMPLATE.md`

## Scope

- historical review sync;
- pagination;
- multi-location sync;
- raw and normalized storage;
- rating-only handling;
- idempotent upsert;
- review version history;
- CSV/XLSX Outscraper import;
- import validation;
- NEW_REVIEW and UPDATED_REVIEW event pipeline;
- Pub/Sub configuration bila akses tersedia;
- scheduled reconciliation;
- sync report.

## Jangan Kerjakan

- AI topic analysis;
- public reply;
- operational issue tracking lengkap.

## Definition of Done

- historical/import data masuk;
- duplicate dicegah;
- rating-only benar;
- event duplicate tidak menggandakan review;
- updated review memiliki version history;
- Gate D lulus;
- completion report dibuat.

Setelah selesai, berhenti dan jangan mengerjakan RUN 05.
