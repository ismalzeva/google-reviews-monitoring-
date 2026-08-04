# GATE AC Round 2 — Product Validation Report

**Tanggal:** 4 Agustus 2026  
**Validator:** Hermes (automated browser testing)  
**Lingkungan:** `localhost:8083` — `grm_db` PostgreSQL — Flask via venv  
**Browser:** 375px simulated (Round 2 Part 1) + 1280px Browserbase (Round 2 Part 2)  
**Data:** Bubur Fay (fallback + mock, Apify timeout 8s)  
**Akun Test:** `gate-round2-1785826385@test.com` / `Test1234!` (dibuat saat validasi)  
**Baseline:** EPIC-001 (DISC-001 s/d DISC-004) — commit `1e06e8e`

---

## 1. Executive Summary

| Metrik | Hasil |
|---|---|
| Skenario PASS | 4/7 |
| Skenario FAIL | 2/7 |
| Skenario PARTIAL | 1/7 |
| **Critical tersisa** | **2** |
| **High tersisa** | **4** |
| Medium tersisa | 3 |
| **Verdict** | **BLOCKED** |

GATE AC mensyaratkan **0 Critical** untuk APPROVED. Saat ini ada 2 Critical — registrasi broken link dan Flask error bocor ke UI.

---

## 2. Ringkasan Per Skenario

| # | Skenario | Status | Critical | High | Medium |
|---|---|---|---|---|---|
| 1 | Landing Page | ✅ PASS WITH NOTES | 0 | 0 | 0 |
| 2 | Search | ✅ PASS | 0 | 0 | 0 |
| 3 | Preview | ⚠️ PASS WITH NOTES | 0 | 1 | 1 |
| 4 | Register | ❌ FAIL | 1 | 1 | 0 |
| 5 | Trial Activation | ❌ FAIL | 1 | 1 | 1 |
| 6 | AI Advisor | ✅ PASS WITH NOTES | 0 | 0 | 0 |
| 7 | Dashboard | ⚠️ PASS WITH NOTES | 0 | 1 | 1 |

---

## 3. Detail per Skenario

### SKENARIO 1: Landing Page — ✅ PASS WITH NOTES

**Langkah:** Buka halaman pertama → pahami value prop → cari CTA → scroll penuh.

| Check | Hasil |
|---|---|
| UVP 10-detik: "Tahu masalah terbesar pelanggan Anda dalam 10 detik" | ✅ |
| Trial gratis tanpa kartu kredit terlihat | ✅ "Semua paket: trial 14 hari gratis · tanpa kartu kredit" |
| CTA utama konsisten (nav + pricing + footer) | ✅ |
| Console errors | ✅ 0 errors |
| Horizontal scroll (1280px) | ✅ Tidak ada |
| Mobile 375px | ⚠️ Tidak terverifikasi (browser tool tidak support viewport resize) |

**Friction:** Tidak ada. Mobile verification deferred ke manual testing.

---

### SKENARIO 2: Search — ✅ PASS

**Langkah:** Cari "Bubur Fay" → lihat hasil → klik salah satu.

| Check | Hasil |
|---|---|
| Search box langsung di atas fold | ✅ |
| Hasil "Bubur Fay" muncul (7 cabang) | ✅ |
| Nama + alamat + rating + review count per hasil | ✅ |
| Source banner (DISC-004): "⚠️ Google Maps tidak merespons — menampilkan data fallback" + "Coba lagi →" | ✅ |
| Preview bisa diakses TANPA login | ✅ |
| Hasil unik, mudah dibedakan | ✅ |
| Loading indicator saat search | ✅ (teks "Mencari...") |

**Friction:** 0.

---

### SKENARIO 3: Preview — ⚠️ PASS WITH NOTES

**Langkah:** Klik outlet dari search → lihat preview → cek analisis → cek CTA.

