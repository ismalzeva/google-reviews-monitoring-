# GRM UI Polish Backlog

Version: 1.0
Status: Backlog (Post-MVP)

## Purpose
Kumpulan improvement UI/UX non-kritikal yang ditunda setelah GRM-001 (Landing Page Redesign). Tidak satu pun item di sini menghalangi MVP — semua adalah polish untuk meningkatkan konversi dan pengalaman.

## Rule
- Tidak diimplementasikan tanpa instruksi eksplisit
- Prioritas berdasarkan impact-to-effort ratio
- Setiap item wajib memiliki acceptance criteria singkat

---

## Priority: HIGH (impact besar, effort kecil)

### POL-001: Smooth scroll nav links
- **Area:** Landing — nav links ("Fitur", "Cara Kerja", "Demo", "Harga", "FAQ")
- **Issue:** Klik nav link melakukan navigasi ke halaman terpisah (/features, /demo, dll) — seharusnya smooth-scroll ke section yang sama di landing
- **AC:** Klik nav link di landing → smooth scroll ke section terkait (bukan page reload)

### POL-002: FAQ accordion — open first item by default
- **Area:** Landing — FAQ section
- **Issue:** Semua FAQ tertutup saat load; user harus klik satu per satu
- **AC:** Item FAQ pertama terbuka otomatis saat page load

### POL-003: Demo Preview — angka real-time
- **Area:** Landing — Demo Preview (contoh/sandbox)
- **Issue:** Data statis; akan lebih impactful jika angka sedikit dianimasikan (count-up)
- **AC:** Angka (438, 4.5, 3, 72%) count-up saat section masuk viewport

### POL-004: Trust bar — ganti teks dengan angka
- **Area:** Hero — trust row
- **Issue:** Trust items hanya teks ("Tanpa login Google Business", "Data review publik", dll) — perlu 1-2 social proof angka
- **AC:** Tambah item "500+ bisnis dipantau" dengan angka yang menonjol

---

## Priority: MEDIUM (impact sedang, effort sedang)

### POL-005: Mobile hamburger menu
- **Area:** Nav — mobile
- **Issue:** Nav links hilang di mobile (<720px); user tidak bisa navigasi dari mobile
- **AC:** Hamburger icon di mobile → tap → expand menu vertikal dengan semua nav links

### POL-006: Feature cards — ikon kustom
- **Area:** Features section
- **Issue:** Menggunakan emoji (🎯 🏢 👥 📈); terlihat kurang premium
- **AC:** Ganti dengan Lucide SVG icons (target, building, users, trending-up) — warnai dengan orange #ff7a00

### POL-007: Pricing cards — hover elevation
- **Area:** Pricing section
- **Issue:** Cards statis; tidak ada feedback visual saat hover
- **AC:** Hover → card naik (translateY -4px) + shadow bertambah; transisi smooth

### POL-008: Demo Preview — visual chart
- **Area:** Demo Preview section
- **Issue:** Hanya stat cards + list teks; kurang visual
- **AC:** Tambah mini bar chart (CSS-only) untuk "Sentimen per bulan" atau "Top 3 Masalah"

### POL-009: Sticky nav — background transition
- **Area:** Nav
- **Issue:** Nav selalu putih semi-transparan; tidak ada perubahan saat scroll
- **AC:** Nav transparan di hero → jadi solid putih + shadow setelah scroll >100px

### POL-010: Search — autocomplete suggestion
- **Area:** Hero — search card
- **Issue:** Input polos; tidak ada suggestion saat user mengetik
- **AC:** Dropdown suggestion muncul setelah 2 karakter (bisnis fiktif untuk sekarang) + keyboard navigasi

---

## Priority: LOW (nice-to-have)

### POL-011: Hero — fade-in animation
- **Area:** Hero section
- **Issue:** Konten muncul instant; tidak ada entrance animation
- **AC:** Headline fade-in + slide-up 300ms; sub-hero 150ms delay; search card 300ms delay

