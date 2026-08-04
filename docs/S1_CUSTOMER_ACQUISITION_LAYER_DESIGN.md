# SPRINT S1 — CUSTOMER ACQUISITION LAYER (PRODUCT DESIGN)

Version: 1.0 · Status: ACTIVE (DESIGN ONLY — DO NOT IMPLEMENT)
Referensi: `grm-product-vision-and-gtm` (acuan permanen)
Mindset: Product Team (bukan engineer). Output = desain produk, tanpa coding/DB/API/halaman.

---

## 1. PRD SPRINT S1

### Ringkasan
Membangun **Customer Acquisition Layer**: seluruh pengalaman dari pertama kali user mengenal GRM sampai menjadi customer berbayar — tanpa bantuan sales.

### Target User
- **Owner UMKM / F&B multi-cabang** (misal Bubur Fay, PLN-like service business) — persona utama
- **Marketing manager** brand multi-outlet (bonus persona)
- **Agency** yang mengelola review banyak klien (tahap lanjut)

### Masalah
Owner tidak tahu kondisi review bisnisnya, sulit membandingkan cabang, dan tidak tahu tindakan pertama. GRM solusinya — tapi belum bisa "dicoba sendiri" tanpa sales.

### Solusi
Customer Acquisition Layer: Landing (value < 3 menit) → **Preview Analysis tanpa daftar** → Registration → Free Trial → Subscription → Dashboard → Renewal → Referral.

### Success Metrics (North Star)
- Visitor memahami value: **< 3 menit**
- **Preview Analysis** dimulai: ≥ 40% visitor landing
- **Trial started**: ≥ 10% preview → register
- **Paid subscription**: ≥ 20% trial → bayar
- Time-to-value (search → lihat analisis): **< 2 menit**

### Scope Sprint S1
- Hanya desain (IA, journey, funnel, screen flow, wireframe, copy).
- Billing engine & payment = Sprint terpisah (Tahap 4 roadmap) — desain alurnya saja.

---

## 2. INFORMATION ARCHITECTURE (versi terbaik)

```
PUBLIC (tanpa login)                    AUTH / PRODUCT (login)
├── Landing (/)                         ├── Login
│   ├── Hero + CTA                       ├── Register (Signup 2-langkah)
│   ├── Social proof (jumlah bisnis)     ├── Preview Analysis (bisa tanpa login,
│   ├── Features (→ hasil bisnis)        │     terbatas 1 bisnis)
│   ├── How it Works (3 langkah)         ├── Trial Dashboard (14 hari)
│   ├── Live Demo (interaktif contoh)    ├── Owner Dashboard (existing)
│   ├── Pricing (3 tier)                 ├── Onboarding (tambah outlet)
│   ├── FAQ                              └── Billing/Subscription (Tahap 4)
│   └── Footer (kontak, legal)
├── /features
├── /how-it-works
├── /demo            ← Preview Analysis publik
├── /pricing
├── /faq
└── /login · /register
```

**Keputusan desain:**
- **Search Business + Preview Analysis ada di halaman Landing** (inline, tanpa pindah halaman) — shortest path ke value. Visitor ketik nama bisnis → langsung lihat analisis contoh → CTA register.
- Landing = hub; halaman lain (features/how-it-works/pricing/faq) = pendukung keputusan.
- Demo = analisis bisnis **fiktif** (anonymized) supaya tidak bocor data review orang; Preview pribadi (bisnis sendiri) hanya setelah register/trial — menjaga Core Platform.

---

## 3. NAVIGATION MAP

```
[PUBLIC NAV]  Logo GRM | Fitur | Cara Kerja | Demo | Harga | FAQ | [Login] [Coba Gratis→]
[FOOTER]      Produk: Fitur·Demo·Harga | Bantuan: FAQ·Hubungi | Legal: Privasi·Syarat | © GRM

[AUTH NAV — existing]  Dashboard | Outlet | Performa | AI Advisor | Reviews | Settings | [+ Outlet]
```

