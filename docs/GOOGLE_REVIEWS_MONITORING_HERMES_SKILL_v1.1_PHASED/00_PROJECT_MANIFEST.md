---
name: project-manifest
version: 1.0.0
project: Google Reviews Monitoring & Intelligence
pilot: Bubur Fay
status: scope-locked
---

# HERMES AGENT SKILL — PROJECT MANIFEST

## 1. PRODUCT DEFINITION

Google Reviews Monitoring & Intelligence adalah aplikasi web yang mengubah Google Reviews menjadi:

- peringatan reputasi;
- insight pengalaman pelanggan;
- temuan operasional;
- draft balasan;
- alur approval;
- issue tracking;
- laporan manajemen.

Pilot pertama adalah **Bubur Fay**.

## 2. CORE USER PROBLEM

Owner bisnis dengan banyak review atau banyak outlet kesulitan:

- membaca seluruh review;
- menemukan keluhan berulang;
- mengetahui outlet yang bermasalah;
- memastikan semua review penting telah dibalas;
- merespons review dengan cepat tetapi tetap aman;
- menghubungkan suara pelanggan dengan tindakan operasional.

## 3. CORE PRODUCT PROMISE

> Owner dapat mengetahui apa masalahnya, terjadi di outlet mana, seberapa sering, seberapa serius, siapa yang harus menangani, dan bagaimana merespons pelanggan.

## 4. PRIMARY USERS

### Owner

Membutuhkan:

- ringkasan seluruh lokasi;
- review prioritas;
- risiko reputasi;
- approval kasus sensitif;
- laporan berkala.

### Supervisor Operasional

Membutuhkan:

- masalah berdasarkan outlet;
- rekomendasi pemeriksaan;
- penanggung jawab;
- status penyelesaian.

### Customer Service / Review Responder

Membutuhkan:

- antrean review;
- draft balasan;
- approval status;
- status publikasi dan moderasi.

### Admin

Membutuhkan:

- onboarding bisnis;
- pencarian lokasi;
- verifikasi lokasi;
- koneksi Google;
- konfigurasi policy;
- impor data.

## 5. MVP SCOPE

### Included

- multi-tenant business;
- multi-outlet;
- search-by-brand branch discovery;
- owner verification;
- OAuth Google connection;
- official location reconciliation;
- CSV/XLSX import;
- initial review sync;
- incremental review sync;
- Pub/Sub review notifications;
- AI sentiment and issue analysis;
- response drafting;
- configurable auto-reply safety policy;
- approval workflow;
- reply publication;
- moderation-state tracking;
- issue tracking;
- dashboard;
- reporting;
- role-based access;
- audit log.

### Excluded

Lihat `README_FIRST.md` bagian NON-GOALS.

## 6. PRODUCT PRINCIPLES

### P1 — Ownership Must Be Verified

Nama yang sama atau mirip tidak membuktikan kepemilikan.

### P2 — Official Account Is Primary

Lokasi dari akun Google Business Profile yang diotorisasi menjadi sumber utama untuk tindakan pengelolaan.

### P3 — Human Control for Risk

Semakin tinggi risiko, semakin tinggi kebutuhan approval manusia.

### P4 — Public Reply Is Not Internal Resolution

Balasan kepada pelanggan dan tindakan operasional adalah dua output berbeda.

### P5 — Preserve Original Evidence

Review asli, rating, waktu, dan balasan asli tidak boleh ditimpa oleh hasil AI.

### P6 — AI Must Be Explainable

Setiap analisis menyertakan:

- label;
- ringkasan alasan;
- confidence;
- bukti kutipan pendek dari review;
- rekomendasi.

Hermes tidak boleh menampilkan chain-of-thought.

### P7 — Idempotent Processing

Review atau event yang sama tidak boleh menghasilkan record, balasan, atau isu ganda.

### P8 — Safe Failure

Ketika API, permission, token, atau quality gate gagal:

- jangan menebak;
- jangan memublikasikan balasan;
- simpan status gagal;
- tampilkan tindakan perbaikan.

## 7. PILOT SUCCESS CRITERIA

Pilot Bubur Fay berhasil apabila:

1. Owner menemukan kandidat cabang dengan mengetik nama brand.
2. Owner dapat memilih cabang yang benar.
3. Sistem dapat mencocokkan lokasi publik dan lokasi akun resmi.
4. Review lama dapat masuk ke sistem.
5. Review baru dapat terdeteksi.
6. Review dengan teks dianalisis.
7. Rating-only review tetap dihitung dalam statistik.
8. Review aman memperoleh draft yang relevan.
9. Review negatif tidak dipublikasikan otomatis.
10. Review kritis menciptakan alert dan issue.
11. Owner dapat melihat perbandingan outlet.
12. Tindakan internal dapat dilacak sampai selesai.
