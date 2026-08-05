# GATE AC: Product Validation

**Version:** 1.0  
**Status:** ACTIVE  
**Audience:** Product Team, QA, Owner (Ismal)  
**Purpose:** Validasi end-to-end GRM dari perspektif owner bisnis — memastikan setiap Acceptance Criteria tidak hanya lulus secara teknis, tetapi **berguna secara nyata** bagi owner UMKM.

---

## 1. Prinsip Validasi

### 1.1 Mindset

| Bukan | Tapi |
|---|---|
| "Tombol bisa diklik" | "Owner tahu apa yang terjadi setelah klik" |
| "Data muncul di database" | "Owner melihat value dalam <3 menit" |
| "Error message ada" | "Owner tidak panik dan tahu langkah selanjutnya" |
| "Responsive di 375px" | "Owner bisa pakai sambil pegang HP satu tangan" |

### 1.2 Aturan Validasi

1. **Pakai data bisnis asli** (Bubur Fay, atau bisnis nyata lain yang disetujui). Jangan data dummy.
2. **Jangan jadi engineer.** Berpikirlah seperti owner restoran yang baru pertama kali pakai.
3. **Catat SEMUA friction** — sekecil apa pun. "Agak bingung" = friction.
4. **Jangan menjustifikasi bug.** Kalau ada yang salah, catat. Tidak ada "tapi kan emang belum diimplementasi."
5. **Setiap langkah harus punya kriteria sukses**. Tidak boleh "kira-kira berhasil."

---

## 2. Skenario Uji Coba Nyata (7 Skenario)

---

### SKENARIO 1: Pertama Kali Membuka Website

**Persona:** Owner UMKM dapat link GRM dari teman WhatsApp.

**Langkah:**
1. Buka `http://43.134.112.7:8083` di HP.
2. Lihat halaman pertama yang muncul.
3. Scroll dari atas ke bawah.
4. Coba pahami: "ini aplikasi apa? buat saya atau bukan?"

**Kriteria Sukses:**
- [ ] Dalam 10 detik pertama, owner bisa menjawab: "Ini aplikasi untuk memantau review Google bisnis saya."
- [ ] Dalam 30 detik, owner bisa menjawab: "Saya bisa coba gratis tanpa kartu kredit."
- [ ] Ada CTA utama yang jelas — tidak ada 5 tombol berbeda yang membingungkan.
- [ ] Teks terbaca jelas di HP (tidak terlalu kecil, tidak kepotong).
- [ ] Tidak ada horizontal scroll di 375px.
- [ ] Tidak ada loading spinner lebih dari 3 detik.
- [ ] Tidak ada error console (cek browser console).

**Friction Checklist:**
| Friction | Severity | Catatan |
|---|---|---|
| Tidak tahu ini aplikasi apa dalam 10 detik | Critical | Gagal UVP — visitor bounce |
| CTA tidak jelas (lebih dari 2 tombol primary) | High | Owner bingung harus klik yang mana |
| Teks terlalu kecil / tidak terbaca di HP | High | Owner menyerah sebelum baca |
| Load >3 detik di koneksi 4G | Medium | Kesan lambat = tidak profesional |
| Horizontal scroll di 375px | Medium | Mobile-first gagal |

---

### SKENARIO 2: Mencari Bisnis Sendiri

**Persona:** Owner restoran "Bubur Fay" penasaran apakah bisnisnya ada di GRM.

**Langkah:**
1. Klik CTA utama di landing (mis. "Coba Gratis" atau "Cari Bisnis Anda").
2. Ketik "Bubur Fay" di search box.
3. Lihat hasil pencarian.
4. Pilih salah satu outlet.
5. Lihat preview analisis.

