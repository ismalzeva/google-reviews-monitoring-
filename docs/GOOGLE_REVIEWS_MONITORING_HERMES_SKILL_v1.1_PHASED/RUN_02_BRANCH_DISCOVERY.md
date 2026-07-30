---
name: run-02-branch-discovery
phase: 2
---

# RUN 02 — BRANCH DISCOVERY & OWNER VERIFICATION

## Prasyarat

RUN 01 berstatus `completed` atau `completed_with_limitations` tanpa blocker fondasi.

## Instruksi untuk Hermes

Baca:

1. `README_FIRST.md`
2. `02_BRANCH_DISCOVERY_AND_VERIFICATION.md`
3. `08_DATA_CONTRACTS_AND_OUTPUT_SCHEMA.md`
4. Bagian Gate B dalam `09_QUALITY_GATES_ACCEPTANCE_TESTS.md`
5. `10_COMPLETION_REPORT_TEMPLATE.md`

## Scope

- form input nama brand;
- pencarian kandidat lokasi;
- hasil pencarian “Bubur Fay”;
- normalisasi kandidat;
- deduplikasi;
- tampilan kandidat;
- owner verification;
- status cabang benar, bukan cabang, lama/tutup, duplikat, belum yakin;
- audit keputusan owner.

Gunakan mock adapter bila API key belum tersedia, tetapi tandai limitation dengan jelas.

## Jangan Kerjakan

- OAuth Google Business Profile;
- official location access;
- review ingestion;
- reply.

## Definition of Done

- owner dapat mengetik `Bubur Fay`;
- kandidat tampil;
- kandidat tidak otomatis official;
- owner dapat memverifikasi;
- duplicate candidate ditangani;
- Gate B lulus;
- completion report dibuat.

Setelah selesai, berhenti dan jangan mengerjakan RUN 03.
