---
name: google-reviews-monitoring-hermes
version: 1.0.0
language: id-ID
type: hermes-skill-package
status: production-ready-draft
project: Google Reviews Monitoring & Intelligence
pilot: Bubur Fay
---

# README FIRST — GOOGLE REVIEWS MONITORING & INTELLIGENCE

## 1. TUJUAN PAKET

Paket skill ini menjadi **single source of truth** bagi Hermes Agent untuk membangun, menjalankan, menguji, dan mengevaluasi aplikasi Google Reviews Monitoring & Intelligence.

Produk membantu owner:

1. Mengetik nama brand, misalnya `Bubur Fay`.
2. Menemukan kandidat lokasi/cabang yang tampil di Google Maps.
3. Memverifikasi lokasi mana yang benar-benar merupakan cabang resmi.
4. Menghubungkan akun Google Business Profile.
5. Menarik lokasi resmi dan review dari akun yang diberi izin.
6. Memantau review baru atau review yang diperbarui.
7. Menganalisis sentimen, topik, masalah, urgensi, dan risiko reputasi.
8. Membuat draft balasan cepat.
9. Mengirim balasan otomatis hanya pada kasus yang aman.
10. Meminta persetujuan manusia untuk kasus yang berisiko.
11. Mengescalasi kasus kritis kepada owner atau supervisor.
12. Menyimpan tindak lanjut dan laporan operasional.

## 2. ATURAN UTAMA HERMES

Hermes WAJIB:

- membaca file ini terlebih dahulu;
- mengikuti urutan dan routing file;
- tidak menambah fitur di luar scope v1.0 tanpa instruksi eksplisit;
- tidak menganggap hasil pencarian publik sebagai bukti kepemilikan cabang;
- tidak memublikasikan balasan berisiko tanpa approval;
- tidak mengubah atau menyembunyikan review asli;
- tidak menyimpan credential Google dalam log, prompt, atau output;
- selalu memisahkan fakta review, analisis AI, draft balasan, dan tindakan internal;
- menghentikan proses pada quality gate yang gagal;
- menghasilkan completion report setelah implementasi atau pengujian.

## 3. URUTAN BACA

1. `README_FIRST.md`
2. `00_PROJECT_MANIFEST.md`
3. `01_CORE_OPERATING_MODEL.md`
4. Modul yang sesuai dengan tugas.
5. `08_DATA_CONTRACTS_AND_OUTPUT_SCHEMA.md`
6. `09_QUALITY_GATES_ACCEPTANCE_TESTS.md`
7. `10_COMPLETION_REPORT_TEMPLATE.md`

## 4. ROUTER TUGAS

| Tugas | File wajib |
|---|---|
| Memahami produk dan scope | `00_PROJECT_MANIFEST.md` |
| Menentukan agent dan alur kerja | `01_CORE_OPERATING_MODEL.md` |
| Mencari semua titik berdasarkan nama brand | `02_BRANCH_DISCOVERY_AND_VERIFICATION.md` |
| Menghubungkan akun Google Business Profile | `03_GOOGLE_BUSINESS_PROFILE_CONNECTION.md` |
| Mengambil dan memonitor review | `04_REVIEW_INGESTION_AND_REALTIME_MONITORING.md` |
| Menganalisis review | `05_AI_REVIEW_ANALYSIS_RULES.md` |
| Membuat dan memublikasikan balasan | `06_RAPID_RESPONSE_AGENT.md` |
| Membuat kasus dan tindak lanjut internal | `07_ISSUE_ESCALATION_AND_OPERATIONS.md` |
| Membuat database/API/output | `08_DATA_CONTRACTS_AND_OUTPUT_SCHEMA.md` |
| Menguji implementasi | `09_QUALITY_GATES_ACCEPTANCE_TESTS.md` |
| Melaporkan hasil kerja | `10_COMPLETION_REPORT_TEMPLATE.md` |

## 5. SUMBER DATA YANG DIIzINKAN

### A. Public Location Discovery

Gunakan Google Places Text Search untuk mencari kandidat tempat berdasarkan teks seperti:

```text
Bubur Fay
Bubur Fay Depok
Bubur Fay Bekasi
```

Hasil discovery hanya berstatus **kandidat**, bukan lokasi resmi.

### B. Official Business Locations

Gunakan akun Google Business Profile yang diotorisasi owner untuk memperoleh daftar lokasi yang dapat diakses.

Daftar lokasi dari akun resmi menjadi sumber kebenaran utama mengenai lokasi yang dapat dikelola aplikasi.

### C. Review Management

Gunakan Google Business Profile review endpoints untuk:

- mengambil review;
- mengambil review lintas lokasi;
- membaca balasan;
- membuat atau memperbarui balasan;
- menghapus balasan bila diperintahkan pengguna berwenang.

### D. Real-Time Notification

Gunakan My Business Notifications API dan Google Cloud Pub/Sub untuk event:

- `NEW_REVIEW`;
- `UPDATED_REVIEW`.

### E. Manual/Fallback Import

MVP boleh menerima file CSV/XLSX hasil Outscraper untuk:

- initial historical import;
- pengujian;
- fallback ketika akses Business Profile API belum tersedia.

Data impor manual tidak memberikan hak untuk memublikasikan balasan ke Google.

## 6. SOURCE OF TRUTH

Urutan prioritas sumber:

1. Review dan lokasi dari akun Google Business Profile yang diotorisasi.
2. Data review asli yang tersimpan di database.
3. Data hasil impor Outscraper.
4. Hasil pencarian publik Google Places.
5. Analisis AI.

AI tidak pernah menjadi sumber fakta utama.

## 7. STATUS UTAMA

### Status Kandidat Lokasi

- `discovered`
- `owner_confirmed`
- `owner_rejected`
- `old_or_closed`
- `possible_duplicate`
- `uncertain`
- `matched_to_gbp`
- `unmatched_to_gbp`

### Status Review

- `new`
- `analyzed`
- `draft_ready`
- `awaiting_approval`
- `approved`
- `published`
- `reply_pending_moderation`
- `reply_approved`
- `reply_rejected`
- `escalated`
- `resolved`

### Status Isu

- `new`
- `under_review`
- `assigned`
- `in_progress`
- `resolved`
- `closed`
- `reopened`

## 8. NON-GOALS V1.0

Hermes tidak boleh menambahkan secara otomatis:

- social listening umum;
- integrasi Instagram, TikTok, GoFood, GrabFood, atau ShopeeFood;
- prediksi penjualan;
- deteksi review palsu tingkat lanjut;
- native mobile app;
- sistem pembayaran SaaS;
- publikasi balasan negatif tanpa persetujuan;
- perubahan data Google Business Profile selain balasan review;
- klaim kepemilikan lokasi secara otomatis;
- penghapusan review pelanggan;
- pengiriman pesan langsung kepada reviewer.

## 9. COMPLETION DEFINITION

Paket dianggap diterapkan dengan benar apabila:

- owner dapat mengetik `Bubur Fay`;
- sistem menampilkan kandidat lokasi;
- owner dapat memverifikasi kandidat;
- akun Google dapat dihubungkan melalui OAuth;
- lokasi resmi dapat direkonsiliasi dengan kandidat;
- review dapat ditarik dan dianalisis;
- review baru dapat diterima melalui event atau sinkronisasi;
- draft balasan dapat dibuat;
- positive-safe review dapat diproses sesuai policy;
- review negatif/sensitif menunggu approval;
- review kritis dieskalasi;
- status moderasi balasan dapat dipantau;
- seluruh perubahan tercatat dalam audit log;
- acceptance test lulus;
- completion report dibuat.

## 10. CARA EKSEKUSI BERTAHAP

Semua file boleh diunggah sekaligus sebagai knowledge/skill reference.

Jangan meminta Hermes mengimplementasikan seluruh produk dalam satu prompt.
Setelah upload, baca dan jalankan `EXECUTION_SEQUENCE.md`, kemudian gunakan
`RUN_01_FOUNDATION.md` sampai `RUN_07_OPERATIONS_AND_RELEASE.md` secara berurutan.