| Check | Hasil |
|---|---|
| Nama outlet + rating terlihat | ✅ "Bubur Fay Depok — 4.5★" |
| Distribusi rating (bar chart) | ✅ 5★=720 (hanya 5★ yang tampil di fallback, tapi grafik ada) |
| Branch selector (dropdown) | ✅ |
| CTA: "Coba Gratis" + "Buka Prioritas Perbaikan →" | ✅ |
| Tidak ada blank state / white screen | ✅ |
| Error state (DISC-004): saat gagal fetch | ✅ "⚠️ Informasi dari Google Maps tidak dapat dimuat" + 2 CTA |
| **Masalah Utama = analisis nyata, bukan placeholder** | ❌ **HIGH** — Isinya: *"Kategori masalah paling sering disebut — tanpa rekomendasi PIC atau tindakan"* |
| AI Advisor content | ❌ **MEDIUM** — Hanya teks "AI", tidak ada insight |

**FRICTION-003 [HIGH]:** Preview publik belum menampilkan analisis nyata. Placeholder "tanpa rekomendasi PIC atau tindakan" membuat owner tidak bisa melihat value produk sebelum register.

**FRICTION-005 [MEDIUM]:** AI Advisor section di preview hanya placeholder "AI".

---

### SKENARIO 4: Register — ❌ FAIL

**Langkah:** Dari preview, klik "Coba Gratis 14 Hari" → isi form step 1 → step 2 → submit → login.

| Check | Hasil |
|---|---|
| Step indicator 1/2 → 2/2 | ✅ |
| Validasi form (button hanya enable jika field valid) | ✅ |
| Badge: "14 hari gratis · Tanpa kartu kredit · Langsung pakai" | ✅ (muncul di step 2) |
| Tidak ada field kartu kredit | ✅ |
| Auto-login setelah submit | ✅ (redirect 302, langsung ke dashboard) |
| Loading time <3 detik | ✅ |
| **Link CTA dari preview → /register** | ❌ **CRITICAL** — 404 Not Found. Route sebenarnya: `/auth/register` |
| **Password toggle (show/hide)** | ❌ **HIGH** — Tidak ada. Kritis untuk mobile input. |
| Error: "Email sudah terdaftar" | ✅ (muncul saat daftar ulang) |
| Rate limit: "Terlalu banyak percobaan" | ✅ (setelah >10 POST/menit) |

**FRICTION-001 [CRITICAL]:** Link `href="/register"` di semua CTA "Coba Gratis" di preview → broken (404). Harusnya `/auth/register`.

**FRICTION-002 [HIGH]:** Tidak ada toggle show/hide password di form step 1 dan login.

---

### SKENARIO 5: Trial Activation — ❌ FAIL

**Langkah:** Setelah register/login → trial welcome → "Mulai Aktivasi" → step 1→2→3→4.

| Step | Hasil |
|---|---|
| Trial Welcome: "Selamat datang" + "Outlet: 0/1" + "Mulai Aktivasi →" | ✅ |
| Step 1/4 — Cari Outlet: search "Bubur Fay" → 5 hasil | ✅ |
| Step 1/4 — Rating + review count + "Pilih" CTA per hasil | ✅ |
| Step 1/4 — "Trial: maks 1 outlet" diinformasikan | ✅ |
| Step 2/4 — Verifikasi Outlet: "Ya, Lanjutkan" CTA | ✅ |
| Step 3/4 — Sinkronkan Review | ❌ **CRITICAL** — Flask error: *"Working outside of application context"* bocor ke halaman HTML |
| Step 3/4 — **Tidak ada opsi "Lewati"** | ❌ **HIGH** — User terjebak: hanya ada "Coba Lagi" |
| Step 3/4 — `/trial/activate/step3/start` endpoint | ❌ Broken — menghasilkan error setiap panggilan |
| Step 4/4 — (WOW Moment) | ❌ Tidak bisa dicapai karena terjebak di step 3 |
| Route `/trial/skip` | ✅ Berfungsi — bypass ke dashboard |

**FRICTION-006 [CRITICAL]:** Endpoint `/trial/activate/step3/start` broken — Flask `RuntimeError: Working outside of application context`. Error text bocor ke HTML frontend.

**FRICTION-007 [HIGH]:** Step 3 tidak memiliki fallback path. User yang Apify-nya timeout (common scenario) TIDAK BISA melanjutkan aktivasi. Hanya ada tombol "Coba Lagi" — infinite loop.

**FRICTION-008 [MEDIUM]:** WOW Moment (step 4) tidak bisa divalidasi karena terblokir di step 3.

---

