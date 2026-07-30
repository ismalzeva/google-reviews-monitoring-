---
name: run-03-google-connection
phase: 3
---

# RUN 03 — GOOGLE BUSINESS PROFILE CONNECTION

## Prasyarat

RUN 01 dan RUN 02 selesai.

## Instruksi untuk Hermes

Baca:

1. `README_FIRST.md`
2. `03_GOOGLE_BUSINESS_PROFILE_CONNECTION.md`
3. bagian reconciliation pada `02_BRANCH_DISCOVERY_AND_VERIFICATION.md`
4. `08_DATA_CONTRACTS_AND_OUTPUT_SCHEMA.md`
5. Bagian Gate C dalam `09_QUALITY_GATES_ACCEPTANCE_TESTS.md`
6. `10_COMPLETION_REPORT_TEMPLATE.md`

## Scope

- OAuth 2.0;
- consent dan scope;
- account listing;
- pemilihan account;
- official location listing;
- pagination;
- rekonsiliasi Place ID;
- ambiguous match flow;
- connection health;
- disconnect/revoke;
- encrypted token storage;
- reply-enabled eligibility flag.

## Jangan Kerjakan

- review sync massal;
- Pub/Sub;
- AI;
- reply publication.

## Definition of Done

- OAuth flow tersedia;
- account dan location dapat dibaca atau blocker API dijelaskan;
- kandidat dapat direkonsiliasi;
- hanya manageable location yang reply-enabled;
- credential tidak bocor;
- Gate C lulus;
- completion report dibuat.

Setelah selesai, berhenti dan jangan mengerjakan RUN 04.
