# GRM-006: Public Registration (2-Step Wizard)

**Issue Type:** Feature  
**Status:** Designed (Awaiting Implementation)  
**Priority:** P0  
**Estimasi:** M  
**Dependency:** GRM-004 (CTA dari Preview → Register)  
**Sprint:** S1 — Customer Acquisition Layer  

---

## 1. PRD (Product Requirement Document)

### 1.1 Problem Statement

Saat ini visitor yang sudah melihat preview analisis bisnisnya tidak bisa langsung mendaftar. Registration flow existing (`/auth/register`) adalah single-form legacy yang:
- Redirect ke `/?register=success` tanpa auto-login
- Tidak ada step wizard
- Tidak meminta `business_name`, `brand_name`, `city` di form terpisah
- Tidak ada tracking event `registration_completed`
- Template masih melempar `data is undefined` error (pre-existing bug dari auth.py L34)

**GRM-006 mengganti seluruh registration flow dengan 2-step wizard baru.**

### 1.2 User Story

> Sebagai **owner UMKM**, saya ingin mendaftar GRM dalam **2 langkah** tanpa kartu kredit dan **langsung masuk dashboard trial** — supaya saya bisa segera melihat analisis review bisnis saya.

### 1.3 Wireframe (dari S1 Design)

```
┌────────────────────────────────────────┐
│ [GRM.]                 [Login]         │
│                                        │
│  [Step indicator: ●○○○  1/2]           │
│                                        │
│  ┌─ STEP 1: Buat Akun ───────────────┐│
│  │ Email        [________________]    ││
│  │ Password     [________________]    ││
│  │ Nama Anda    [________________]    ││
│  │                                    ││
│  │ [✓] Password minimal 8 karakter    ││
│  │                                    ││
│  │ [         Lanjut →       ]        ││
│  └────────────────────────────────────┘│
│                                        │
│  ──────────────────────────────────    │
│                                        │
│  ┌─ STEP 2: Bisnis Anda ─────────────┐│
│  │ Nama Bisnis  [________________]    ││
│  │ Brand        [________________]    ││
│  │ Kota         [________________]    ││
│  │                                    ││
│  │ ✅ Tanpa kartu kredit              ││
│  │ ✅ 14 hari trial gratis            ││
│  │ ✅ Tanpa verifikasi email          ││
│  │                                    ││
│  │ [  ← Kembali  ]  [Mulai Coba Gratis→]││
│  └────────────────────────────────────┘│
│                                        │
└────────────────────────────────────────┘
```

### 1.4 Flow Diagram

```
/preview (CTA "Buka Prioritas Perbaikan")
    │
    ▼
/register
    │
    ├─ Step 1: email + password + display_name
    │     │ [client-side validation]
    │     │ [POST /auth/register — step=1]
    │     ▼
    ├─ Step 2: business_name + brand_name + city
    │     │ [POST /auth/register — step=2]
    │     ▼
    ├─ Backend creates:
    │     User (email, password_hash, display_name, role=owner)
    │     Business (name, brand_name, city, tenant_id=auto,
    │               trial_ends_at=now+14days, status=trialing)
    │     └─ audit log: registration_completed
    │
    ├─ Auto-login (flask_login.login_user)
    │
    └─ Redirect: /dashboard (trial mode)
         └─ Banner trial: "14 hari tersisa"
```

### 1.5 Non-Goals (Eksplisit TIDAK Termasuk)

| Item | Kenapa exclude |
|---|---|
| Verifikasi email | Backlog GRM-009 (email sequence) |
| Kartu kredit | Trial gratis, billing di GRM-010+ |
| Google OAuth / SSO | V2, prioritize email/password dulu |
| Password strength meter | Nice-to-have, POL-025 di UI polish |
| Phone number | Tidak diminta, bisa ditambah nanti |
| CAPTCHA | Tidak — rate limit CSRF sudah cukup |
| Multi-tenant di step 2 | Satu user = satu business untuk MVP |

### 1.6 Design Decisions

| Decision | Rationale |
|---|---|
| 2 step, bukan 1 form panjang | Kurangi cognitive load, conversion rate lebih tinggi (acuan: Typeform studies) |
| Step 2 reusable untuk onboarding | Nanti GRM-008 (Onboarding Wizard) akan reuse step 2 sebagai "Step 2: Bisnis Anda" |
| Auto-login setelah register | Hilangkan friction — user tidak perlu login ulang |
| Redirect ke dashboard trial | WOW moment langsung, bukan halaman "sukses" static |
| Tanpa verifikasi email | Speed to value — user bisa langsung pakai. Email sequence nanti di GRM-009 |
| business_name DAN brand_name | business_name = legal name, brand_name = nama display (contoh: "PT Fay Berkah" vs "Bubur Fay") |
| Trial 14 hari dari created_at | Business.trial_ends_at default = now + 14 hari |
| Password ≥8 karakter | Standar minimum, tanpa kompleksitas requirement (uppercase/number/symbol) |

