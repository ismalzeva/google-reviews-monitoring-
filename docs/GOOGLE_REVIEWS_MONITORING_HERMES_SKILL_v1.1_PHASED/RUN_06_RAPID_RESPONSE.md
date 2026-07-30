---
name: run-06-rapid-response
phase: 6
---

# RUN 06 — RAPID RESPONSE, APPROVAL & MODERATION

## Prasyarat

RUN 03, RUN 04, dan RUN 05 selesai.

## Instruksi untuk Hermes

Baca:

1. `README_FIRST.md`
2. `06_RAPID_RESPONSE_AGENT.md`
3. bagian urgency pada `05_AI_REVIEW_ANALYSIS_RULES.md`
4. `08_DATA_CONTRACTS_AND_OUTPUT_SCHEMA.md`
5. Bagian Gate F dalam `09_QUALITY_GATES_ACCEPTANCE_TESTS.md`
6. `10_COMPLETION_REPORT_TEMPLATE.md`

## Scope

- response routing;
- Bubur Fay brand tone;
- draft reply;
- safe auto-reply eligibility;
- human approval;
- edit/reject flow;
- publication idempotency;
- update existing reply;
- moderation status;
- rejected-reply correction flow;
- response metrics;
- audit trail.

Auto-reply harus OFF secara default sampai seluruh Gate F dan security check lulus.

## Jangan Kerjakan

- perluasan ke platform selain Google;
- menghapus review;
- meminta pelanggan menghapus review;
- auto-reply pada rating 1–2 atau critical.

## Definition of Done

- positive-safe route lulus;
- rating 1–2 menunggu approval;
- critical escalation route tersedia;
- duplicate publication dicegah;
- moderation rejection ditangani;
- Gate F lulus;
- completion report dibuat.

Setelah selesai, berhenti dan jangan mengerjakan RUN 07.
