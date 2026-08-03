# GRM Backlog

Version: 1.0
Status: ACTIVE
Purpose: Single source of truth seluruh pekerjaan implementasi GRM SaaS.
Diurutkan berdasarkan **dependency**, bukan kemudahan.

---

## Structure

```
Epic → Feature → Issue
```

Setiap Issue:
- Issue ID (format: GRM-XXX)
- Nama
- Objective (1-2 kalimat)
- Acceptance Criteria (checklist)
- Dependency (Issue ID yang harus selesai lebih dulu)
- Priority (P0/P1/P2/P3)
- Estimasi (S/M/L/XL)
- Status (Todo / In Progress / Done / Blocked)

---

## Glossary

| Prefix | Arti |
|--------|------|
| P0 | Blocker — tidak bisa lanjut tanpa ini |
| P1 | High — critical path ke paid customer |
| P2 | Medium — penting tapi tidak blocking |
| P3 | Low — nice-to-have |

| Size | Estimasi (sesi) |
|------|-----------------|
| S | ≤1 sesi |
| M | 2-3 sesi |
| L | 4-6 sesi |
| XL | 7+ sesi (harus dipecah) |

---

## EPIC 1: Customer Acquisition

**Epic Goal:** Visitor memahami value GRM dalam <3 menit, mencari bisnis sendiri, melihat preview analisis, daftar, dan memulai trial — semuanya self-service tanpa bantuan sales.

**Definition of Done:**
- [ ] Visitor bisa mencari bisnis nyata dari landing tanpa login
- [ ] Visitor bisa melihat preview analisis (data publik) tanpa login
- [ ] Visitor bisa daftar 2 langkah (tanpa kartu kredit) dan langsung masuk trial
- [ ] User baru mencapai WOW Moment (AI Advisor + Prioritas Hari Ini) dalam <3 menit
- [ ] Trial 14 hari berjalan dengan tracking masa aktif & nudge
- [ ] Marketing website (landing + 5 sub-page) live dengan CTA konversi
- [ ] Semua metric funnel tercapture: visitor → search → preview → register → trial

**Success Metrics:**
- [ ] Visitor → Search: ≥40% dari landing visitor
- [ ] Search → Preview: ≥80% dari search
- [ ] Preview → Register: ≥25% dari preview
- [ ] Register → Trial Active: ≥90% dari register
- [ ] Time-to-WOW (landing → AI Advisor): <3 menit
- [ ] Landing load time: <3 detik
- [ ] Search response: <2 detik
- [ ] Preview generation: <3 detik

---

### Feature 1.1: Marketing Website

Halaman publik yang menjual hasil, bukan fitur. Menjawab "ini buat saya?" dalam 10 detik.

#### GRM-001: Landing Page Redesign

- **Objective:** Implementasi ulang landing page sesuai S1 design — hero messaging, social proof, features (hasil), how-it-works (3 langkah), demo embed, pricing, FAQ, footer.
- **Acceptance Criteria:**
  - [ ] Hero section: headline "Tahu masalah terbesar pelanggan Anda dalam 10 detik" + sub-hero + CTA "Coba Gratis"
  - [ ] Search business inline — menerima nama bisnis ATAU Google Maps URL
  - [ ] Placeholder jelas: "Nama bisnis atau link Google Maps, mis. Bubur Fay"
  - [ ] Validasi input kosong — tidak bisa submit tanpa isi
  - [ ] Social proof bar: "X+ bisnis memantau review"
  - [ ] 3 feature cards (hasil, bukan fitur): Prioritas Hari Ini, Perbandingan Cabang, PIC + Tindakan
  - [ ] How It Works: 3 langkah (Tambah Outlet → Sinkron → Tindakan) — visual
  - [ ] Demo Preview embed (contoh/sandbox — bukan data nyata)
  - [ ] Pricing: 3 tier (Pemula/Pro/Premium) dengan CTA per tier
  - [ ] FAQ accordion (5 pertanyaan top)
  - [ ] Footer: kontak, privasi, syarat
  - [ ] Mobile responsive (375px+)
  - [ ] Load time <3 detik
  - [ ] Landing = hub; halaman lain (features/how-it-works/pricing/faq/demo) = sub-page yang bisa di-scroll-to dari landing
