# GRM-007: Trial Activation

**Issue Type:** Feature  
**Status:** Designed (Awaiting Implementation)  
**Priority:** P0  
**Estimasi:** M–L  
**Dependency:** GRM-006 (Registration 2-Step Wizard) ✅  
**Sprint:** S1 — Customer Acquisition Layer  

> **Catatan:** GRM-007 menggabungkan Trial Management (backlog asli) + Onboarding Activation (sebagian GRM-008) menjadi satu alur terpadu: Trial Welcome → Tambah Outlet → Sync → WOW Moment. GRM-008 nanti akan fokus pada multi-outlet onboarding dan skip flow.

---

## 1. PRD (Product Requirement Document)

### 1.1 Problem Statement

Setelah GRM-006, user baru langsung masuk `/dashboard/` — halaman kosong tanpa outlet, tanpa review, tanpa AI Advisor. User tidak tahu:
- Bahwa dia sedang dalam masa trial 14 hari
- Apa yang harus dilakukan pertama kali
- Bagaimana cara menambahkan outlet
- Kapan dia akan melihat value dari GRM

Akibatnya: **drop-off tinggi**, user tidak mencapai WOW Moment, dan trial hangus tanpa aktivasi.

### 1.2 User Story

> Sebagai **owner UMKM yang baru mendaftar**, saya ingin **langsung diarahkan menambahkan outlet pertama saya, menyinkronkan review, dan melihat Prioritas Hari Ini untuk bisnis saya sendiri** — supaya saya merasakan value GRM dalam <5 menit, tanpa bantuan sales.

### 1.3 Core Principle

**"Jangan kirim user baru ke dashboard kosong."**

Setiap user baru harus melalui **Trial Activation Flow** sebelum bisa mengakses dashboard penuh. Dashboard tanpa outlet dan sync = useless.

---

## 2. User Flow

```
REGISTER (GRM-006)
    │
    ▼
┌─────────────────────────────┐
│  TRIAL WELCOME              │
│  "Selamat datang, [Nama]!"  │
│                             │
│  Masa trial: 14 hari        │
│  Outlet: 0/1 (max trial)    │
│                             │
│  ┌───────────────────────┐  │
│  │ ○ Tambah outlet       │  │
│  │ ○ Verifikasi outlet   │  │
│  │ ○ Sinkronkan review   │  │
│  │ ○ Buka AI Advisor     │  │
│  └───────────────────────┘  │
│                             │
│  [ Mulai Aktivasi → ]      │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  STEP 1: Tambah Outlet      │
│                             │
│  Cari bisnis Anda:          │
│  [________________] [Cari]  │
│                             │
│  Hasil pencarian:           │
│  ┌───────────────────────┐  │
│  │ ○ Bubur Fay Cab.      │  │
│  │   Caman, Bekasi       │  │
│  │   4.3★ · 238 review   │  │
│  │   [Pilih]             │  │
│  └───────────────────────┘  │
│                             │
│  Trial: maks 1 outlet      │
└─────────────────────────────┘
    │ (pilih outlet)
    ▼
┌─────────────────────────────┐
│  STEP 2: Verifikasi Outlet  │
│                             │
│  Konfirmasi:                │
│  "Bubur Fay — Caman"        │
│  Bekasi, Indonesia          │
│                             │
│  Apakah ini outlet Anda?    │
│  [Ya, Lanjutkan] [Batal]    │
└─────────────────────────────┘
    │ (konfirmasi)
    ▼
┌─────────────────────────────┐
│  STEP 3: Sinkronkan Review  │
│                             │
│  Menyinkronkan review...    │
│  ████████░░░░  67%          │
│                             │
│  152/238 review tersimpan   │
│                             │
│  (Setelah selesai otomatis) │
└─────────────────────────────┘
    │ (sync selesai)
    ▼
┌─────────────────────────────┐
│  ✨ WOW MOMENT ✨            │
│                             │
│  Prioritas Hari Ini         │
│  Bubur Fay — Caman          │
│                             │
│  ┌───────────────────────┐  │
│  │ 🔴 Mendesak            │  │
│  │ Pelayanan kurang ramah │  │
│  │ "pelayannya jutek..."  │  │
│  │ ↳ PIC: Crew Outlet     │  │
│  ├───────────────────────┤  │
│  │ 🟡 Sedang              │  │
│  │ Waktu tunggu lama      │  │
│  │ "nuggu 45 menit..."    │  │
│  │ ↳ PIC: Supervisor      │  │
│  └───────────────────────┘  │
│                             │
│  [ Lihat Dashboard → ]     │
└─────────────────────────────┘
    │
    ▼
  DASHBOARD (dengan data real)
```