**Kriteria Sukses:**
- [ ] Search box langsung terlihat, tidak perlu scroll jauh.
- [ ] Bisa ketik dan search dalam <2 detik setelah halaman load.
- [ ] Hasil pencarian muncul dalam <5 detik.
- [ ] Setidaknya 1 outlet Bubur Fay muncul.
- [ ] Owner bisa membedakan outlet satu dengan yang lain (nama + alamat jelas).
- [ ] Ada indikator jumlah review & rating untuk setiap hasil.
- [ ] Kalau tidak ada hasil: pesan jelas, bukan layar kosong.
- [ ] Owner tidak perlu login untuk melihat preview (jika preview publik sudah diimplementasi).

**Friction Checklist:**
| Friction | Severity | Catatan |
|---|---|---|
| Search box tidak terlihat di atas fold | Critical | Visitor tidak tahu harus ngapain |
| Hasil pencarian >5 detik | High | Owner mengira aplikasi hang |
| Hasil tidak relevan (bisnis lain) | Critical | Trust hilang — "ini data ngasal" |
| Tidak ada hasil sama sekali untuk bisnis nyata | Critical | Produk tidak berguna |
| Hasil tidak bisa dibedakan (nama mirip, alamat kurang) | High | Owner pilih outlet salah |
| Preview terlalu teknis / banyak angka | Medium | Owner tidak mengerti value |

---

### SKENARIO 3: Melihat Preview Analisis

**Persona:** Owner sudah menemukan outletnya dan ingin lihat "seperti apa sih analisisnya."

**Langkah:**
1. Klik outlet dari hasil pencarian.
2. Lihat halaman preview yang muncul.
3. Scroll konten preview.
4. Coba pahami: "apa yang GRM kasih tahu tentang bisnis saya?"
5. Temukan dan klik CTA untuk lanjut.

**Kriteria Sukses:**
- [ ] Preview menampilkan BUKAN hanya review mentah — ada analisis/ringkasan.
- [ ] Owner bisa lihat rating dan jumlah review outlet tersebut.
- [ ] Ada insight yang membuat owner berpikir "oh iya juga ya" — bukan generic.
- [ ] Ada CTA yang jelas: "Daftar Gratis untuk Lihat Selengkapnya" atau sejenisnya.
- [ ] Preview tidak menampilkan data bisnis orang lain (tenant isolation).
- [ ] Teks preview terbaca di HP.
- [ ] Tidak ada error 500 / stack trace.

**Friction Checklist:**
| Friction | Severity | Catatan |
|---|---|---|
| Preview kosong / hanya "Belum ada data" | Critical | Tidak ada value — visitor bounce |
| Preview hanya review mentah tanpa analisis | High | Tidak beda dari Google Maps |
| CTA tidak ada / tersembunyi | Critical | Visitor tidak tahu langkah selanjutnya |
| Insight generic ("tingkatkan pelayanan") | Medium | Tidak可信 — "AI cuma ngasal" |
| Data salah / bukan bisnis yang dicari | Critical | Fatal |

---

### SKENARIO 4: Registrasi

**Persona:** Owner sudah lihat preview, tertarik, dan ingin daftar.

**Langkah:**
1. Klik CTA dari preview.
2. Isi form step 1: email, password, nama.
3. Lihat validasi real-time (password minimal 8 karakter?).
4. Klik "Lanjut".
5. Isi form step 2: nama brand, nama bisnis, kota.
6. Lihat badge "✅ 14 hari gratis · tanpa kartu kredit".
7. Klik "Mulai Coba Gratis".
8. Lihat halaman setelah submit.

**Kriteria Sukses:**
- [ ] Step indicator jelas (1/2 → 2/2).
- [ ] Validasi langsung muncul saat ketik (bukan setelah submit).
- [ ] Password bisa di-toggle (show/hide) — penting untuk mobile.
- [ ] Tidak ada verifikasi email. Langsung bisa lanjut.
- [ ] Tidak ada field kartu kredit di step manapun.
- [ ] Brand, bisnis, dan kota yang diisi muncul benar di step 2.
- [ ] Setelah submit → langsung masuk (auto-login), TIDAK ke halaman "silahkan login."
- [ ] Loading maksimal 3 detik.
- [ ] Tidak ada error.