- **Issue Success Criteria:**
  - **Business Goal:** Visitor langsung paham GRM = AI yang memberi prioritas tindakan dari review Google — dalam 10 detik pertama
  - **UX Goal:** User bisa: baca headline → paham value → scroll fitur → lihat contoh → cek harga → FAQ — tanpa kebingungan
  - **Conversion Goal:** ≥40% visitor mengklik Search, ≥5% klik CTA "Coba Gratis"
  - **Design Goal:** Terasa seperti SaaS modern premium — bersih, lega, profesional. Tidak seperti template murah.
  - **Performance Goal:** First paint <1.5s, full load <3s, mobile scroll lancar
- **Dependency:** S1 design doc (READY)
- **Priority:** P0
- **Estimasi:** L
- **Status:** Done

#### GRM-002: Static Pages (Features, How It Works, Pricing, FAQ, Demo)

- **Objective:** Melengkapi halaman pendukung dari landing — semua dengan CTA menuju konversi.
- **Acceptance Criteria:**
  - [ ] /features: 4-6 hasil bisnis dengan visual + CTA
  - [ ] /how-it-works: 3 langkah visual + trust badges
  - [ ] /pricing: 3 tier + FAQ pricing + CTA "Coba Gratis"
  - [ ] /faq: 8-10 pertanyaan + jawaban + CTA
  - [ ] /demo: preview analisis bisnis fiktif (data statis) + CTA "Coba untuk bisnis Anda"
  - [ ] Semua halaman mobile responsive
  - [ ] Nav konsisten dengan landing
- **Dependency:** GRM-001
- **Priority:** P1
- **Estimasi:** M
- **Status:** Done

---

### Feature 1.2: Public Search & Preview

Memungkinkan visitor mencari bisnis NYATA sendiri dan melihat preview analisis — TANPA login/daftar. Kunci self-service acquisition.

#### GRM-003: Public Business Search

- **Objective:** Visitor bisa mengetik nama bisnis di landing dan mendapatkan hasil pencarian dari database publik (Google Maps) — tanpa login.
- **Acceptance Criteria:**
  - [ ] Search input di hero landing (nama bisnis + opsional kota)
  - [ ] Autocomplete / suggestions minimal (3 karakter minimum)
  - [ ] Hasil pencarian: nama bisnis, alamat, rating, jumlah review, kota
  - [ ] Multi-result: jika banyak cabang → list semua
  - [ ] Single result: langsung redirect ke preview
  - [ ] Rate limiting: max 10 search/menit per IP (anti abuse)
  - [ ] Tanpa login Google Business — data publik
  - [ ] Error handling: "tidak ditemukan" + saran
- **Dependency:** GRM-001
- **Priority:** P0
- **Estimasi:** L
- **Status:** Done

#### GRM-004: Public Preview Analysis Page

- **Objective:** Visitor bisa melihat preview analisis untuk bisnis yang dipilih — rating, distribusi, top masalah (samar), teaser AI Advisor (terkunci) — tanpa login.
- **Acceptance Criteria:**
  - [ ] Halaman preview: /preview?place_id=xxx
  - [ ] Tampilkan: rating bintang, total review, 5-bar distribusi
  - [ ] Tampilkan: top 3 kategori masalah (judul + jumlah review) — **tanpa** PIC dan tindakan
  - [ ] AI Advisor teaser: 2 contoh masalah terlihat, 1 terkunci blur + "🔒 Buka setelah daftar"
  - [ ] Jika bisnis multi-cabang: selector cabang (dropdown) + perbandingan rating
  - [ ] CTA: "Buka 3 prioritas perbaikan bisnis Anda →" (mengarah ke register)
  - [ ] CTA sekunder: "Coba Gratis 14 Hari — tanpa kartu kredit"
  - [ ] Sumber data: Apify public review (crawler) — cache 24 jam untuk kurangi cost
  - [ ] Preview data NYATA (bukan fiktif) untuk bisnis yang dipilih
  - [ ] Trust badge: "Data dari Google Maps (publik) • tanpa login Google Business"
- **Dependency:** GRM-003
- **Priority:** P0
- **Estimasi:** L
- **Status:** Done

#### GRM-005: Public Preview Analytics Service