Alur publik → produk: Coba Gratis → (search) → preview → register → dashboard trial.
Back button & breadcrumb minimal (landing single-page friendly).

---

## 4. USER JOURNEY (persona utama: Owner UMKM multi-cabang)

```
Tahap        Aksi user                                Emosi              Titik kontak GRM
───────────  ───────────────────────────────────────  ─────────────────  ───────────────────────────────
Awareness    Liat iklan/IG/WhatsApp/referensi          penasaran          → landing (3 detik hook)
Landing      Baca hero 10-30 detik                     "ini buat saya?"    → value prop + social proof
Value        Scroll Features/How it Works              "ngerti, mau coba"  → CTA "Coba Gratis"
Preview      Ketik nama bisnis → lihat analisis        "wow, data saya!"   → Preview Analysis inline
Register     Daftar (email + password)                 ringan              → 2 langkah, tanpa kartu kredit
Trial        Tambah outlet → sync → lihat AI Advisor   "ini yang saya mau" → Onboarding + Trial Dashboard
Activate     Baca Prioritas Hari Ini                   "langsung action"   → AI Advisor (fokus <10 detik)
Subscription Paywall/trial habis → pilih paket          "worth it"          → Pricing + Billing
Weekly       Buka dashboard tiap minggu                "tetap terpantau"   → Monitoring + email weekly
Renewal      Bayar lagi                                "sudah kebiasaan"   → auto-billing + reminder
Referral     Rekomendasi ke owner lain                 bangga              → link referral + reward
```

**Friction points yang harus dihilangkan:** tanpa preview (user takut data), daftar panjang, kartu kredit di awal, onboarding rumit.

---

## 5. CONVERSION FUNNEL

```
Visitor (100%)
  ↓  40% paham value & klik CTA
Search/Preview (40%)
  ↓  50% lihat analisis & tertarik
Register (20%)
  ↓  50% selesaikan onboarding
Trial Active (10%)
  ↓  30% pakai dashboard minggu pertama
Paid Subscription (3%)
  ↓  70% renew bulan berikutnya
Renewal (2.1%)
  ↓  10% referral
Referral (0.2% → visitor baru)
```

**Pintu funnel:** Preview = kunci (tanpa daftar). **Drop-off utama:** register (2 langkah, no credit card), activation (onboarding 1-2 menit).

---

## 6. SCREEN FLOW

```
Landing (/)
   │ CTA "Coba Gratis" (scroll ke search)
   ▼
Search Business (inline di landing)
   ▼ (pilih bisnis fiktif / ketik nama)
Preview Analysis (tanpa login, 1 bisnis contoh)
   ├─ CTA "Daftar untuk analisis bisnis Anda" → Register
   └─ (opsional) "Lihat contoh lain"
Register (2 langkah: akun + profil bisnis)
   ▼ verify email
Trial Dashboard (14 hari, tanpa kartu)
   └─ Onboarding wizard: + Tambah Outlet → Sync → AI Advisor
        ▼
Owner Dashboard (existing)
   ├─ AI Advisor (fokus)
   ├─ Performa outlet
   └─ Billing/Subscription (Tahap 4: pilih paket → bayar)
Renewal/Referral (email weekly + link referral)
```

---

## 7. WIREFRAME (LOW-FIDELITY)