**Friction Checklist:**
| Friction | Severity | Catatan |
|---|---|---|
| Validasi baru muncul setelah submit | High | Owner harus isi ulang — frustrasi |
| Password tidak bisa di-toggle | Medium | Salah ketik, harus reset nanti |
| Ada verifikasi email | Critical | Tidak sesuai AC — drop-off tinggi |
| Ada field kartu kredit di form | Critical | Owner curiga "ini trial beneran gratis?" |
| Setelah submit → halaman login | Critical | Owner bingung "saya sudah daftar apa belum?" |
| Loading >3 detik setelah submit | Medium | Kesan lambat |
| Error saat submit tanpa pesan jelas | High | Owner tidak tahu cara memperbaiki |

---

### SKENARIO 5: Trial Activation

**Persona:** Owner baru selesai daftar. Dapat 14 hari trial. Ingin segera lihat analisis bisnisnya sendiri.

**Langkah:**
1. Lihat halaman Trial Welcome.
2. Baca sisa hari trial, jumlah outlet (0/1).
3. Lihat checklist 4 langkah.
4. Klik "Mulai Aktivasi" atau "Lewati."
5. Jika "Mulai Aktivasi":
   - Step 1: Cari bisnis → pilih outlet
   - Step 2: Verifikasi outlet
   - Step 3: Sync review (lihat progress bar)
   - Step 4: WOW Moment (lihat AI Advisor)
6. Jika "Lewati": buka dashboard kosong dengan banner trial.
7. Tutup browser. Buka lagi. Login. Verifikasi bisa resume.

**Kriteria Sukses:**
- [ ] Trial Welcome muncul setelah registrasi, BUKAN dashboard kosong.
- [ ] Sisa hari trial ditampilkan akurat (14 hari dari `created_at`).
- [ ] Outlet count: "0/1" saat baru daftar.
- [ ] Checklist 4 langkah terlihat dengan status pending/completed.
- [ ] CTA "Mulai Aktivasi" jelas dan hanya satu.
- [ ] Link "Lewati" ada tapi tidak dominan (bukan tombol).
- [ ] Step 1: search outlet berfungsi, hasil bisa dipilih.
- [ ] Step 2: detail outlet benar (nama, alamat, rating, jumlah review).
- [ ] Step 3: progress bar real-time (tidak freeze), ada angka review tersimpan.
- [ ] Step 4: AI Advisor menampilkan Prioritas Hari Ini — BUKAN error/kosong.
- [ ] **PENTING:** AI Advisor menampilkan insight SPESIFIK — misalnya "Pelayanan kurang ramah" + kutipan review asli — bukan generik.
- [ ] Ada confetti/celebration singkat di WOW Moment.
- [ ] Tombol "Lihat Dashboard" di Step 4 mengarah ke dashboard dengan data.
- [ ] Setelah setup_complete, dashboard bisa diakses tanpa redirect balik ke trial.
- [ ] **Resume:** Tutup browser saat di step 2 → login lagi → langsung ke step 2.
- [ ] Progress memory: setup_progress tidak hilang setelah logout/login.

**Friction Checklist:**
| Friction | Severity | Catatan |
|---|---|---|
| Trial Welcome tidak muncul → langsung dashboard kosong | Critical | Gagal AC-6 |
| Sisa hari salah (mis. 0 hari padahal baru daftar) | Critical | Timezone bug — owner panik |
| Checklist tidak update setelah selesai step | High | Owner mengira progress hilang |
| Progress bar freeze / tidak bergerak | High | Owner tidak tahu sync sedang berjalan |
| Sync makan waktu >3 menit | Medium | AC-29 gagal |
| AI Advisor kosong / error | Critical | Gagal AC-15 |
| AI Advisor insight generik | High | Owner tidak percaya AI — "cuma template" |
| Tidak ada celebration | Low | Nice-to-have tapi meningkatkan retensi |
| Resume gagal — kembali ke step 1 bukan step terakhir | Critical | Owner frustrasi harus ulang |
| Progress hilang setelah logout | Critical | Gagal AC-32 |
| Tidak ada trial banner setelah skip | High | Owner lupa status trial |
| Search outlet tidak menemukan bisnis nyata | Critical | Tidak bisa aktivasi |