- **Objective:** Backend service untuk menghasilkan preview analisis publik dari data review mentah — ringan, cepat (<3 detik), tanpa full AI pipeline.
- **Acceptance Criteria:**
  - [ ] Service: /api/public/preview?place_id=xxx (no auth)
  - [ ] Output JSON: rating, total_review, distribution (5 bar), top_issues (3, tanpa PIC/tindakan), sentiment_summary
  - [ ] Cache di Redis/dict: 24 jam per place_id
  - [ ] Fallback: jika data belum tersedia → trigger async fetch + tampilkan "sedang mengumpulkan data..."
  - [ ] Rate limit: 20 req/menit per IP
  - [ ] Analytics: track preview_started events
- **Dependency:** GRM-003, GRM-004
- **Priority:** P1
- **Estimasi:** M
- **Status:** Done

---

### Feature 1.3: Registration & Trial Onboarding

Mengubah visitor yang sudah lihat preview → daftar → trial aktif dalam <3 menit.

#### GRM-006: Public Registration (2-Step Wizard)

- **Objective:** Registration flow sesuai S1 design — 2 langkah, tanpa kartu kredit, langsung masuk trial.
- **Acceptance Criteria:**
  - [ ] Step 1: Email + Password + Nama → "Lanjut"
  - [ ] Step 2: Nama Bisnis + Brand + Kota → "Mulai Coba Gratis"
  - [ ] Validasi real-time per field (email format, password ≥8 karakter)
  - [ ] Tanpa kartu kredit
  - [ ] Tanpa verifikasi email (opsi tambahkan nanti)
  - [ ] Auto-login setelah register
  - [ ] Redirect ke onboarding wizard
  - [ ] CSRF protection
  - [ ] Track: registration_completed event
- **Dependency:** GRM-004 (CTA dari preview)
- **Priority:** P0
- **Estimasi:** M
- **Status:** Todo

#### GRM-007: Trial Management

- **Objective:** Setiap bisnis baru otomatis masuk trial 14 hari. Tracking masa trial, status, dan nudge.
- **Acceptance Criteria:**
  - [ ] Business.trial_ends_at field (datetime, default: created_at + 14 hari)
  - [ ] Business.status: trialing / active / expired / suspended
  - [ ] Dashboard menampilkan banner trial: "X hari tersisa — Pilih Paket"
  - [ ] Trial expired → dashboard lock (kecuali billing page) + redirect ke pricing
  - [ ] API: GET /api/trial/status → {days_left, status}
  - [ ] Admin bisa extend trial manual
- **Dependency:** GRM-006
- **Priority:** P0
- **Estimasi:** M
- **Status:** Todo

#### GRM-008: Onboarding Wizard

- **Objective:** User baru bisa langsung tambah outlet, sync review, dan lihat AI Advisor — mencapai WOW Moment dalam <3 menit.
- **Acceptance Criteria:**
  - [ ] Step 1: "Cari bisnis Anda" — search box + hasil (auto-discover dari nama brand)
  - [ ] Step 2: Checklist multi-select cabang yang ditemukan
  - [ ] Step 3: "Sinkronkan review" — progress bar + jumlah review masuk
  - [ ] Step 4: "Ini Prioritas Hari Ini" — AI Advisor tampil (WOW Moment)
  - [ ] Skip option untuk user yang ingin langsung ke dashboard
  - [ ] Progress indicator (langkah 1/4, 2/4, dst)
  - [ ] Setelah selesai → redirect ke dashboard dengan AI Advisor sebagai fokus
  - [ ] Track: onboarding_completed, wow_moment_reached events
- **Dependency:** GRM-007
- **Priority:** P1
- **Estimasi:** L
- **Status:** Todo

#### GRM-009: Post-Registration Email (Welcome + Trial Nudge)

- **Objective:** Email otomatis: welcome (hari 0), nudge (hari 3, 7), trial ending (hari 12, 14).
- **Acceptance Criteria:**
  - [ ] Welcome email: "Prioritas pertama Anda →" + link dashboard
  - [ ] Day 3: "Apakah Anda sudah lihat AI Advisor?" + tips
  - [ ] Day 7: "Seminggu review bisnis Anda — ini trennya"
  - [ ] Day 12: "Trial berakhir 2 hari lagi — lanjutkan?"
  - [ ] Day 14: "Trial berakhir hari ini — pilih paket"
  - [ ] Unsubscribe link
  - [ ] HTML + plain text