### POL-012: Scroll-to-top button
- **Area:** Global — landing
- **Issue:** Landing panjang; user harus scroll manual ke atas
- **AC:** Floating button muncul setelah scroll >500px; klik → smooth scroll ke top

### POL-013: Pricing — annual/monthly toggle
- **Area:** Pricing section
- **Issue:** Hanya harga bulanan; annual discount bisa naikkan conversion
- **AC:** Toggle Bulanan/Tahunan; tahunan = diskon 20% + label "Hemat 20%"

### POL-014: Footer — social proof bar
- **Area:** Footer
- **Issue:** Footer polos; tidak ada trust signal
- **AC:** Tambah baris "GRM dibangun dengan transparansi — baca kebijakan privasi kami" + link

### POL-015: Loading skeleton — Demo Preview
- **Area:** Demo Preview section
- **Issue:** Konten langsung muncul; skeleton loading akan memberi kesan "data diproses"
- **AC:** Skeleton card muncul 1 detik → fade ke konten asli

### POL-016: Feature cards — ikon background color
- **Area:** Features section
- **Issue:** Ikon tanpa background; kurang definition
- **AC:** Tambah lingkaran background oranye pudar (#fff0e5) di belakang setiap ikon

### POL-017: Testimonial section
- **Area:** Landing (section baru antara Demo Preview dan Pricing)
- **Issue:** Tidak ada social proof dari pengguna nyata
- **AC:** 2-3 kutipan singkat + nama + bisnis; desain card horizontal

### POL-018: Trust badges — logos
- **Area:** Hero, di bawah search card
- **Issue:** Tidak ada recognizable trust signal (badge keamanan, partner)
- **AC:** Row logo kecil: "Review dari Google Maps" + "AI-powered" + "Data publik"

### POL-019: FAQ — search/filter
- **Area:** FAQ section
- **Issue:** 5 pertanyaan; saat nanti bertambah, user sulit cari
- **AC:** Input filter di atas FAQ list; real-time filter accordion items

### POL-020: Dark mode toggle
- **Area:** Global
- **Issue:** Hanya light mode
- **AC:** Toggle di nav; simpan preference di localStorage; CSS variables dark palette

---

## Summary

| Priority | Count | Est. Total Effort |
|----------|-------|--------------------|
| HIGH | 4 | 1-2 jam |
| MEDIUM | 6 | 3-5 jam |
| LOW | 10 | 5-8 jam |
| **Total** | **24** | **~15 jam** |

## GRM-003: Public Business Search Polish

Ditunda setelah GRM-003 selesai. Semua item non-kritikal.

### POL-021: Search results — input debounce
- **Area:** /search page — search bar
- **Issue:** Setiap perubahan input memerlukan submit manual; UX akan lebih baik dengan debounce auto-submit
- **AC:** Auto-submit setelah user berhenti mengetik 500ms (tetap pertahankan tombol "Cari →" untuk explicit submit)

### POL-022: Search results — address truncation mobile
- **Area:** /search — result cards
- **Issue:** Alamat panjang overflow di mobile (<400px); text-overflow:ellipsis sudah ada tapi layout kadang pecah
- **AC:** Test di 320px width; pastikan semua card kompak tanpa overflow

### POL-023: "Tidak ditemukan" — feedback tombol
- **Area:** /search — empty state
- **Issue:** Saat bisnis tidak ditemukan, user tidak bisa memberi sinyal "bisnis ini harusnya ada"
- **AC:** Tambah tombol kecil "Laporkan bisnis hilang" → endpoint no-op (future: kirim ke admin)

### POL-024: Rate limit — countdown timer
- **Area:** /search — rate limited state
- **Issue:** Pesan statis "Terlalu banyak pencarian" tanpa indikasi kapan bisa coba lagi
- **AC:** Tampilkan countdown mundur (sisa detik) sampai limit reset; auto-enable search input setelah reset

## Dependency
- Semua item independent dari GRM-002 s/d GRM-024
- Bisa dikerjakan kapan saja setelah MVP tercapai
- Tidak satu pun memengaruhi Core Platform