### 7.1 Landing
```
┌──────────────────────────────────────────────────────────┐
│ [GRM.]            Fitur Cara Demo Harga FAQ   [Login]     │
│                       [Coba Gratis →]                     │
│  "Naikkan rating & kepuasan pelanggan dari review        │
│   Google — otomatis. Tahu masalah terbesar dalam 10       │
│   detik, siapa yang harus menangani."                     │
│  [Nama bisnis Anda ▓▓▓▓▓▓▓▓▓▓▓]  [Lihat Analisis →]      │
│  ── 500+ bisnis memantau review ──                        │
│  [Feature 1] [Feature 2] [Feature 3]  (3 kartu hasil)     │
│  Cara Kerja: 1.Tambahkan 2.Sinkron 3.Tindakan             │
│  [Demo Preview embed]                                     │
│  Pricing: [Pemula] [Pro*] [Premium]                       │
│  FAQ (accordion)                                          │
│  [Coba Gratis 14 Hari — tanpa kartu kredit]               │
└──────────────────────────────────────────────────────────┘
```

### 7.2 Preview Analysis (kunci konversi)
```
┌──────────────────────────────────────────────────────────┐
│ Analisis: [Bubur Fay] [Bekasi ▼]  [Lihat]                │
│  Rating ★4.48 · 438 review · 3 masalah utama              │
│  🚨 Prioritas: Rasa tidak konsisten (10 review)           │
│     • rasa berubah · makanan basi                         │
│  [Bar distribusi rating] [Bar sentimen]                   │
│  [🔒 Daftar gratis untuk analisis BISNIS ANDA →]          │
└──────────────────────────────────────────────────────────┘
```

### 7.3 Register (2 langkah)
```
[1/2] Email ▓▓▓ · Password ▓▓▓ · Nama ▓▓▓   → Lanjut
[2/2] Nama bisnis ▓▓▓ · Kota ▓▓▓  → Mulai Coba Gratis
(✅ tanpa kartu kredit · 14 hari)
```

### 7.4 Trial Dashboard (hari pertama)
```
[GRM.]  Dashboard | Outlet | Performa | AI Advisor | ...
🚨 Prioritas Hari Ini: [masalah #1 + PIC + tindakan]
Ringkasan: N masalah · N apresiasi
[Banner trial: "14 hari tersisa → Pilih Paket"]
```

---

## 8. VALUE PROPOSITION PER HALAMAN

| Halaman | Tujuan | CTA utama | Perasaan user |
|---|---|---|---|
| Landing | Paham value <3 menit | "Coba Gratis" / "Lihat Analisis" | "Ini menyelesaikan masalah saya" |
| Preview | Buktikan value dengan data | "Daftar untuk bisnis Anda" | "Wow, saya mau ini" |
| Pricing | Transparan, pilih paket | "Mulai Pro" | "Harga masuk akal, ROI jelas" |
| Register | Masuk tanpa hambatan | "Mulai Coba Gratis" | "Cepat & aman" |
| Trial Dashboard | Rasakan hasil nyata | "Pilih Paket" | "Ini meningkatkan bisnis saya" |
| FAQ | Hilangkan keraguan | "Coba Gratis" | "Tenang, semua terjawab" |

---

## 9. DRAFT COPYWRITING (fokus manfaat, bukan fitur)

**Hero landing:**
"Review Google Anda bicara. GRM menerjemahkannya jadi **tindakan**.
Naikkan rating, puaskan pelanggan, dan lindungi reputasi bisnis Anda — tanpa membaca ratusan review satu per satu."

**Preview CTA:**
"Lihat analisis bisnis Anda seperti ini — **gratis 14 hari**, tanpa kartu kredit."

**Features (hasil, bukan fitur):**
- "Tahu **masalah terbesar** pelanggan dalam 10 detik." (bukan: "kategori review otomatis")
- "Bandingkan **setiap cabang** — mana yang perlu perhatian." (bukan: "dashboard multi-outlet")
- "Dapatkan **rencana tindakan + penanggung jawab**." (bukan: "AI Advisor")
- "Pantau **setiap minggu** tanpa buka Google Maps satu-satu."

**Pricing (3 tier):**
- **Pemula** — 1 outlet · Rp 99rb/bulan
- **Pro** (populer) — hingga 5 outlet · Rp 299rb/bulan
- **Premium** — outlet tanpa batas · Rp 799rb/bulan
(angka indikatif; keputusan harga = sprint terpisah)