- **Dependency:** GRM-007
- **Priority:** P2
- **Estimasi:** M
- **Status:** Todo

---

## EPIC 2: Monetization

**Epic Goal:** User trial yang sudah merasakan value → pilih paket → bayar → aktif berlangganan. Semua self-service.

**Definition of Done:**
- [ ] 3 paket harga (Pemula/Pro/Premium) terdefinisi dan tampil di pricing page publik
- [ ] User bisa pilih paket, bayar via payment gateway, dan langsung aktif penuh
- [ ] Billing engine: invoice otomatis, payment status sync, history
- [ ] Trial → paid activation mulus tanpa kehilangan data
- [ ] Auto-renewal berfungsi dengan notifikasi sebelum charge
- [ ] Payment failure handling: retry + dunning + suspend
- [ ] Admin bisa lihat semua subscription, extend trial, change plan manual

**Success Metrics:**
- [ ] Trial → Paid: ≥20% konversi
- [ ] Renewal rate: ≥70% (bulan pertama)
- [ ] Payment success rate: ≥95%
- [ ] Time-to-paid (pilih paket → bayar → aktif): <5 menit
- [ ] Churn rate: <5% per bulan
- [ ] MRR tercapture di admin dashboard

---

### Feature 2.1: Subscription Engine

#### GRM-010: Pricing & Plan Management

- **Objective:** Sistem paket berlangganan: definisi paket, harga, fitur per tier, upgrade/downgrade.
- **Acceptance Criteria:**
  - [ ] 3 paket: Pemula (1 outlet, Rp 99rb/bln), Pro (≤5 outlet, Rp 299rb/bln), Premium (unlimited, Rp 799rb/bln)
  - [ ] Admin panel: CRUD paket (nama, harga, outlet_limit, fitur list)
  - [ ] API: GET /api/plans (public)
  - [ ] Pricing page dinamis dari database
  - [ ] Per-tier feature comparison table
  - [ ] Business.plan_id + Business.subscription_status
- **Dependency:** GRM-007 (trial)
- **Priority:** P0
- **Estimasi:** M
- **Status:** Todo

#### GRM-011: Billing Engine

- **Objective:** Sistem billing: invoice, payment, status langganan, payment history.
- **Acceptance Criteria:**
  - [ ] Invoice generation: otomatis saat user pilih paket
  - [ ] Invoice status: pending / paid / expired / cancelled
  - [ ] Payment history page di dashboard
  - [ ] Business.subscription_status: trialing / active / past_due / cancelled / expired
  - [ ] Business.subscription_ends_at
  - [ ] Auto-renewal flag (default: on)
  - [ ] Invoice reminder: 7 hari, 3 hari, 1 hari sebelum jatuh tempo
  - [ ] Dunning: 1, 3, 7 hari setelah overdue → suspend → cancel
- **Dependency:** GRM-010
- **Priority:** P0
- **Estimasi:** L
- **Status:** Todo

#### GRM-012: Payment Gateway Integration

- **Objective:** Integrasi payment gateway (Midtrans/Xendit) untuk pembayaran self-service.
- **Acceptance Criteria:**
  - [ ] Integrasi payment gateway (pilih: Midtrans atau Xendit)
  - [ ] Metode: transfer bank, QRIS, e-wallet
  - [ ] Webhook handler: payment success / failure / expired
  - [ ] Payment status sync real-time
  - [ ] Test mode + production mode (toggle env)
  - [ ] Handling: payment timeout, retry, double-payment prevention
- **Dependency:** GRM-011
- **Priority:** P0
- **Estimasi:** L
- **Status:** Todo

#### GRM-013: Trial → Paid Activation

- **Objective:** Flow dari trial berakhir → pilih paket → bayar → aktif penuh. Mulus, tidak kehilangan data user.
- **Acceptance Criteria:**
  - [ ] Paywall page setelah trial expired: "Pilih Paket untuk Lanjutkan"
  - [ ] Data user (outlet, review, analisis) tetap utuh selama masa tenggang (7 hari)
  - [ ] Setelah bayar: langsung aktif penuh, tidak ada re-onboarding
  - [ ] Upgrade/downgrade mid-cycle: prorated billing
  - [ ] Cancel subscription: feedback reason + data retention policy
  - [ ] Reactivation: user bisa aktif lagi dalam 30 hari dengan data lama
