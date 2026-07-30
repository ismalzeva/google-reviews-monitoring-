---
name: google-business-profile-connection
version: 1.0.0
type: connector-skill
status: active
---

# HERMES AGENT SKILL — GOOGLE BUSINESS PROFILE CONNECTION

## 1. PURPOSE

Menghubungkan aplikasi dengan akun Google Business Profile milik owner untuk:

- membaca akun yang dapat diakses;
- membaca lokasi resmi;
- membaca review;
- menerima notifikasi;
- membuat atau memperbarui balasan review.

## 2. PREREQUISITES

Sebelum koneksi produksi:

- Google Cloud project tersedia;
- akses Business Profile APIs telah disetujui Google;
- API terkait telah diaktifkan;
- OAuth consent screen telah dikonfigurasi;
- OAuth client tersedia;
- redirect URI sesuai environment;
- user yang login memiliki akses ke Business Profile;
- token disimpan secara aman.

Tidak ada asumsi bahwa mengaktifkan API otomatis memberikan kuota atau approval.

## 3. AUTHORIZATION

Gunakan OAuth 2.0.

Scope utama:

```text
https://www.googleapis.com/auth/business.manage
```

Rules:

- minta scope minimum;
- tampilkan consent secara jelas;
- simpan access token dan refresh token terenkripsi;
- jangan kirim token ke model AI;
- jangan tampilkan token di log;
- dukung disconnect/revoke;
- tandai token expired atau revoked.

## 4. ACCOUNT DISCOVERY

Setelah OAuth:

1. List accounts yang dapat diakses.
2. Simpan account resource name.
3. Tampilkan account name dan account type.
4. Minta owner memilih account bila lebih dari satu.
5. Jangan mengasumsikan account pertama adalah account yang benar.

## 5. OFFICIAL LOCATION RETRIEVAL

Gunakan Business Information API:

```text
accounts.locations.list
```

Rules:

- gunakan read mask;
- lakukan pagination;
- simpan location resource name;
- simpan metadata dan place ID bila tersedia;
- catat direct/indirect access;
- jangan menimpa owner verification record.

## 6. LOCATION DATA MINIMUM

```yaml
gbp_location_id:
gbp_account_id:
resource_name:
store_code:
title:
phone_numbers:
website_uri:
categories:
storefront_address:
latlng:
regular_hours:
open_info:
metadata:
  place_id:
  maps_uri:
connection_status:
access_status:
last_synced_at:
```

## 7. VERIFIED LOCATION REQUIREMENT

Review retrieval harus mengikuti batasan API.

Jika review endpoint menolak karena lokasi belum memenuhi persyaratan atau belum terverifikasi:

- set `review_access_status: unavailable`;
- jangan menebak review;
- jangan memakai public discovery sebagai pengganti permission;
- tampilkan langkah perbaikan kepada admin.

## 8. CONNECTION STATUS

```yaml
not_connected
oauth_in_progress
connected
token_expired
token_revoked
permission_denied
api_access_pending
quota_unavailable
partial_access
disconnected
```

## 9. LOCATION RECONCILIATION

Prioritas match:

1. exact `place_id`;
2. exact official resource mapping yang sudah disimpan;
3. exact address + phone;
4. high-confidence normalized name + geospatial match;
5. human review.

Ambiguous matches wajib approval owner/admin.

## 10. DISCONNECT FLOW

Ketika owner disconnect:

- revoke token bila diminta;
- hentikan sync;
- hentikan Pub/Sub processing untuk account tersebut;
- set reply disabled;
- pertahankan historical data sesuai retention policy;
- catat audit event.

## 11. SECURITY RULES

Dilarang:

- hardcode OAuth secret di client;
- menyimpan refresh token plaintext;
- memasukkan credential dalam prompt;
- memberi role viewer akses melakukan reply;
- memakai token satu tenant untuk tenant lain;
- mencatat full API response yang mengandung data sensitif tanpa redaction.

## 12. HEALTH CHECK

Connection health memeriksa:

```yaml
oauth_token_valid:
api_access_available:
account_accessible:
location_count:
review_endpoint_accessible:
notification_setting_accessible:
last_successful_sync:
last_error:
```

## 13. QUALITY GATE

Koneksi lulus hanya jika:

- OAuth berhasil;
- account dapat diambil;
- minimal satu lokasi dapat dibaca atau sistem menjelaskan dengan benar bahwa account kosong;
- tenant isolation lulus;
- token tersimpan terenkripsi;
- no-secret-in-log test lulus.

## 14. ACCEPTANCE CRITERIA

- Owner dapat login dengan Google.
- Owner dapat memilih account.
- Sistem dapat menampilkan accessible locations.
- Sistem dapat mencocokkan location dengan candidate.
- Sistem dapat menandai location mana yang reply-enabled.
- Disconnect menghentikan tindakan API.
- Credential tidak muncul pada UI, log, AI prompt, atau completion report.
