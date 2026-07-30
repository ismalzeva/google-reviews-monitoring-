---
name: execution-sequence
version: 1.1.0
project: Google Reviews Monitoring & Intelligence
pilot: Bubur Fay
type: phased-implementation-router
---

# EXECUTION SEQUENCE — JANGAN DIKERJAKAN SEKALIGUS

## Prinsip

Semua skill `.md` boleh diunggah ke Hermes sejak awal agar menjadi referensi lengkap.

Namun, implementasi WAJIB dijalankan bertahap. Jangan memberi Hermes satu perintah untuk membangun seluruh produk sekaligus.

Setiap tahap:

1. hanya membaca file yang disebutkan;
2. tidak mengerjakan tahap berikutnya;
3. menjalankan quality gate tahap tersebut;
4. membuat completion report;
5. berhenti setelah hasil tahap dilaporkan.

## Urutan Eksekusi

| Tahap | Fokus | Prompt |
|---|---|---|
| 1 | Audit repository, fondasi, database, tenant, autentikasi | `RUN_01_FOUNDATION.md` |
| 2 | Pencarian “Bubur Fay” dan verifikasi kandidat cabang | `RUN_02_BRANCH_DISCOVERY.md` |
| 3 | OAuth Google Business Profile dan rekonsiliasi lokasi | `RUN_03_GOOGLE_CONNECTION.md` |
| 4 | Sinkronisasi review, impor, Pub/Sub, deduplikasi | `RUN_04_REVIEW_INGESTION.md` |
| 5 | Analisis AI dan dashboard intelligence | `RUN_05_ANALYSIS_AND_DASHBOARD.md` |
| 6 | Draft balasan, approval, publikasi, moderasi | `RUN_06_RAPID_RESPONSE.md` |
| 7 | Issue tracking, laporan, keamanan, final acceptance | `RUN_07_OPERATIONS_AND_RELEASE.md` |

## Aturan Berhenti

Hermes harus berhenti apabila:

- ada blocker credential/API;
- migration gagal;
- tenant isolation gagal;
- source data tidak dapat diverifikasi;
- acceptance test tahap gagal;
- fitur membutuhkan keputusan owner yang belum tersedia.

Hermes harus memberikan status:

- `completed`;
- `completed_with_limitations`;
- `blocked`;
- `not_ready_for_next_phase`.

## Larangan

Hermes tidak boleh:

- melompati urutan;
- mengaktifkan auto-reply sebelum Tahap 6;
- membuat Pub/Sub sebelum koneksi Google siap;
- menganggap Places candidate sebagai official outlet;
- menyatakan production-ready sebelum Tahap 7 lulus;
- menambah fitur di luar scope.