- **Dependency:** GRM-012
- **Priority:** P0
- **Estimasi:** M
- **Status:** Todo

---

### Feature 2.2: Pricing Page Public

#### GRM-014: Pricing Page Live

- **Objective:** Halaman pricing publik yang transparan, menjual value per tier, dengan CTA "Coba Gratis" untuk trial — bukan langsung bayar.
- **Acceptance Criteria:**
  - [ ] 3 tier cards dengan perbandingan fitur
  - [ ] "Pro" sebagai rekomendasi (highlighted)
  - [ ] FAQ pricing: "Apakah bisa ganti paket?", "Apakah bisa refund?", dll
  - [ ] CTA: "Coba Gratis 14 Hari" (bukan "Beli Sekarang")
  - [ ] Mobile: stacked cards
  - [ ] Enterprise/volume custom quote contact
- **Dependency:** GRM-010
- **Priority:** P1
- **Estimasi:** S
- **Status:** Todo

---

## EPIC 3: Customer Success & Retention

**Epic Goal:** User aktif terus mendapatkan value → perpanjang langganan → rekomendasi ke orang lain.

**Definition of Done:**
- [ ] Weekly email report terkirim otomatis setiap Senin ke semua user paid
- [ ] WhatsApp notification (opt-in) untuk alert penting
- [ ] Auto-renewal berfungsi penuh: charge, retry, notification
- [ ] Referral program live: unique link, tracking, reward (1 bulan gratis)
- [ ] Referral page di dashboard user

**Success Metrics:**
- [ ] Weekly Active Business: ≥60% dari paid user (buka dashboard minimal 1x/minggu)
- [ ] Email open rate: ≥40%
- [ ] Email CTR (ke dashboard): ≥15%
- [ ] Renewal rate: ≥70% (bulanan)
- [ ] Referral rate: ≥10% user paid mengirim referral link
- [ ] Referral → trial conversion: ≥15%
- [ ] Churn reason: tercapture saat cancel

---

### Feature 3.1: Weekly Monitoring & Reports

#### GRM-015: Weekly Email Report

- **Objective:** Setiap minggu, user mendapat email ringkasan: tren rating, masalah baru, perbaikan dari minggu lalu.
- **Acceptance Criteria:**
  - [ ] Email mingguan otomatis (setiap Senin pagi)
  - [ ] Konten: ringkasan rating (naik/turun), top 3 masalah baru, 1 apresiasi, perbandingan minggu lalu
  - [ ] Per outlet (jika multi-cabang): ringkasan per cabang
  - [ ] CTA: "Buka Dashboard" + "Lihat Prioritas Minggu Ini"
  - [ ] Personalisasi: nama owner, nama bisnis
  - [ ] Unsubscribe + frequency preference
  - [ ] HTML + plain text
  - [ ] Track: email_opened, email_cta_clicked
- **Dependency:** GRM-013 (harus ada user paid)
- **Priority:** P1
- **Estimasi:** L
- **Status:** Todo

#### GRM-016: WhatsApp Notification (Opsional)

- **Objective:** Notifikasi WhatsApp untuk alert penting: review negatif baru, tren turun, trial ending, payment due.
- **Acceptance Criteria:**
  - [ ] Opt-in WhatsApp (user masukkan nomor)
  - [ ] Template: 🚨 [Outlet]: 3 review negatif baru (waktu tunggu) → tindakan
  - [ ] Frekuensi kontrol (max 1/hari)
  - [ ] Integrasi Fonnte/WA Gateway
  - [ ] Unsubscribe: ketik STOP
- **Dependency:** GRM-013
- **Priority:** P2
- **Estimasi:** M
- **Status:** Todo

---

### Feature 3.2: Renewal

#### GRM-017: Auto-Renewal System

