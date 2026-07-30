# RUN_09 — Owner Checklist: Google Live Activation

Dokumen ini berisi semua yang harus disiapkan owner (Ismal / Bubur Fay)
sebelum GRM bisa terhubung ke Google Business Profile secara live.

---

## ✅ 1. Google Cloud Project

| Item | Status | Notes |
|------|--------|-------|
| Google Cloud Project aktif | ⬜ | Buat di https://console.cloud.google.com |
| Billing enabled | ⬜ | Business Profile API gratis, Pub/Sub bayar per usage |
| Project ID tercatat | ⬜ | Diisi ke `GCP_PROJECT_ID` di .env |
| Business Profile API enabled | ⬜ | API Library → Google Business Profile API → Enable |
| Pub/Sub API enabled | ⬜ | API Library → Cloud Pub/Sub API → Enable |

## ✅ 2. OAuth Consent Screen

| Item | Status | Notes |
|------|--------|-------|
| User Type = External | ⬜ | Karena pilot 1 outlet, bisa Testing dulu |
| App name = "Google Reviews Monitoring" | ⬜ | Atau "Bubur Fay Review Manager" |
| Support email (milik owner) | ⬜ | Email yang bisa dihubungi Google |
| Scopes: `business.manage` | ⬜ | Sensitive scope → perlu verification nanti |
| Test users (email owner Bubur Fay) | ⬜ | Tambahkan email owner sebagai test user |

**Catatan:** Selama status *Testing*, hanya test users yang bisa OAuth.
Untuk production perlu verification (butuh waktu).

## ✅ 3. OAuth Credentials (Client ID & Secret)

| Item | Status | Notes |
|------|--------|-------|
| Application type = Web application | ⬜ | |
| **Client ID** tercatat | ⬜ | Diisi ke `GOOGLE_CLIENT_ID` |
| **Client Secret** tercatat | ⬜ | Diisi ke `GOOGLE_CLIENT_SECRET` |
| Authorized JavaScript origins | ⬜ | `https://grm.centil.id` (domain GRM nanti) |
| **Authorized redirect URIs** | ⬜ | **WAJIB**: `https://grm.centil.id/google/callback` |

## ✅ 4. Redirect URI Produksi

| Item | Status | Notes |
|------|--------|-------|
| Domain GRM sudah pointing ke VPS | ⬜ | Misal: `grm.centil.id → 43.134.112.7` |
| Caddy reverse proxy terpasang | ⬜ | `grm.centil.id → localhost:8083` |
| HTTPS auto-SSL (Caddy) OK | ⬜ | Caddy handle LetsEncrypt otomatis |
| Redirect URI di GCP cocok | ⬜ | Harus sama persis dengan Caddy domain |

## ✅ 5. Akun Google Owner Bubur Fay

| Item | Status | Notes |
|------|--------|-------|
| Email terdaftar sebagai test user | ⬜ | Di OAuth consent screen → Test users |
| Punya akses ke Google Business Profile | ⬜ | Verifikasi di https://business.google.com |
| Punya peran Manager/Owner di GBP | ⬜ | Minimal Manager level |
| Nama bisnis = "Bubur Fay" | ⬜ | Atau nama sesuai GBP |

## ✅ 6. Pub/Sub Setup

| Item | Status | Notes |
|------|--------|-------|
| Pub/Sub Topic dibuat | ⬜ | Nama: `grm-review-events` atau sesuai |
| Pub/Sub Subscription dibuat | ⬜ | Push subscription → `https://grm.centil.id/pubsub-webhook` |
| Service Account Pub/Sub | ⬜ | Untuk push auth (optional tapi recommended) |
| GCP Project ID diisi ke .env | ⬜ | `GCP_PROJECT_ID` |
| Topic name diisi ke .env | ⬜ | `PUBSUB_TOPIC` |
| Subscription name diisi ke .env | ⬜ | `PUBSUB_SUBSCRIPTION` |

## ✅ 7. .env Configuration (Final)

Setelah semua siap, update `.env`:

```
# === Google OAuth ===
GOOGLE_CLIENT_ID=<dari GCP OAuth>
GOOGLE_CLIENT_SECRET=<dari GCP OAuth>
GOOGLE_REDIRECT_URI=https://grm.centil.id/google/callback

# === Pub/Sub ===
GCP_PROJECT_ID=<project-id>
PUBSUB_TOPIC=grm-review-events
PUBSUB_SUBSCRIPTION=grm-review-push-sub
PUBSUB_SERVICE_ACCOUNT_JSON=/home/ubuntu/google-reviews-monitoring/pubsub-sa.json

# === Pilot ===
GRM_PILOT_MODE=true
GRM_PILOT_MAX_OUTLETS=1
# Kosongkan whitelist agar auto-pick outlet pertama

# === Switches (TETAP OFF) ===
GRM_AUTO_REPLY_ENABLED=false
GRM_REPLY_ENABLED_GLOBAL=false
```

## ✅ 8. Rollback Plan

Jika live activation bermasalah:

| Langkah | Caranya |
|---------|---------|
| Kembali ke mock | Kosongkan GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET, restart app |
| Nonaktifkan pilot | Set `GRM_PILOT_MODE=false` |
| Hentikan review sync | Matikan Pub/Sub subscription |
| Hapus data outlet | Hapus dari Outlet table via admin |
| Full rollback | `git checkout ae3a738` (RUN_08) + restart |

---

## Ringkasan Blocker MINIMUM untuk Live

Blocker KRITIS sebelum RUN_09 bisa selesai:
1. **GOOGLE_CLIENT_ID** — harus ada
2. **GOOGLE_CLIENT_SECRET** — harus ada
3. **Domain + Caddy** — GRM perlu HTTPS
4. **Redirect URI** — harus cocok antara GCP + Caddy + .env
5. **Owner Bubur Fay connect** — OAuth flow dari UI GRM

Blocker ini TIDAK bisa di-code. Butuh tindakan owner secara manual.