### 2.1 Pasca-Aktivasi

Setelah WOW Moment, user bisa langsung ke dashboard dengan data real. Di dashboard tetap ada:

- **Trial Banner** di atas: "Trial · 12 hari tersisa · 1 outlet" (selama masa trial)
- **Status trial** di sidebar: badge "TRIAL" hijau/oranye/merah
- **Nudge** saat trial mau habis

### 2.2 Resume State

Jika user keluar di tengah activation flow (tutup browser, timeout, dll), saat login kembali:
- Cek apakah activation sudah selesai (`business.setup_complete = True`)
- Jika belum: redirect ke step terakhir yang belum selesai
- Progres disimpan di `business.setup_progress` (JSON field melacak step mana yang sudah done)

---

## 3. Wireframe (Mobile-First)

### 3.1 Mobile Viewport (375×812)

```
┌─────────────────────┐
│ [GRM.]              │  ← top bar, sticky
├─────────────────────┤
│                     │
│  Selamat datang,    │
│  Fay Owner! 👋      │
│                     │
│  ┌───────────────┐  │
│  │ 🧪 MASA TRIAL │  │  ← trial status card
│  │ 14 hari       │  │
│  │ Tersisa 14    │  │
│  │               │  │
│  │ Outlet: 0/1   │  │
│  └───────────────┘  │
│                     │
│  Checklist Aktivasi │
│  ┌───────────────┐  │
│  │ ○ Cari &      │  │
│  │   tambah      │  │
│  │   outlet      │  │
│  ├───────────────┤  │
│  │ ○ Verifikasi  │  │
│  ├───────────────┤  │
│  │ ○ Sync review │  │
│  ├───────────────┤  │
│  │ ○ Buka AI     │  │
│  │   Advisor     │  │
│  └───────────────┘  │
│                     │
│  ┌─────────────────┐│
│  │ Mulai Aktivasi →││ ← single CTA
│  └─────────────────┘│
│                     │
│  Atau [Lewati,      │
│  langsung dashboard]│ ← small secondary link
│                     │
└─────────────────────┘
```

### 3.2 Step 1: Tambah Outlet (mobile)

```
┌─────────────────────┐
│ ← Kembali   1/4     │
├─────────────────────┤
│                     │
│  Cari Bisnis Anda   │
│                     │
│  [Cari nama bisnis  │
│   atau alamat...  ] │
│  [     Cari     ]   │
│                     │
│  Hasil:             │
│  ┌───────────────┐  │
│  │ Bubur Fay      │  │
│  │ Jl. Caman Raya │  │
│  │ Bekasi         │  │
│  │ ★4.3 · 238    │  │
│  │ [Pilih]        │  │
│  └───────────────┘  │
│                     │
│  Trial: maks 1      │
│  outlet             │
│                     │
└─────────────────────┘
```

### 3.3 Step 3: Sync Progress (mobile)

```
┌─────────────────────┐
│ ← Kembali   3/4     │
├─────────────────────┤
│                     │
│  Menyinkronkan      │
│  Review...          │
│                     │
│  ████████░░░░ 67%   │
│                     │
│  152/238 review     │
│  tersimpan          │
│                     │
│  ⏳ Mohon tunggu,   │
│  proses 1-2 menit   │
│                     │
└─────────────────────┘
```

### 3.4 WOW Moment (mobile)

```
┌─────────────────────┐
│           ✓ 4/4     │
├─────────────────────┤
│                     │
│  ✨ Selesai!        │
│                     │
│  Prioritas Hari Ini │
│  Bubur Fay — Caman  │
│                     │
│  ┌───────────────┐  │
│  │ 🔴 Mendesak    │  │
│  │ Pelayanan      │  │
│  │ "pelayannya    │  │
│  │  jutek..."     │  │
│  │ PIC: Crew      │  │
│  ├───────────────┤  │
│  │ 🟡 Sedang      │  │
│  │ Waktu tunggu   │  │
│  │ "nunggu 45     │  │
│  │  menit..."     │  │
│  │ PIC: Supervisor│  │
│  └───────────────┘  │
│                     │
│  ┌─────────────────┐│
│  │Lihat Dashboard →││
│  └─────────────────┘│
│                     │
└─────────────────────┘
```