- **Objective:** Langganan diperpanjang otomatis, dengan notifikasi sebelum charge.
- **Acceptance Criteria:**
  - [ ] Auto-renewal: default ON
  - [ ] Notifikasi: 7 hari sebelum renewal (email)
  - [ ] Charge attempt: H-1 subscription ends
  - [ ] Gagal charge: retry 3x (1, 3, 5 hari setelah)
  - [ ] Gagal total → subscription expired + email
  - [ ] User bisa matikan auto-renewal kapan saja
- **Dependency:** GRM-012
- **Priority:** P1
- **Estimasi:** M
- **Status:** Todo

---

### Feature 3.3: Referral

#### GRM-018: Referral Program

- **Objective:** User merekomendasikan GRM ke owner lain — dapat reward.
- **Acceptance Criteria:**
  - [ ] Unique referral link per user
  - [ ] Referral tracking: siapa diundang, status trial/paid
  - [ ] Reward: 1 bulan gratis per referral yang jadi paid
  - [ ] Referral page di dashboard: link, status, reward
  - [ ] Share button: WhatsApp, Email, Copy Link
  - [ ] Fraud prevention: no self-referral, same business
- **Dependency:** GRM-013
- **Priority:** P2
- **Estimasi:** M
- **Status:** Todo

---

## EPIC 4: Platform Hardening & Scale

**Epic Goal:** Sistem stabil, aman, multi-tenant siap, performa baik di banyak user.

**Definition of Done:**
- [ ] Multi-tenant: satu bisnis bisa punya banyak user dengan role berbeda
- [ ] Permission matrix enforced di semua endpoint
- [ ] Database optimized: semua query critical path <500ms dengan 10K+ review
- [ ] Caching layer aktif untuk landing, preview, AI Advisor
- [ ] Security: OWASP Top 10 tertutup, rate limiting, CSRF, secrets audit
- [ ] Error monitoring live: Sentry/GlitchTip + alert Telegram
- [ ] Admin panel: Ismal bisa lihat semua bisnis, user, subscription, metrik
- [ ] Backup database harian

**Success Metrics:**
- [ ] Dashboard load: <1 detik (dengan cache)
- [ ] Preview generation: <3 detik (dengan cache)
- [ ] Error rate: <1%
- [ ] Uptime: ≥99.5% (exclude maintenance window)
- [ ] Security: 0 critical/high vulnerability
- [ ] Backup: 0 data loss incident
- [ ] Tenant isolation: 0 cross-tenant data leak

---

### Feature 4.1: Multi-Tenant Hardening

#### GRM-019: Membership & Role System

- **Objective:** Satu bisnis bisa punya banyak user dengan role berbeda (owner, admin, supervisor, viewer).
- **Acceptance Criteria:**
  - [ ] Invite user ke bisnis (via email)
  - [ ] Role assignment: owner, admin, supervisor, customer_service, viewer
  - [ ] Permission matrix: siapa bisa akses/ubah apa
  - [ ] UI: Settings → Team → Invite + list + role dropdown
  - [ ] Audit log: user invited, role changed, removed
  - [ ] Owner tidak bisa di-remove
- **Dependency:** GRM-013 (harus ada user dulu)
- **Priority:** P2
- **Estimasi:** L
- **Status:** Todo

---

### Feature 4.2: Performance & Reliability

#### GRM-020: Database Optimization & Indexing

- **Objective:** Query critical path (dashboard, AI Advisor, review list) tetap <500ms dengan data 10K+ review per outlet.
- **Acceptance Criteria:**
  - [ ] Query analysis: identifikasi slow queries (>100ms)
  - [ ] Index: reviews (tenant_id, outlet_id, created_at), (tenant_id, rating)
  - [ ] Index: outlets (tenant_id, business_id)
  - [ ] Dashboard query: explain analyze <200ms untuk 10 outlet, 5000 review
  - [ ] Pagination semua list endpoint
- **Dependency:** GRM-013
- **Priority:** P1
- **Estimasi:** M
- **Status:** Todo

#### GRM-021: Caching Layer

- **Objective:** Cache untuk halaman publik (landing, preview), AI Advisor results, analytics aggregations.
- **Acceptance Criteria:**
  - [ ] Redis/Memcached untuk production
  - [ ] Cache: landing page (1 jam), preview analysis (24 jam per place_id), pricing (1 jam)
  - [ ] Cache: AI Advisor per outlet (invalidasi saat sync baru)
  - [ ] Cache invalidation strategy jelas
  - [ ] Fallback: cache miss → compute → simpan
