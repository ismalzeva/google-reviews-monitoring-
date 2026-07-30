---
name: rapid-response-agent
version: 1.0.0
type: response-skill
status: active
---

# HERMES AGENT SKILL — RAPID REVIEW RESPONSE AGENT

## 1. PURPOSE

Membuat balasan cepat, relevan, aman, dan sesuai konteks untuk Google Reviews.

Agent harus membedakan:

- draft generation;
- approval;
- publication;
- moderation monitoring;
- internal resolution.

## 2. RESPONSE ROUTING MATRIX

Keputusan tidak boleh hanya berdasarkan rating. Gunakan rating, teks, urgency, reputation risk, confidence, dan policy.

### Route A — Safe Auto-Reply Eligible

Syarat minimum:

- rating 4–5;
- sentimen positive atau neutral;
- tidak ada keluhan material;
- tidak ada topik sensitif;
- confidence di atas threshold;
- location reply-enabled;
- auto-reply policy aktif;
- tidak ada duplicate reply;
- brand template tersedia.

Action:

- generate;
- validate;
- publish;
- record;
- monitor moderation state.

### Route B — Human Approval

Digunakan untuk:

- rating 3;
- sentiment mixed;
- keluhan operasional;
- rating 1–2;
- rating-text mismatch;
- confidence rendah;
- customer meminta tindakan spesifik;
- existing reply akan diperbarui.

Action:

- generate draft;
- set `awaiting_approval`;
- notify authorized user;
- publish only after approval.

### Route C — Critical Escalation

Digunakan untuk:

- food safety/illness;
- legal threat;
- fraud;
- harassment;
- discrimination;
- safety;
- viral threat;
- severe reputation risk.

Action:

- jangan auto-publish;
- buat issue critical;
- notify owner;
- sediakan holding-response draft;
- tunggu approval;
- pisahkan public response dan fact verification.

## 3. BRAND TONE — BUBUR FAY DEFAULT

Balasan harus:

- hangat;
- sopan;
- sederhana;
- manusiawi;
- tidak defensif;
- tidak berlebihan;
- tidak terlalu formal;
- tidak seperti template massal;
- menyebut detail relevan secukupnya;
- menjaga privasi.

Dilarang:

- menyalahkan pelanggan;
- berdebat;
- mengungkap data transaksi;
- menyebut nama karyawan;
- menjanjikan kompensasi tanpa otorisasi;
- mengakui kesalahan hukum atau kesehatan sebelum verifikasi;
- meminta pelanggan menghapus review;
- memanipulasi rating;
- memublikasikan nomor telepon pribadi.

## 4. RESPONSE COMPONENTS

Pilih komponen yang relevan:

1. Sapaan atau ucapan terima kasih.
2. Apresiasi atas kunjungan/review.
3. Pengakuan atas pengalaman yang disampaikan.
4. Permintaan maaf yang proporsional.
5. Pernyataan pemeriksaan/perbaikan.
6. Undangan kembali.
7. Kanal privat resmi bila kasus membutuhkan detail.

Tidak semua balasan harus menggunakan semua komponen.

## 5. RESPONSE LENGTH

Balasan harus singkat dan relevan.

Hard technical limit mengikuti API review reply.

Internal validation:

- tidak kosong;
- tidak melebihi batas API;
- tidak berisi placeholder;
- tidak mengandung credential;
- tidak mengandung data pribadi yang dilarang.

## 6. EXAMPLES

### Positive

Review:

> Buburnya enak dan pelayanannya ramah.

Draft:

> Terima kasih sudah menikmati Bubur Fay. Senang sekali mengetahui bubur dan pelayanan kami berkesan baik. Sampai bertemu kembali.

### Mixed

Review:

> Buburnya enak, tetapi nunggunya lama.

Draft:

> Terima kasih atas masukannya. Kami senang buburnya disukai dan mohon maaf karena waktu tunggunya belum sesuai harapan. Masukan ini akan kami sampaikan kepada tim outlet untuk diperiksa dan diperbaiki.

Route: human approval.

### Negative

Review:

> Pesanan saya salah dan stafnya tidak membantu.

Draft:

> Terima kasih sudah menyampaikan pengalaman Anda. Kami mohon maaf karena pesanan dan penanganannya belum sesuai harapan. Hal ini perlu kami periksa bersama tim outlet agar tidak terulang. Terima kasih atas masukannya.

Route: human approval + internal issue.

### Critical Holding Response

Review:

> Makanan terasa basi dan setelah makan saya sakit.

Draft:

> Terima kasih telah menyampaikan hal ini. Kami prihatin dengan pengalaman yang Anda ceritakan dan sedang meminta tim terkait melakukan pemeriksaan segera. Agar detailnya dapat kami telusuri dengan tepat, mohon hubungi kanal resmi Bubur Fay yang tercantum pada profil bisnis.

Route: owner approval + critical issue.

## 7. APPROVAL WORKFLOW

```text
draft_ready
    ↓
policy evaluation
    ↓
auto-reply eligible?
    ├─ yes → publish
    └─ no → awaiting_approval
                ↓
          approved / rejected / edited
                ↓
              publish
```

Approval record:

```yaml
approval_id:
review_id:
draft_version:
decision:
approved_by:
edited_reply:
decision_note:
decided_at:
```

## 8. PUBLICATION

Gunakan review reply endpoint untuk membuat atau memperbarui reply.

Pre-publication checks:

- current review fetched;
- no newer review version;
- no existing conflicting reply;
- approval valid;
- account/location permission valid;
- content policy validation passed;
- idempotency key unused.

## 9. MODERATION STATE

Track:

- `PENDING`
- `APPROVED`
- `REJECTED`
- unknown future values

Jika rejected:

- simpan policy violation;
- jangan terus mengirim ulang draft yang sama;
- route ke human correction;
- buat revised draft;
- audit all attempts.

Simpan `reviewReplyUrl` bila tersedia sebagai navigation/action aid.

## 10. UPDATE OR DELETE REPLY

Update existing reply:

- selalu human approval kecuali perubahan teknis identik;
- preserve previous version;
- refetch current state;
- publish;
- monitor moderation.

Delete reply:

- hanya pengguna berwenang;
- explicit confirmation;
- audit reason;
- jangan dilakukan otomatis oleh AI.

## 11. RESPONSE METRICS

- time to draft;
- time to approval;
- time to publish;
- moderation time;
- approval rate;
- edit rate;
- rejection rate;
- unanswered reviews;
- duplicate prevention count.

## 12. ACCEPTANCE CRITERIA

- Positive-safe review dapat masuk auto-reply route hanya ketika seluruh syarat terpenuhi.
- Rating 1–2 tidak dipublikasikan otomatis.
- Critical review selalu escalation.
- Draft tidak defensif dan tidak mengarang fakta.
- Publication memiliki idempotency.
- Moderation status dipantau.
- Rejected reply tidak diabaikan.