---

## 4. Acceptance Criteria

### 4.1 Trial Lifecycle (AC-1 s/d AC-5)

| AC | Deskripsi | Verifikasi |
|----|-----------|------------|
| AC-1 | Trial dimulai otomatis setelah registrasi | `business.status = 'trialing'`, `trial_ends_at = now + 14 hari` |
| AC-2 | Trial maksimal 1 outlet | UI step Add Outlet menampilkan "0/1", API POST outlet gagal jika sudah ada 1 outlet saat trial |
| AC-3 | Tanpa kartu kredit | Tidak ada field/input CC di flow manapun selama trial |
| AC-4 | Status trial: `active` (hari 1–14), `expiring_soon` (hari 12–14), `expired` (hari 15+) | Property dinamis `trial_status` berdasarkan `trial_ends_at` vs `now()` |
| AC-5 | Trial banner di dashboard selama masa trial | "🧪 Trial · X hari tersisa · 1 outlet" di atas dashboard |

### 4.2 Trial Welcome Page (AC-6 s/d AC-10)

| AC | Deskripsi | Verifikasi |
|----|-----------|------------|
| AC-6 | Setelah register, redirect ke `/trial/welcome`, BUKAN `/dashboard/` | Ubah redirect di `auth.py` Step 2 handler |
| AC-7 | Trial Welcome menampilkan: nama user, sisa hari, outlet count, checklist 4 langkah | Render dari `business.trial_ends_at` dan `business.outlet_count` |
| AC-8 | Checklist 4 langkah: Tambah Outlet, Verifikasi, Sync Review, AI Advisor | Render statis dengan status `pending/completed` dari `business.setup_progress` |
| AC-9 | CTA tunggal: "Mulai Aktivasi →" (arahkan ke step 1) | Satu tombol primary, tidak ada multiple CTA |
| AC-10 | Secondary link "Lewati, langsung dashboard" | Link kecil, bukan tombol. Redirect ke dashboard dengan banner trial |

### 4.3 Activation Steps (AC-11 s/d AC-18)

| AC | Deskripsi | Verifikasi |
|----|-----------|------------|
| AC-11 | Step 1: Cari bisnis — search box + hasil dari discovery service | Gunakan adapter discovery yang sudah ada di `onboarding.py` |
| AC-12 | Step 1: Menampilkan "Trial: maks 1 outlet" | Label di bawah search results |
| AC-13 | Step 2: Verifikasi — konfirmasi outlet yang dipilih | Halaman konfirmasi dengan detail outlet, tombol "Ya, Lanjutkan" / "Batal" |
| AC-14 | Step 3: Sync review — progress bar real-time | Polling endpoint `/api/sync/progress/<task_id>` setiap 2 detik |
| AC-15 | Step 4: WOW Moment — AI Advisor menampilkan Prioritas Hari Ini | Panggil `ai_advisor.generate()` dengan outlet yang baru disync |
| AC-16 | Progress indicator langkah X/4 di setiap step | Mirip GRM-006 step indicator |
| AC-17 | Back button di setiap step (kecuali WOW Moment) | Kembali ke step sebelumnya, data pre-filled |
| AC-18 | Setelah WOW Moment, user bisa "Lihat Dashboard →" | Redirect ke dashboard, kini ada data real. Banner trial tetap tampil |

### 4.4 Resume & Edge States (AC-19 s/d AC-23)

| AC | Deskripsi | Verifikasi |
|----|-----------|------------|
| AC-19 | Resume: user yang sudah login dan `setup_complete=False` di-redirect ke step terakhir yang belum selesai | Middleware / `before_request` di blueprint dashboard |
| AC-20 | Resume: jika user sudah punya outlet tapi belum sync → redirect ke Step 3 | Baca `business.setup_progress` JSON |
| AC-21 | Empty state: search tidak menghasilkan apa-apa → tampilkan "Tidak ditemukan. Coba nama lain." | Sama seperti existing discovery empty state |
| AC-22 | Loading state: spinner/loader saat discovery dan sync | Indikator visual; tidak ada infinite spinner |
| AC-23 | Error state: jika sync gagal → tampilkan pesan jelas + tombol "Coba Lagi" | Tangkap exception dari `sync_service`, jangan tampilkan stack trace |