- **Dependency:** GRM-020
- **Priority:** P2
- **Estimasi:** M
- **Status:** Todo

#### GRM-022: Error Monitoring & Alerting

- **Objective:** Tahu error sebelum user lapor. Monitoring uptime, error rate, slow endpoint.
- **Acceptance Criteria:**
  - [ ] Sentry / GlitchTip integration untuk error tracking
  - [ ] Health check endpoint: /health (DB, Redis, Apify)
  - [ ] Uptime monitoring (external: cron tiap 5 menit)
  - [ ] Alert: error rate >5%, response time >2s, disk >80%, memory >90%
  - [ ] Alert channel: Telegram ke Ismal
- **Dependency:** None (independent)
- **Priority:** P2
- **Estimasi:** M
- **Status:** Todo

---

### Feature 4.3: Security

#### GRM-023: Security Audit & Hardening

- **Objective:** Pastikan tidak ada vulnerability umum (OWASP Top 10) sebelum production launch ke publik.
- **Acceptance Criteria:**
  - [ ] CSRF protection semua form
  - [ ] Rate limiting: login (5/menit/IP), register (3/jam/IP), search (10/menit/IP)
  - [ ] SQL injection: semua query pakai parameterized
  - [ ] XSS: content-security-policy header, template autoescape
  - [ ] HTTPS enforced (sudah via Caddy)
  - [ ] Secrets audit: tidak ada hardcoded key/token/password
  - [ ] Dependency vulnerability scan (pip-audit / safety)
  - [ ] Backup database harian
- **Dependency:** GRM-006 (sebelum register publik)
- **Priority:** P0
- **Estimasi:** M
- **Status:** Todo

---

### Feature 4.4: Admin Panel

#### GRM-024: Admin Dashboard

- **Objective:** Ismal bisa lihat semua bisnis, user, subscription status, dan metrik platform.
- **Acceptance Criteria:**
  - [ ] Admin panel di /admin (superadmin only)
  - [ ] List semua bisnis: nama, brand, plan, status, trial_ends, created_at
  - [ ] List user per bisnis
  - [ ] Metrik platform: total business, trial, paid, churn, MRR
  - [ ] Manual action: extend trial, suspend business, change plan
  - [ ] Search/filter bisnis
- **Dependency:** GRM-013
- **Priority:** P2
- **Estimasi:** M
- **Status:** Todo

---

## Dependency Map

```
GRM-001 (Landing)
  ├── GRM-002 (Static Pages)
  ├── GRM-003 (Public Search)
  │     └── GRM-004 (Public Preview)
  │           ├── GRM-005 (Preview Analytics Service)
  │           └── GRM-006 (Registration) ──┬── GRM-007 (Trial)
  │                                        │     ├── GRM-008 (Onboarding Wizard)
  │                                        │     ├── GRM-009 (Welcome Email)
  │                                        │     └── GRM-010 (Pricing & Plans)
  │                                        │           ├── GRM-011 (Billing Engine)
  │                                        │           │     └── GRM-012 (Payment Gateway)
  │                                        │           │           ├── GRM-013 (Trial→Paid Activation)
  │                                        │           │           │     ├── GRM-015 (Weekly Email)
  │                                        │           │           │     ├── GRM-016 (WhatsApp)
  │                                        │           │           │     ├── GRM-017 (Auto-Renewal)
  │                                        │           │           │     ├── GRM-018 (Referral)
  │                                        │           │           │     ├── GRM-019 (Membership)
  │                                        │           │           │     ├── GRM-020 (DB Optimization)
  │                                        │           │           │     │     └── GRM-021 (Caching)
  │                                        │           │           │     └── GRM-024 (Admin Panel)
  │                                        │           │           └── GRM-014 (Pricing Page Live)
  │                                        │           └── ...
  │                                        └── GRM-023 (Security Audit)
  └── GRM-022 (Error Monitoring) [independent]
```

---

## Execution Order (Critical Path)