**FAQ (top):**
- "Berapa lama setup?" → "2 menit: tambah outlet, sinkron otomatis."
- "Apakah butuh login Google Business?" → "Tidak. GRM membaca review publik."
- "Apa bedanya dengan Google My Business?" → "GRM menganalisis & memberi prioritas tindakan + PIC, bukan sekadar menampilkan."

---

## 10. GROWTH REVIEW

**Friction yang ditemukan & solusi desain:**
1. **Preview butuh daftar?** → Tidak. Preview analisis di landing tanpa login (1 bisnis contoh). Kunci self-service.
2. **Registrasi panjang?** → 2 langkah, tanpa kartu kredit, tanpa verifikasi manual (email OTP opsional).
3. **Time-to-value?** → Search → Preview inline < 1 menit; trial → AI Advisor siap < 5 menit (sync otomatis).
4. **Owner bisa coba < 3 menit?** → Ya: buka landing (10s) → ketik bisnis (10s) → lihat preview (30s) → daftar (60s) → trial dashboard (30s). ≈ 2,5 menit.
5. **Shorten:** hapus halaman "About" dari nav (pindah footer) — fokus ke hasil.

---

## 11. SELF REVIEW

**Terhadap product philosophy:**
- Setiap halaman punya CTA jelas menuju konversi (Visitor→Paid). ✅
- Preview memvalidasi value sebelum bayar → mengurangi churn trial. ✅
- Bahasa manfaat, bukan fitur. ✅
- Arsitektur: Customer Layer (landing/preview/register/billing) terpisah dari Core Platform — tidak merusak. ✅
- Gap: pricing angka belum final; billing engine = sprint berikutnya; marketing website penuh (SEO/blog) = Tahap 2 lanjutan.

**Risiko:**
- Preview data fiktif bisa kurang meyakinkan → sertakan testimoni/angka.
- Trial 14 hari tanpa activation nudge → email onboarding + in-app nudge.

---

STOP — Sprint S1 selesai (desain). Tunggu approval sebelum implementasi.

---

# SPRINT S1 REVISION — 4 ARTEfAK TAMBAHAN

## 12. DECISION FUNNEL (proses psikologis user)

Bukan sekadar langkah — ini **perjalanan keputusan emosional** yang harus didorong tiap halaman:

```
Problem Awareness   "Review bisnisku banyak yang negatif tapi aku tidak tahu harus mulai dari mana."
      ↓             → Landing hero menyentuh masalah (rating, keluhan, reputasi)
Interest            "Ada alat yang bisa mengubah review jadi tindakan?"
      ↓             → Features/How it Works (manfaat konkret)
Trust               "Apakah ini aman & benar-benar berfungsi?"
      ↓             → Social proof, kejelasan tanpa login Google, privasi, transparansi harga
Curiosity           "Seperti apa hasilnya untuk bisnisku?"
      ↓             → Preview Analysis (kunci! user melihat 'masa depan' datanya)
Trial               "Tidak rugi coba — gratis 14 hari, tanpa kartu."
      ↓             → Register 2 langkah + onboarding instan
Confidence          "Data saya benar, Advisor-nya masuk akal, saya bisa bertindak."
      ↓             → Trial Dashboard + AI Advisor fokus + hasil minggu pertama
Purchase            "Ini worth it — saya bayar."
      ↓             → Pricing transparan + billing mulus
Retention           "Saya butuh ini tiap minggu."
      ↓             → Monitoring + email weekly + renewal
```

**Prinsip desain:** tiap halaman = satu "dorongan psikologis" menuju tahap berikutnya. Landing menyentuh **Problem**; Preview membangkitkan **Curiosity**; Trial membangun **Confidence**; hasil minggu pertama mengubah Confidence → **Purchase**.

---

## 13. TRUST LAYER (mengapa owner percaya sebelum mencoba)