### 4.5 Tracking Events (AC-24 s/d AC-26)

| AC | Deskripsi | Verifikasi |
|----|-----------|------------|
| AC-24 | Event `trial_started` difire saat pertama kali masuk Trial Welcome | Log di `audit_logs` table atau analytics logger |
| AC-25 | Event `outlet_added`, `first_sync_started`, `first_sync_completed`, `wow_moment_reached`, `trial_expired` difire sesuai milestone | Masing-masing event dicatat dengan timestamp + tenant_id |
| AC-26 | Tracking bersifat non-blocking (fire-and-forget) | Tidak mengganggu user flow jika logger gagal |

### 4.6 Non-Goals (AC-NG)

| AC-NG | Tidak Dikerjakan |
|-------|------------------|
| AC-NG-1 | Billing page / payment gateway |
| AC-NG-2 | Subscription plan selection / upgrade |
| AC-NG-3 | Multi-outlet onboarding (>1 outlet saat trial) |
| AC-NG-4 | Email marketing / trial reminder email |
| AC-NG-5 | Referral program |
| AC-NG-6 | Retention nudge / win-back campaign |
| AC-NG-7 | Admin panel untuk extend trial manual |
| AC-NG-8 | Dashboard lock setelah trial expired (akan di GRM-009) |

### 4.7 Mobile-First (AC-27 s/d AC-28)

| AC | Deskripsi |
|----|-----------|
| AC-27 | Semua halaman trial activation harus mobile-first (375px viewport) |
| AC-28 | Tidak menggunakan horizontal scroll di mobile; semua konten vertikal stack |

---

## 5. Technical Notes

### 5.1 Model Changes

```python
# Business — field baru
setup_complete: bool = False         # True setelah WOW Moment tercapai
setup_progress: JSON (nullable)      # {"step1": "done", "step2": "done", "step3": "in_progress", "step4": "pending"}
setup_started_at: datetime (nullable)
wow_moment_reached_at: datetime (nullable)

# Business — property dinamis (bukan kolom DB)
@property
def trial_status(self) -> str:
    if self.status != 'trialing':
        return self.status
    days_left = (self.trial_ends_at - now).days
    if days_left <= 0:
        return 'expired'
    if days_left <= 3:
        return 'expiring_soon'
    return 'active'

@property
def trial_days_left(self) -> int:
    return max(0, (self.trial_ends_at - now).days)

@property
def outlet_count(self) -> int:
    return Outlet.query.filter_by(
        tenant_id=self.tenant_id, business_id=self.id, monitor_enabled=True
    ).count()
```

### 5.2 New Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/trial/welcome` | GET | Trial Welcome page |
| `/trial/activate` | GET | Activation flow entry → redirect ke step saat ini |
| `/trial/activate/step1` | GET | Step 1 — Tambah Outlet |
| `/trial/activate/step1/search` | POST | Search outlet via discovery adapter |
| `/trial/activate/step1/select` | POST | Pilih outlet dari hasil search |
| `/trial/activate/step2` | GET | Step 2 — Verifikasi Outlet |
| `/trial/activate/step2/confirm` | POST | Konfirmasi outlet → simpan ke DB |
| `/trial/activate/step3` | GET | Step 3 — Sync Review |
| `/trial/activate/step3/start` | POST | Mulai sync (return task_id) |
| `/trial/activate/step3/progress/<task_id>` | GET | Poll progress sync (JSON) |
| `/trial/activate/step4` | GET | Step 4 — WOW Moment |
| `/api/trial/status` | GET | JSON: `{days_left, status, outlet_count, setup_complete}` |

### 5.3 Redirect Middleware

```python
# Di app/__init__.py atau sebagai before_request di dashboard blueprint
# Jika user sudah login, business.status == 'trialing', dan setup_complete == False:
#   → redirect ke trial_welcome atau step terakhir yang belum selesai

@bp.before_request
def _redirect_trialing_user():
    if current_user.is_authenticated:
        biz = current_user.business
        if biz and biz.status == 'trialing' and not biz.setup_complete:
            # Cek apakah request sudah ke trial route → jangan infinite redirect
            if not request.path.startswith('/trial/'):
                return redirect(url_for('trial.welcome'))
```