---

### SKENARIO 6: AI Advisor (Pasca-Aktivasi)

**Persona:** Owner sudah selesai aktivasi. Sekarang ingin lihat "apa yang harus saya perbaiki hari ini."

**Langkah:**
1. Dari dashboard, klik "AI Advisor" di sidebar.
2. Lihat Prioritas Hari Ini.
3. Baca masalah yang ditampilkan.
4. Perhatikan: apakah ada PIC (siapa yang harus menangani)?
5. Perhatikan: apakah ada bukti (kutipan review, jumlah review, periode)?
6. Coba klik salah satu masalah.
7. Lihat apakah ada rekomendasi tindakan.
8. Refresh halaman. Lihat apakah data tetap sama (tidak hilang).

**Kriteria Sukses:**
- [ ] AI Advisor menampilkan minimal 1 prioritas (TIDAK kosong).
- [ ] Setiap prioritas memiliki: masalah, bukti (kutipan + jumlah + periode), PIC, severity.
- [ ] PIC spesifik: Crew / Supervisor / Kitchen / Owner — bukan "Team" generik.
- [ ] Setidaknya ada 1 prioritas dengan severity MENDESAK (jika data review memang punya masalah).
- [ ] Top Masalah Spesifik = sub-issues granular ("rasa berubah/basi", "judes", "lama") — bukan "pelayanan buruk" saja.
- [ ] Filter periode berfungsi: bisa lihat "Semua Waktu", "30 Hari Terakhir", atau custom.
- [ ] Tidak ada loading spinner abadi (>10 detik).
- [ ] Jika review terlalu sedikit → tampilkan pesan ramah, bukan error.
- [ ] Data tidak berubah/hilang setelah refresh.

**Friction Checklist:**
| Friction | Severity | Catatan |
|---|---|---|
| AI Advisor kosong padahal sudah sync sukses | Critical | Tidak ada value |
| Masalah terlalu generik ("tingkatkan pelayanan") | High | Tidak actionable |
| PIC tidak spesifik atau salah | High | Owner tidak tahu siapa yang harus bertindak |
| Tidak ada bukti (kutipan review palsu/tidak ada) | Critical | Kepercayaan hilang |
| Top Masalah Spesifik tidak muncul | Medium | Owner butuh detail untuk briefing tim |
| Filter periode tidak berfungsi | Low | Nice-to-have tapi mengurangi utilitas |
| Pesan kosong/error tidak ramah | Medium | Owner bingung dan keluar |
| Loading >10 detik | High | Owner menganggap error |

---

### SKENARIO 7: Dashboard

**Persona:** Owner ingin lihat gambaran besar: review semua outlet, perbandingan, performa.

**Langkah:**
1. Buka Dashboard.
2. Lihat statistik utama: total review, rating rata-rata, tren.
3. Perhatikan trial banner (jika masih trial).
4. Klik tab/banding outlet.
5. Coba bandingkan 2 outlet.
6. Coba filter per kota.
7. Coba ganti periode (Semua Waktu, Bulan Ini, Custom).
8. Refresh. Semua data tetap konsisten.