### SKENARIO 6: AI Advisor — ✅ PASS WITH NOTES

**Langkah:** Setelah trial selesai → klik "AI Advisor" di nav → lihat prioritas perbaikan.

| Check | Hasil |
|---|---|
| "Prioritas Perbaikan Hari Ini" heading — jelas | ✅ |
| Period selector: Seluruh Waktu / 7h / 30h / 90h | ✅ |
| Update timestamp: "diperbarui 4/8/2026, 15.11.45" | ✅ |
| Empty state: "Belum ada masalah signifikan. 👍" — informatif | ✅ |
| Disclaimers: "Bukti hanya dari review publik yang tersimpan" + priority labels | ✅ |
| Source attribution: "source: Apify" | ✅ |
| Tidak ada blank state | ✅ |
| Console errors | ✅ 0 |

**Friction:** Tidak ada. Empty state informatif dan jelas. Data analisis hanya kosong karena 0 review tersimpan — bukan bug UI.

---

### SKENARIO 7: Dashboard — ⚠️ PASS WITH NOTES

**Langkah:** Dari trial selesai → lihat dashboard → semua widget → cek empty states.

| Check | Hasil |
|---|---|
| Outlet terpilih terlihat: "Bubur Fay Depok · 4.5★ · 1280 Review di Google" | ✅ |
| Period selector: Seluruh Waktu + 7h/30h/90h/Bulan/Rentang | ✅ |
| Stats cards: Rating Rata-rata, Review, Positif, Negatif | ✅ (semua "—", karena 0 data) |
| AI Advisor widget + CTA "Lihat semua →" | ✅ |
| Chart: Tren Rating | ✅ "Belum ada data review pada periode ini." |
| Chart: Distribusi Rating | ✅ "Belum ada review pada periode ini." |
| Chart: Sentimen | ✅ "Belum ada data." |
| Aspek Teratas: 6 kategori + count 0 | ✅ (ditampilkan walau kosong) |
| "Sync terakhir: belum" + "Sync Sekarang" CTA | ✅ |
| Navigation: Dashboard, Outlet, Performa, AI Advisor, Reviews, Settings | ✅ Semua berfungsi |
| Reviews tab: filter Semua/Positif/Netral/Negatif | ✅ |
| Settings: Profile + Provider mode + Logout | ✅ |
| **Outlet tab kosong** | ❌ **HIGH** — Outlet "Bubur Fay Depok" yang sudah dipilih di trial tidak muncul di tab Outlet. Hanya "Tambah outlet baru." |
| **Performa tab kosong** | ⚠️ **MEDIUM** — Outlet tidak muncul, sehingga perbandingan 1v1 dan perbandingan per kota tidak berfungsi. |

**FRICTION-009 [HIGH]:** Outlet tab tidak menampilkan outlet yang sudah dipilih saat trial. User akan bingung: "Outlet saya ke mana?"

**FRICTION-010 [MEDIUM]:** Performa tab bergantung pada outlet yang muncul — karena outlet tidak muncul, seluruh fitur comparison tidak bisa digunakan.

---

## 4. Daftar Friction Lengkap

| ID | Severity | Skenario | Deskripsi |
|---|---|---|---|
| FRICTION-001 | **CRITICAL** | 4 | Link CTA "Coba Gratis 14 Hari" → `/register` (404). Harusnya `/auth/register` |
| FRICTION-006 | **CRITICAL** | 5 | Endpoint `/trial/activate/step3/start` broken: Flask `app_context` error + error text bocor ke UI |
| FRICTION-002 | **HIGH** | 4 | Tidak ada toggle show/hide password di form register & login |
| FRICTION-003 | **HIGH** | 3 | Preview "Masalah Utama" = placeholder, bukan analisis nyata |
| FRICTION-007 | **HIGH** | 5 | Step 3 tidak ada opsi skip/fallback — user terjebak infinite "Coba Lagi" |
| FRICTION-009 | **HIGH** | 7 | Outlet tab tidak menampilkan outlet yang sudah dipilih saat trial |
| FRICTION-005 | MEDIUM | 3 | AI Advisor di preview hanya placeholder "AI" |
| FRICTION-008 | MEDIUM | 5 | Step 4 (WOW Moment) tidak bisa diuji karena terblokir |
| FRICTION-010 | MEDIUM | 7 | Performa tab kosong — tidak bisa validasi fitur comparison |