Elemen yang membangun kepercayaan **sebelum** user memasukkan data:

1. **Tanpa login Google** — "GRM membaca review PUBLIK. Tidak perlu akun Google Business, tidak ada akses ke data pribadi pelanggan." (beda kunci dari tools lain)
2. **Privasi eksplisit** — badge: "Data bisnis Anda aman · hanya Anda yang melihat · kami tidak menjual data"
3. **Transparansi sumber** — "Data dari Google Maps (review publik) · diperbarui otomatis"
4. **Social proof** — jumlah bisnis terdaftar, testimoni owner, logo partner (kalau ada), studi kasus singkat (Bubur Fay: +0.2 rating dalam 3 bulan — contoh)
5. **Kejelasan harga** — pricing di depan, tanpa biaya tersembunyi, "tanpa kartu kredit untuk trial"
6. **Preview tanpa daftar** — bukti value tanpa komitmen = trust tertinggi
7. **Kredibilitas data** — label "review tersimpan vs total di Google" (belajar dari RUN_Q1), periode jelas, tidak ada angka mengada-ada
8. **Bahasa sederhana** — tidak ada jargon teknis (AI/API/OAuth tidak disebut di publik)
9. **Kontak nyata** — WhatsApp/email dukungan terlihat, FAQ menjawab keraguan
10. **Legal** — privasi & syarat jelas di footer

---

## 14. CURIOSITY LAYER (membuat Preview membuat user ingin buka AI Advisor)

Preview tidak cukup menampilkan angka — harus **menggantungkan** sesuatu yang hanya bisa dibuka setelah daftar:

1. **Tampilkan "teaser analisis"** di preview:
   - Rating, distribusi, top kategori (gratis lihat)
   - 🚨 **"Prioritas Hari Ini"** tampil SAMAR: judul masalah + jumlah review, tapi **saran tindakan & PIC dikunci** dengan blur + label "🔒 Buka setelah daftar"
2. **Teaser AI Advisor** — kartu "AI Advisor akan memberitahu: *masalah terbesar, siapa yang harus menangani, tindakan pertama*" dengan 2 contoh masalah nyata dari bisnis fiktif, lalu 1 masalah "milik bisnis Anda" yang terkunci.
3. **"Penasaran?" nudge** — setelah preview, CTA: "Buka 3 prioritas perbaikan bisnis Anda →" (bukan "Daftar" generik).
4. **Preview per cabang** — pilih "Bekasi" vs "Depok" → tampilkan perbandingan samar ("Cabang Bekasi ⭐4.5 · Depok ⭐4.8 — mana yang perlu perhatian? 🔒")
5. **Urgency ringan** — "Analisis ini diperbarui otomatis · lihat versi live bisnis Anda gratis 14 hari"
6. **Gamifikasi rasa ingin tahu** — preview menampilkan "3 masalah terbesar" tapi hanya 1 yang terlihat; 2 lainnya blur dengan jumlah review — user ingin buka AI Advisor untuk melihat sisanya.

**Tujuan:** Curiosity → Trial (bukan sekadar "lihat angka").

---

## 15. EMOTIONAL JOURNEY (emosi per halaman)

```
Landing           CURIOUS      "Bisa begitu? Ada alat untuk ini?"
      ↓
Features          INTERESTED   "Ini menyelesaikan masalah yang aku rasakan."
      ↓
Preview           SURPRISED    "Wow, datanya lengkap dan jelas. Aku bisa lihat masalah bisnisku."
      ↓
Teaser AI Advisor WANT MORE    "Aku penasaran — apa yang AI katakan tentang bisnisku?"
      ↓
Register          HOPEFUL      "Mudah, cepat, tanpa kartu. Semoga bermanfaat."
      ↓
Onboarding        ENGAGED      "Outlet aku masuk, review tersinkron — keren."
      ↓
Dashboard         CONFIDENT    "Aku bisa lihat kondisi semua cabang sekaligus."
      ↓
AI Advisor        RELIEVED     "Akhirnya tahu harus mulai dari mana — dan siapa yang menangani."
      ↓
Monitoring        CONTROL      "Aku pantau tiap minggu, tidak buta lagi."
      ↓
Billing           COMMITTED    "Ini worth it, aku lanjutkan."
      ↓
Renewal/Referral  PROUD        "Aku merekomendasikan ke owner lain."
```

