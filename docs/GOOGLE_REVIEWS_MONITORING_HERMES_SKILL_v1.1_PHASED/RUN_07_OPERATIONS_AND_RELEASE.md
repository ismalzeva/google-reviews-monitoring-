---
name: run-07-operations-and-release
phase: 7
---

# RUN 07 — ISSUE TRACKING, REPORTING & RELEASE GATE

## Prasyarat

RUN 01–06 selesai.

## Instruksi untuk Hermes

Baca:

1. `README_FIRST.md`
2. `07_ISSUE_ESCALATION_AND_OPERATIONS.md`
3. `08_DATA_CONTRACTS_AND_OUTPUT_SCHEMA.md`
4. seluruh `09_QUALITY_GATES_ACCEPTANCE_TESTS.md`
5. `10_COMPLETION_REPORT_TEMPLATE.md`

## Scope

- issue creation;
- assignment;
- SLA/target configuration;
- status flow;
- escalation;
- repeat-pattern parent issue;
- closure evidence;
- weekly/monthly report;
- final security tests;
- tenant isolation;
- approval bypass test;
- end-to-end test;
- production readiness decision.

## Release Rule

Jika critical safety/security test gagal:

- auto-reply tetap OFF;
- status `not_ready_for_production`;
- remediation wajib spesifik.

## Definition of Done

- issue tidak otomatis selesai ketika reply dipublikasikan;
- critical case tereskalasi;
- pattern review terhubung;
- report tersedia;
- seluruh gate diuji;
- final completion report dibuat;
- status release dinyatakan secara jujur.

Setelah tahap ini, berhenti. Jangan menambah scope baru.