### 1.7 Risk & Mitigation

| Risk | Mitigation |
|---|---|
| Spam registration (bot) | CSRF token + rate limit (10 POST/menit per IP) + audit log |
| Duplicate email | Unique constraint di DB; error message jelas: "Email sudah terdaftar. Login?" |
| Step 1 disubmit tanpa step 2 | Session flag `registration_step1_email` dengan TTL 10 menit; redirect ke step 2 jika flag ada |
| User refresh page mid-step | Step number di-embed di form (hidden input `step`) — server tahu konteks |
| Business name kosong | Boleh kosong (opsional), tapi redirect ke onboarding wizard (GRM-008) untuk isi nanti |

---

## 2. Acceptance Criteria (Checklist)

### Step 1: Akun
- [ ] **GRM-006-01** Halaman `/register` menampilkan **Step 1** pertama kali: Email + Password + Nama Anda
- [ ] **GRM-006-02** Validasi client-side real-time: email format (regex `@`), password ≥8 karakter, nama tidak kosong
- [ ] **GRM-006-03** Error ditampilkan inline di bawah field (bukan flash message), berwarna merah, animasi shake ringan
- [ ] **GRM-006-04** Tombol "Lanjut →" disabled saat validasi gagal, enabled saat semua field valid
- [ ] **GRM-006-05** POST Step 1: server validasi ulang. Jika email sudah terdaftar → error "Email sudah terdaftar. [Login?]" dengan link ke `/auth/login`
- [ ] **GRM-006-06** Step 1 sukses → simpan `registration_step1` di session (email + display_name + password_hash tentatif), tampilkan Step 2

### Step 2: Bisnis
- [ ] **GRM-006-07** Step 2 menampilkan: Nama Bisnis (opsional), Brand, Kota
- [ ] **GRM-006-08** Validasi client-side: brand_name wajib diisi, city wajib diisi (email/dp sudah dari session step 1)
- [ ] **GRM-006-09** Tombol "← Kembali" mengembalikan ke Step 1 dengan data terisi ulang
- [ ] **GRM-006-10** Tombol "Mulai Coba Gratis →" disabled saat validasi gagal

### Submission
- [ ] **GRM-006-11** POST Step 2 → backend: buat User + Business (tenant_id auto-generated) + auto-login
- [ ] **GRM-006-12** Business.trial_ends_at = created_at + 14 hari, Business.status = 'trialing'
- [ ] **GRM-006-13** Setelah auto-login → **redirect ke `/dashboard`** (bukan halaman static sukses)

### Security
- [ ] **GRM-006-14** CSRF protection di kedua step (Flask-WTF atau manual token)
- [ ] **GRM-006-15** Password di-hash sebelum disimpan (werkzeug generate_password_hash)
- [ ] **GRM-006-16** Session `registration_step1` menggunakan signed session (Flask default) — tidak bisa di-tamper client
- [ ] **GRM-006-17** Rate limit: 10 POST /auth/register per IP per menit

### Tracking
- [ ] **GRM-006-18** `registration_completed` event tercatat di audit log (user_id, business_id, ip, timestamp)
- [ ] **GRM-006-19** Event disimpan ke analytics tracker (reuse `_track_event` pattern dari GRM-005)

### Edge Cases
- [ ] **GRM-006-20** User sudah login → akses `/register` → redirect ke `/dashboard`
- [ ] **GRM-006-21** Session `registration_step1` expired (>10 menit) → redirect ke Step 1 dengan pesan "Sesi habis, silakan isi ulang"
- [ ] **GRM-006-22** User refresh Step 2 → data dari session tetap muncul
- [ ] **GRM-006-23** User skip Step 1 URL manipulation (`/register?step=2` tanpa session) → redirect ke Step 1
- [ ] **GRM-006-24** Template tidak melempar `UndefinedError: 'data' is undefined` (pre-existing bug — perbaikan di register.html)
- [ ] **GRM-006-25** Mobile responsive: step indicator di atas, form full-width, tombol full-width

---

## 3. Technical Notes (Implementation Guide)