**Checkpoint desain:** jika sebuah halaman tidak memunculkan emosi yang diharapkan, halaman itu gagal. Contoh: Preview yang hanya tabel angka → tidak SURPRISED → perlu visualisasi + teaser AI.

---

STOP — Revision S1 selesai (desain). Tunggu approval sebelum implementasi.

---

# SPRINT S1 FINAL REVISION — 4 ARTEfAK TERAKHIR

## 16. URGENCY LAYER (mengapa owner harus mencoba SEKARANG)

Urgency yang sehat (bukan tekanan palsu):

1. **Biaya penundaan** — "Setiap minggu tanpa analisis = pelanggan tidak puas yang tidak tertangani = rating turun = pelanggan baru hilang."
2. **Review negatif tidak menunggu** — "Satu review buruk hari ini bisa dibaca 100 calon pelanggan minggu ini."
3. **Sinyal kompetitor** — "Kompetitor yang memantau review akan bertindak lebih dulu."
4. **Gratis & cepat** — "Tidak ada alasan menunda: 2 menit setup, 14 hari gratis, tanpa kartu."
5. **Musiman** — "Momen sibuk (weekend, libur, promo) = review membludak = waktu terbaik memantau."
6. **Satu kali analisis tidak cukup** — "Review berubah tiap hari; analisis sekali tidak menyelesaikan. Mulai pantau rutin sekarang."
7. **Jendela trial** — "Trial 14 hari mulai hari ini — cukup untuk melihat pola 1 minggu dan menyiapkan perbaikan."

**Prinsip:** urgency harus berasal dari **konsekuensi bisnis nyata**, bukan countdown palsu. Landing menampilkan 1 baris urgency; email/push reminder saat trial hampir habis.

---

## 17. WHY NOW NARRATIVE

> "Setiap hari, pelanggan Anda menulis review — dan calon pelanggan membacanya.
> Review buruk yang tidak tertangani bukan sekadar 'komentar': itu **rating turun**, itu **pengunjung yang batal datang**, itu **uang yang hilang**.
> Masalahnya bukan Anda tidak peduli — Anda tidak tahu **mulai dari mana** di antara ratusan review.
>
> GRM hadir untuk mengubah itu: dalam 2 menit, Anda tahu **3 masalah terbesar**, **siapa yang harus menangani**, dan **tindakan pertama**.
> Menunda seminggu berarti menunda perbaikan — dan membiarkan satu minggu lagi keluhan tumbuh tanpa jawaban.
>
> Mulai gratis hari ini. 14 hari, tanpa kartu. Lihat sendiri apa yang dikatakan review pelanggan Anda."

**Tujuan narasi:** mengubah "nanti saja" menjadi "kalau bukan sekarang, kapan?" — dengan konsekuensi yang nyata dan solusi yang jelas.

---

## 18. PRODUCT STORY