### 5.4 Sync Progress (In-Memory)

```python
# Reuse atau extend _SYNC_PROGRESS dari onboarding.py
# Format: {task_id: {status, total, synced, percent, error}}

_SYNC_PROGRESS = {}  # shared antara trial dan onboarding
```

### 5.5 Tenant Isolation

Semua query harus difilter dengan `tenant_id` + `business_id` milik `current_user`. Tidak boleh ada trial user yang bisa mengakses data bisnis lain.

### 5.6 Template Files Baru

```
app/templates/trial/
├── welcome.html      # Trial Welcome page
├── activate.html     # Container untuk activation flow
├── _step1_search.html    # Step 1 partial
├── _step2_verify.html    # Step 2 partial
├── _step3_sync.html      # Step 3 partial
└── _step4_wow.html       # Step 4 partial
```

### 5.7 Design System

Mengikuti GRM Design System yang sudah ada:
- Warna primary: `#FF7A00` (orange)
- Background: `#0B0B0B` (dark), surface: `#15171C`
- Font: Inter
- Radius card: 12px
- Radius button: 8px

---

## 6. Test Plan

### 6.1 Gate Tests (`tests/gate_ab_trial.py`)

| Test | Deskripsi |
|------|-----------|
| `test_trial_started_on_register` | Verifikasi `trial_ends_at` = `created_at + 14 days` setelah register |
| `test_trial_welcome_redirect` | User baru setelah register → redirect ke `/trial/welcome` |
| `test_trial_welcome_content` | Halaman welcome menampilkan nama, sisa hari, checklist |
| `test_trial_status_active` | Hari 1–11 → `trial_status = 'active'` |
| `test_trial_status_expiring_soon` | Hari 12–14 → `trial_status = 'expiring_soon'` |
| `test_trial_status_expired` | Hari 15+ → `trial_status = 'expired'` |
| `test_trial_outlet_limit` | POST outlet ke-2 saat trial → 403 |
| `test_skip_to_dashboard` | Link "Lewati" → redirect dashboard + banner trial |
| `test_setup_complete_flag` | Setelah WOW Moment → `setup_complete = True` |
| `test_resume_to_last_step` | User keluar di step 2 → login lagi → redirect step 2 |
| `test_already_activated_no_redirect` | `setup_complete=True` → tidak redirect ke trial |
| `test_wow_moment_has_advisor` | Step 4 menampilkan AI Advisor dengan data outlet user |
| `test_tracking_events` | Verifikasi event `trial_started`, `wow_moment_reached` tercatat |

### 6.2 Regression

- `gate_b.py` — Dashboard baseline (dashboard tetap bisa diakses user non-trial)
- `gate_y.py` — Konsistensi data
- `gate_aa_registration.py` — Registration flow tidak broken
- Existing `tests/gate_*.py` — semua yang sudah ada

---

## 7. Definition of Done

- [ ] Semua AC-1 s/d AC-28 lulus
- [ ] 13 gate tests baru PASSED
- [ ] Regression semua gate existing PASSED
- [ ] Mobile-first: tampilan 375px tidak horizontal scroll
- [ ] Semua edge state (empty, loading, error, retry, resume) tertangani
- [ ] Tracking events tercatat di `audit_logs`
- [ ] Tenant isolation terverifikasi
- [ ] Commit terpisah per sub-task, message format `feat: GRM-007 — ...`
- [ ] Backlog status → Done
- [ ] Laporan final terkirim

---

## 8. Implementation Notes

1. **JANGAN ubah GRM-006** — auth.py redirect hanya ditambah `setup_complete` check, bukan rewrite.
2. **JANGAN mulai Billing/Payment/Subscription** — trial berakhir = dashboard tetap bisa dibuka (lock di GRM-009).
3. **Reuse discovery adapter** dari `onboarding.py` — jangan buat search dari nol.
4. **Sync service** sudah ada di `sync_service.py` — panggil via API, tracking progress in-memory.
5. **AI Advisor** sudah ada di `ai_advisor.py` — panggil dengan tenant_id + business_id after sync.
6. **Middleware redirect** perlu hati-hati — jangan infinite loop, jangan redirect static assets.