**Kriteria Sukses:**
- [ ] Dashboard tidak kosong setelah aktivasi.
- [ ] Statistik utama benar: total review, rating, tren sesuai data.
- [ ] Trial banner terlihat jelas (jika masih trial).
- [ ] Perbandingan outlet berfungsi: 2 outlet bisa dibandingkan side-by-side.
- [ ] Filter kota berfungsi: outlet dari kota berbeda muncul benar.
- [ ] Filter periode berfungsi: data berubah sesuai rentang.
- [ ] Semua halaman dashboard konsisten (label, format angka, warna).
- [ ] Tidak ada "undefined", "NaN", tag HTML mentah.
- [ ] Mobile: tabel perbandingan tidak horizontal scroll.

**Friction Checklist:**
| Friction | Severity | Catatan |
|---|---|---|
| Dashboard kosong setelah aktivasi | Critical | Tidak ada value |
| Statistik salah (rating tidak match Maps) | Critical | Data tidak bisa dipercaya |
| "undefined" / "NaN" di mana pun | High | Kesan tidak profesional |
| Tag HTML mentah terlihat | Medium | Developer tidak QA |
| Perbandingan outlet error | High | Fitur andalan tidak berfungsi |
| Filter kota menampilkan outlet salah | High | Data tidak akurat |
| Periode "Semua Waktu" bukan default | Medium | Preferensi owner: lihat total dulu |
| Mobile: tabel perbandingan horizontal scroll | High | AC-28 gagal |
| Data berubah setelah refresh | High | Inkonsistensi |
| Loading spinner abadi | High | Owner tidak bisa pakai |

---

## 3. Cara Mencatat Friction

### 3.1 Format

```
[FRICTION-###] [Severity] [Skenario #] Langkah # — Judul Singkat
Ekspektasi: (apa yang diharapkan owner)
Realita: (apa yang terjadi)
Dampak: (apa yang terjadi pada owner — bingung/marah/keluar?)
Screenshot: (link atau path)
Reproduksi: (langkah persis untuk memunculkan)
```

### 3.2 Contoh

```
[FRICTION-001] [Critical] [SKENARIO 5] Step 4 — AI Advisor kosong setelah sync sukses
Ekspektasi: AI Advisor menampilkan Prioritas Hari Ini dengan insight spesifik.
Realita: Layar putih, loading spinner hilang, tidak ada konten.
Dampak: Owner menyangka produk tidak berfungsi. Tidak ada nilai yang dirasakan.
Screenshot: /screenshots/friction-001.png
Reproduksi: Login → Trial Welcome → Step 1 pilih outlet → Step 2 konfirmasi → Step 3 sync selesai (100%) → Step 4 kosong.
```

---

## 4. Severity

| Severity | Definisi | Respon |
|---|---|---|
| **Critical** | Produk tidak bisa digunakan untuk mencapai value. Owner tidak mungkin lanjut. | Blocker rilis. Harus diperbaiki sebelum APPROVED. |
| **High** | Produk bisa digunakan tapi ada hambatan signifikan. Owner mungkin menyerah. | Harus diperbaiki sebelum rilis ke publik. Bisa APPROVED dengan catatan jika ada workaround. |
| **Medium** | Mengurangi kenyamanan atau kepercayaan. Owner tetap bisa pakai. | Bisa masuk backlog sprint berikutnya. Tidak memblokir APPROVED. |
| **Low** | Kosmetik atau nice-to-have. Tidak mengganggu alur utama. | Backlog low-priority. Tidak memblokir. |

**Aturan:**
- 0 Critical + 0 High = APPROVED
- 0 Critical + ≤3 High = APPROVED WITH NOTES
- 1+ Critical = BLOCKED
- ≥4 High = BLOCKED

---

## 5. Template Laporan Hasil Uji