---

## 5. Delta vs Baseline EPIC-001

**EPIC-001 selesai (DISC-001 s/d DISC-004):**

| DISC | Perbaikan | Status di Round 2 |
|---|---|---|
| DISC-001 | Konsistensi data (default "Semua Waktu") | ✅ Terverifikasi — semua halaman default "Seluruh Waktu" |
| DISC-002 | Place ID normalization | ✅ Tidak ada error place ID |
| DISC-003 | UX: loading indicator, error state | ✅ Terverifikasi — search loading ada, preview error state informatif |
| DISC-004 | No-blank-state, status banners | ✅ Terverifikasi — source banner di search, empty states di semua chart |

**Perubahan dari baseline:**
- DISC-004 empty states semua berfungsi — tidak ada white screen atau spinner tanpa pesan
- UX flow search→preview→CTA sudah mulus sampai ke register
- Source banner informatif: user tahu data dari cache/fallback
- **Tapi 2 Critical baru ditemukan** yang tidak terkait DISC manapun: broken link dan Flask error di trial step 3

---

## 6. Apakah Milestone M1 Tercapai?

**❌ TIDAK.**

Syarat M1:
- ❌ **7/7 PASS** → Hanya 4/7 PASS, 2 FAIL, 1 PARTIAL
- ❌ **0 Critical** → Ada 2 Critical (FRICTION-001, FRICTION-006)
- ❌ **0 High** → Ada 4 High (FRICTION-002, FRICTION-003, FRICTION-007, FRICTION-009)

---

## 7. Rekomendasi Menuju M1

### Prioritas 1 — Critical (harus fix sebelum M1)

1. **FRICTION-001:** Ganti semua `href="/register"` → `href="/auth/register"` di:
   - `app/templates/landing/preview.html`
   - `app/templates/landing/index.html`
   - Template lain yang mengandung CTA register

2. **FRICTION-006:** Perbaiki endpoint `/trial/activate/step3/start` — Flask `app_context` error kemungkinan karena background task thread tidak punya app context. Wrap dengan `app.app_context()` atau gunakan `current_app._get_current_object()`.

### Prioritas 2 — High (harus fix sebelum M1)

3. **FRICTION-007:** Tambahkan opsi "Lewati sinkronisasi →" di step 3 trial. Endpoint `/trial/skip` sudah ada — tinggal tambahkan link/button di template step 3.

4. **FRICTION-002:** Tambahkan toggle show/hide password di:
   - `auth/register.html` step 1
   - `auth/login.html`

5. **FRICTION-003:** Ganti placeholder "Masalah Utama" di preview publik dengan konten minimal — misalnya summary generik: "Berdasarkan 1280 review publik, sentimen pelanggan umumnya positif. Masalah utama akan terlihat setelah aktivasi." Jangan teks "tanpa rekomendasi PIC atau tindakan".

6. **FRICTION-009:** Perbaiki Outlet tab — tampilkan outlet yang sudah dipilih saat trial meskipun belum ada review.

### Prioritas 3 — Nice to Have

7. **FRICTION-005:** Isi AI Advisor preview dengan minimal summary.
8. **FRICTION-008:** Setelah step 3 fixed, validasi step 4 (WOW Moment).
9. **FRICTION-010:** Setelah outlet muncul, validasi fitur comparison.

---

## 8. Technical Debt (tidak blocking M1)

- Konsolidasi `normalize_place_id()` ke shared utility (DISC-002 follow-up)
- Apify timeout 8s terlalu rendah — pertimbangkan 15-20s untuk production

---

## 9. Verdict Final

```
GATE AC ROUND 2: BLOCKED
Critical: 2  |  High: 4  |  Medium: 3
Skenario PASS: 4/7  |  FAIL: 2  |  PARTIAL: 1
Rekomendasi: Fix 2 Critical + 4 High → Round 3
Estimasi effort: 2-4 jam engineering
```

---

**Laporan dibuat oleh:** Hermes (automated)  
**Waktu selesai:** 4 Agustus 2026, 15:15 WIB  
**Session ID:** GATE-AC-ROUND-2