> ### Kisah Bu Sari, pemilik Bubur Fay
>
> Bu Sari membuka 3 cabang bubur ayam. Pagi-pagi ia membuka Google Maps — membaca review satu per satu, mencari tahu kenapa cabang Depok rating-nya lebih rendah. 45 menit kemudian ia hanya makin bingung: ada yang bilang pelayanan lambat, ada yang porsi kecil, ada yang harga. Ia tidak tahu mana yang benar, mana yang kebetulan, dan siapa yang harus ia tegur.
>
> Suatu hari ia melihat GRM di media sosial: "Lihat analisis bisnis Anda gratis." Ia iseng mengetik nama bisnisnya. **Dua menit kemudian, ia terkejut** — layar menampilkan: *"3 masalah terbesar: rasa tidak konsisten (10 review), pelayanan kurang ramah (5 review), porsi mengecil (3 review) — PIC: Kitchen, Crew, Chef."* Ia tidak perlu membaca 400 review. Semuanya sudah diringkas jadi tindakan.
>
> Ia daftar — tanpa kartu, 2 menit. Cabang-cabangnya tersinkron otomatis. Keesokan harinya, AI Advisor memberitahu: *"Cabang Bekasi paling banyak dikeluhkan soal waktu tunggu di jam 12–14."* Bu Sari menambah satu kasir di jam sibuk.
>
> Seminggu kemudian, review baru mulai membaik. Bulan berikutnya rating cabang Bekasi naik 0.2. Bu Sari membayar langganan tanpa ragu — bukan karena dashboard-nya bagus, tapi karena **review pelanggannya berubah, dan ia tahu apa yang harus dilakukan selanjutnya**.
>
> Sekarang, tiap Minggu pagi ia buka GRM sekali — bukan untuk membaca, tapi untuk **memutuskan**. Dan ketika temannya sesama pemilik usaha bertanya, Bu Sari hanya bilang: "Coba saja, gratis. Kamu akan kaget apa yang review pelangganmu katakan."

**Elemen story:** persona nyata → masalah yang dikenali → **WOW Moment** (preview) → aksi mudah → hasil terukur → pembayaran karena hasil, bukan fitur → referral alami.

---

## 19. WOW MOMENT (momen paling berkesan dalam 3 menit pertama)

### Definisi eksplisit
> **WOW Moment = detik ketika owner melihat "Prioritas Hari Ini" untuk BISNISNYA SENDIRI — masalah terbesar yang langsung dikenali, dengan jumlah review nyata, PIC yang tepat, dan tindakan pertama — dalam < 3 menit sejak pertama membuka website.**

Momen ini terjadi tepat setelah **Preview Analysis** (bisnis fiktif → "ini bisa untuk bisnisku") DAN setelah **trial sync** (data nyata miliknya → "ini BISNISKU, dan aku tahu harus mulai dari mana"). Emosi: *Surprised → Relief* (lihat §15).

### Bagaimana seluruh onboarding diarahkan menuju WOW Moment

| Langkah | Waktu | Tujuan (menuju WOW) |
|---|---|---|
| Landing → Preview (bisnis fiktif) | 0–60 detik | Tunjukkan bentuk hasil; tanam "ini bisa untuk bisnisku" |
| CTA "Buka analisis bisnis Anda" | 60–90 detik | Register 2 langkah tanpa kartu (hambatan minimum) |
| Onboarding: + Tambah Outlet | 90–120 detik | Auto-discover cabang (multi-kota), centang checklist |
| Sync review | 120–150 detik | Progress jelas "review masuk…" (loading box) |
| **WOW: AI Advisor "Prioritas Hari Ini"** | **≤180 detik** | 🚨 Masalah terbesar + bukti + PIC + tindakan pertama — untuk BISNISNYA |
| Nudge trial | setelah WOW | "Sisa 14 hari — lihat hasil minggu pertama" |

**Aturan desain:**
- Tidak boleh ada hambatan sebelum WOW (kartu kredit, verifikasi panjang, onboarding rumit).
- WOW harus **personal** (data bisnis user), bukan generik — itu bedanya dengan preview fiktif.
- Setelah WOW, satu CTA jelas: "Mulai tindakan pertama" (bukan "pelajari fitur").
- Jika user mencapai WOW > 3 menit, onboarding gagal — ukur waktu-ke-WOW sebagai metrik.

---

STOP — FINAL Revision Sprint S1 selesai (desain). Tunggu approval sebelum implementasi.