```markdown
# Gate AC Product Validation Report

**Tanggal:** DD MMM YYYY  
**Penguji:** [Nama]  
**Lingkungan:** [Production / Staging / Local]  
**Browser:** [Chrome Mobile 375px / Desktop]  
**Data uji:** [Bubur Fay / Bisnis lain]  

---

## Ringkasan

| Metrik | Hasil |
|---|---|
| Total skenario | 7 |
| Skenario PASS (tanpa friction) | X |
| Skenario PASS (dengan catatan) | X |
| Skenario FAIL | X |
| Total friction ditemukan | X |
| Critical | X |
| High | X |
| Medium | X |
| Low | X |

---

## Hasil per Skenario

### SKENARIO 1: Pertama Kali Membuka Website
- Status: [PASS / PASS WITH NOTES / FAIL]
- Waktu: [detik]
- Friction: [daftar FRICTION-xxx]
- Catatan: ...

### SKENARIO 2: Mencari Bisnis Sendiri
- Status: [PASS / PASS WITH NOTES / FAIL]
- Waktu: [detik]
- Friction: [daftar FRICTION-xxx]
- Catatan: ...

### SKENARIO 3: Melihat Preview Analisis
- Status: [PASS / PASS WITH NOTES / FAIL]
- Waktu: [detik]
- Friction: [daftar FRICTION-xxx]
- Catatan: ...

### SKENARIO 4: Registrasi
- Status: [PASS / PASS WITH NOTES / FAIL]
- Waktu: [detik]
- Friction: [daftar FRICTION-xxx]
- Catatan: ...

### SKENARIO 5: Trial Activation
- Status: [PASS / PASS WITH NOTES / FAIL]
- Waktu ke WOW: [menit:detik]
- Friction: [daftar FRICTION-xxx]
- Catatan: ...

### SKENARIO 6: AI Advisor
- Status: [PASS / PASS WITH NOTES / FAIL]
- Waktu: [detik]
- Friction: [daftar FRICTION-xxx]
- Catatan: ...

### SKENARIO 7: Dashboard
- Status: [PASS / PASS WITH NOTES / FAIL]
- Waktu: [detik]
- Friction: [daftar FRICTION-xxx]
- Catatan: ...

---

## Daftar Friction (Lengkap)

| ID | Severity | Skenario | Deskripsi | Status |
|---|---|---|---|---|
| FRICTION-001 | Critical | 5 | AI Advisor kosong setelah sync | OPEN |
| FRICTION-002 | High | 7 | "undefined" di dashboard outlet | OPEN |
| ... | ... | ... | ... | ... |

---

## Verdict

| Verdict | Keterangan |
|---|---|
| [APPROVED / APPROVED WITH NOTES / BLOCKED] | [ringkasan alasan] |

---

## Rekomendasi

1. [rekomendasi 1]
2. [rekomendasi 2]
```

---

## 6. Checklist Eksekusi Cepat (Quick Run)

Untuk tes cepat tanpa laporan formal:

```
[ ] SKENARIO 1 — Landing: dimengerti <10 detik?    PASS / FAIL
[ ] SKENARIO 2 — Search: hasil relevan <5 detik?   PASS / FAIL
[ ] SKENARIO 3 — Preview: insight berguna?          PASS / FAIL
[ ] SKENARIO 4 — Register: 2 langkah, auto-login?   PASS / FAIL
[ ] SKENARIO 5 — Trial: sampai WOW <3 menit?       PASS / FAIL
[ ] SKENARIO 6 — AI Advisor: insight spesifik?      PASS / FAIL
[ ] SKENARIO 7 — Dashboard: data benar & konsisten? PASS / FAIL
```

---

## 7. Referensi

| Dokumen | Relevansi |
|---|---|
| `GRM-006_REGISTRATION_2STEP_DESIGN.md` | Skenario 4 |
| `GRM-007_TRIAL_ACTIVATION_DESIGN.md` | Skenario 5, AC-1 s/d AC-33 |
| `S1_CUSTOMER_ACQUISITION_LAYER_DESIGN.md` | Skenario 1–3, user journey |
| `02_GRM_POSITIONING_AND_MESSAGING.md` | UVP, positioning — dasar kriteria sukses Skenario 1 |
| `GRM_BACKLOG.md` | Konteks fitur non-trial |