1. **GRM-001** — Landing Redesign (P0)
2. **GRM-002** — Static Pages (P1)
3. **GRM-003** — Public Search (P0)
4. **GRM-004** — Public Preview (P0)
5. **GRM-005** — Preview Analytics Service (P1)
6. **GRM-006** — Registration 2-Step (P0)
7. **GRM-023** — Security Audit (P0) — *sebelum register terbuka publik*
8. **GRM-007** — Trial Management (P0)
9. **GRM-008** — Onboarding Wizard (P1)
10. **GRM-009** — Welcome Email (P2)
11. **GRM-010** — Pricing & Plans (P0)
12. **GRM-014** — Pricing Page Live (P1)
13. **GRM-011** — Billing Engine (P0)
14. **GRM-012** — Payment Gateway (P0)
15. **GRM-013** — Trial→Paid Activation (P0)
16. **GRM-015** — Weekly Email (P1)
17. **GRM-017** — Auto-Renewal (P1)
18. **GRM-020** — DB Optimization (P1)
19. **GRM-016** — WhatsApp (P2)
20. **GRM-018** — Referral (P2)
21. **GRM-019** — Membership (P2)
22. **GRM-021** — Caching (P2)
23. **GRM-022** — Error Monitoring (P2)
24. **GRM-024** — Admin Panel (P2)

---

## Issue Count Summary

| Epic | Features | Issues | P0 | P1 | P2 | P3 |
|------|----------|--------|----|----|----|----|
| 1. Customer Acquisition | 3 | 9 | 4 | 4 | 1 | 0 |
| 2. Monetization | 2 | 5 | 4 | 1 | 0 | 0 |
| 3. Customer Success & Retention | 3 | 4 | 0 | 2 | 2 | 0 |
| 4. Platform Hardening | 4 | 6 | 1 | 1 | 4 | 0 |
| **Total** | **12** | **24** | **9** | **8** | **7** | **0** |

---

## Rules

1. **Satu sesi = satu Issue.** Jangan mengerjakan >1 Issue dalam satu sesi.
2. **Selesai → test → commit → report.** Setiap Issue wajib ada completion report.
3. **Jangan mulai Issue berikutnya tanpa instruksi eksplisit.**
4. **Product Vision, Positioning, UI Principle, Engineering Workflow = FINAL.** Tidak diubah tanpa instruksi.
5. **Core Platform tidak boleh rusak.** Setiap perubahan harus lolos regression test.
6. **Backlog ini adalah single source of truth.** Jika ada ide baru → tambahkan ke backlog, jangan implementasi di Issue aktif.

---

STOP — Backlog selesai. Jangan implementasi apa pun.

---

## Implementation Status

Melacak ketergantungan provider eksternal per issue — roadmap migrasi mock → production.

| Issue | Status | Provider | Detail |
|-------|--------|----------|--------|
| GRM-001 | Done | N/A | Static HTML, tidak ada provider eksternal |
| GRM-002 | Done | N/A | Static HTML, tidak ada provider eksternal |
| GRM-003 | Done | Mock | `app/services/discovery.py` — `search_places()` mock data Bubur Fay 7 cabang (TAG: mock_adapter). Target production: Google Places API / Apify Google Search scraper |
| GRM-004 | Done | Mock → Apify | Public preview dari data review publik. Fase MVP: mock data (6 branches, distribusi+issue+AI teaser unik per branch) |
| GRM-005 | Done | Mock → Apify | Backend analytics service. Fase MVP: mock data via reuse `preview.py`. Output JSON: rating, total_review, distribution, top_issues, sentiment_summary, branch_selector |
| GRM-006 | Todo | Internal | Registration 2-step wizard — internal DB, tidak ada provider eksternal |
| GRM-007+ | Todo | Apify | Discovery & multi-city crawl — Google Places API / Apify Google Maps scraper |

### Provider Legend

- **N/A** — tidak ada dependency eksternal
- **Mock** — data contoh / statis untuk MVP
- **Internal** — database / sistem internal GRM
- **Apify** — Apify actor (Google Maps scraper, Google Search scraper, dst)
- **Google Places API** — Google Maps Places API (berbayar)
- **Google Business Profile API** — GBP API untuk akses review own-business (OAuth)

### Migration Path

```
Mock  ──→  Apify (public data)  ──→  Google Places API (production scale)
                                      └─→ Google Business Profile API (own-business)
```