### 3.1 Route Design

```
GET  /register              → render step 1 (atau step 2 jika session ada)
POST /register  (step=1)    → validasi step 1 → set session → redirect /register?step=2
POST /register  (step=2)    → validasi step 2 → create user+business → login → redirect /dashboard
```

### 3.2 Session Schema

```python
# Flask session (signed cookie)
session['registration_step1'] = {
    'email': str,
    'display_name': str,
    'password_hash': str,      # sudah di-hash di step 1 (hindari plaintext di cookie)
    'created_at': float,        # time.time() — untuk TTL 10 menit
}
```

### 3.3 Database

```sql
-- User (existing table — tambahkan jika belum ada):
--   id, email, password_hash, display_name, role, business_id, created_at

-- Business (existing table — pastikan field ini ada):
--   id, name, brand_name, city, tenant_id, trial_ends_at, status,
--   plan_id, subscription_status, created_at
```

### 3.4 File yang Terpengaruh

| File | Action |
|---|---|
| `app/routes/auth.py` | **Rewrite** `register()` — support 2-step flow |
| `app/templates/auth/register.html` | **Rewrite** — 2-step wizard UI |
| `app/services/audit.py` | Tambah `registration_completed` event type |
| `app/models/entities.py` | Pastikan `Business.trial_ends_at` dan `Business.status` ada |
| `tests/gate_b.py` | Tambah test case registration: step 1, step 2, auto-login, redirect |
| `tests/gate_y.py` | Tambah test case: session expiry, CSRF, duplicate email |

### 3.5 CSS / Style

- Warna: Design System GRM (sidebar `#0B0B0B`, accent orange `#FF7A00`)
- Font: Inter, seperti landing & search
- Step indicator: ○●○ (bullet connected with line, current step filled)
- Form: card putih, border `#d4d4d8`, focus `#FF7A00`, error `#ef4444`
- Transisi antar step: fade 200ms (jangan animasi slide yang berat)

### 3.6 CTA Context

CTA dari `/preview` → register:
```
/preview → "Buka Prioritas Perbaikan →" → /register
/preview → "Coba Gratis 14 Hari — tanpa kartu kredit" → /register
/search → "Daftar Gratis" → /register
/landing → "Coba Gratis →" → /register
```

Semua CTA mengarah ke `/register` yang sama — 2-step wizard.

---

## 4. Test Plan

### 4.1 Unit/Integration (pytest)

| Test ID | Scenario | Expected |
|---|---|---|
| T-GRM006-01 | POST /register step=1 valid | 302 redirect ke /register?step=2, session terisi |
| T-GRM006-02 | POST /register step=1 duplicate email | 200, error "Email sudah terdaftar" |
| T-GRM006-03 | POST /register step=2 valid | User + Business created, auto-login, 302 → /dashboard |
| T-GRM006-04 | POST /register step=2 tanpa session | 302 → /register (step 1) |
| T-GRM006-05 | GET /register dengan session step1 | Menampilkan step 2 (bukan step 1) |
| T-GRM006-06 | Session expired (>10 menit) | Redirect ke step 1, session dihapus |
| T-GRM006-07 | User sudah login → /register | 302 → /dashboard |
| T-GRM006-08 | Rate limit 10 POST/menit | Request ke-11 → 429 |
| T-GRM006-09 | CSRF token invalid/missing | 400 Bad Request |

### 4.2 Browser Manual

| Test | Action |
|---|---|
| Mobile viewport (375px) | Step indicator + form full-width, tombol full-width |
| Desktop (1440px) | Form centered, max-width 480px |
| Tab navigation | Tab dari email → password → nama → Lanjut |
| Refresh Step 2 | Data tetap tampil (dari session) |
| Back button Step 2 | Kembali ke Step 1, data terisi |

---

## 5. Completion Criteria (Definition of Done)

- [ ] Semua 25 Acceptance Criteria terpenuhi
- [ ] Semua 9 test case pytest PASS (gate baru: `gate_aa_registration.py`)
- [ ] Regression: Gate B + Y tetap PASS
- [ ] Screenshot: Step 1, Step 2, Step 2 dengan error, Mobile view
- [ ] Commit dengan message format `feat: GRM-006 — 2-step registration wizard`
- [ ] Backlog status di-update ke Done

---

**Dibuat:** 3 Agustus 2026  
**Referensi:** S1_CUSTOMER_ACQUISITION_LAYER_DESIGN.md §7.3, GRM_BACKLOG.md §GRM-006
