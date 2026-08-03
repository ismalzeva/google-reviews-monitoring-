# RUN_Q1 — DATA CONSISTENCY AUDIT

Tanggal: 2026-08-03
Status: AUDIT ONLY — DO NOT FIX
Kasus: Dashboard Bekasi (Rating 4.48, Review 438) vs Performance 1v1 Bekasi (Rating 5, Review 1)

---

## A. DIAGRAM ALUR DATA

```
Review Provider (Apify crawler-google-places)
        ↓  sync_public_reviews() — insert/upsert ke tabel `reviews`
Database (PostgreSQL grm_db — tabel: reviews, outlets, review_analyses, sync_reports)
        ↓  analyze_review() — rule-based → tabel review_analyses
Layanan analytics (public_analytics.py, ai_advisor.py) — semua baca tabel sama
   ├── executive_summary → Dashboard
   ├── branch_breakdown → Dashboard "Performa Outlet" + Performance outlets + Compare
   ├── city_performance → Performance per-kota
   ├── outlet_performance → Performance ranking
   ├── compare_outlets → Performance 1v1
   ├── review_explorer → Review Terbaru
   └── ai_advisor.generate → AI Advisor
UI: Dashboard (server-render) · Performance (JS fetch API) · Advisor (JS fetch API)
```

**PENTING:** SEMUA layanan membaca **tabel yang sama** (`reviews` JOIN `outlets`) — tidak ada beda tabel.

---

## B. TABLE SOURCE OF TRUTH

| Halaman | Endpoint | SQL / Sumber | Table | Filter default | Aggregation | Status |
|---|---|---|---|---|---|---|
| Dashboard (header outlet) | `GET /dashboard/` (render) | `Outlet.query` (monitor_enabled) | outlets | — | — | ⚠️ pakai `business_review_count` (metadata Google) |
| Dashboard (KPI Review) | `GET /dashboard/` (render) | `executive_summary()` → `_base_reviews()` | reviews JOIN outlets | **Semua Waktu** | count, avg rating | ✅ |
| Dashboard (Rating KPI) | `GET /dashboard/` (render) | `executive_summary()` | reviews+analyses | Semua Waktu | avg | ✅ |
| Dashboard (Performa panel) | `GET /dashboard/` (render) | `branch_breakdown()` | reviews JOIN outlets | Semua Waktu | group by outlet | ✅ |
| Performance (ranking) | `GET /api/public/analytics/outlets` | `outlet_performance()` → `branch_breakdown()` | reviews JOIN outlets | **30 hari** (JS default) | group by outlet | ⚠️ default beda |
| Performance (1v1) | `GET /api/public/analytics/compare` | `compare_outlets()` → `branch_breakdown()` | reviews JOIN outlets | **30 hari** (JS default) | group by outlet | ⚠️ default beda |
| Performance (per kota) | `GET /api/public/analytics/cities` | `city_performance()` → `_base_reviews()` | reviews JOIN outlets | 30 hari | group by city | ⚠️ default beda |
| Outlet page | `GET /dashboard/outlets` (render) | `Outlet.query` + SyncReport | outlets | — | — | ⚠️ `business_review_count` |
| AI Advisor | `GET /api/public/advisor` | `ai_advisor.generate()` | reviews JOIN outlets + analyses | **Semua Waktu** (start_date=2000) | group (outlet,category), filter rating<4 & negatif/mixed | ✅ |

SQL inti (semua endpoint sama):
```
SELECT reviews.*, outlets.*
FROM reviews JOIN outlets ON reviews.outlet_id = outlets.id
WHERE reviews.tenant_id = :t AND reviews.business_id = :b
  AND reviews.create_time >= :start [AND <= :end]
-- lalu agregasi Python: count, avg(rating), sentimen via review_analyses, group per outlet/kota/kategori
```

---

## C. ROOT CAUSE ANALYSIS

### RC-1 (PENYEBAB UTAMA kasus yang dilaporkan): Beda filter periode antar halaman
- **Dashboard** default → **"Semua Waktu"** (start=2000) → Bekasi: **438 review, avg 4.48**
- **Performance & Compare** default → **30 hari** (`periodQs()` di performa.html mengirim `days=30`) → Bekasi: **1 review (30 hari), avg 5.0**
- Kedua angka BENAR untuk periodenya masing-masing, tapi halaman menampilkan default periode berbeda → terlihat inkonsisten.
- Dataset sumber **sama** (tabel `reviews`); yang beda hanya **WHERE create_time**.

### RC-2: Label "Review" di header dashboard & halaman Outlet = metadata Google, bukan DB
- Header dashboard `outlets[0].review_count` dan halaman Outlet `business_review_count` berasal dari **`outlets.business_review_count`** (metadata dari Google Maps saat discovery/verify).
- KPI "Review" di dashboard = **count tabel `reviews`** (DB).
- Untuk Bekasi keduanya 438 (kebetulan sama karena semua review di-sync). Untuk outlet yang sync-nya terbatas/belum penuh, **angka bisa beda** → label sama tapi makna beda.

### RC-3: Data test polusi (ditemukan saat audit)
- `Test Outlet A` (TST-X1) & `Test Outlet C` (TST-X3) ada di DB live — artefak debugging bug Konfirmasi (verify fixture). Bukan data produksi; perlu dihapus.

### RC-4 (tidak terjadi, tapi berpotensi): beda business_id/place_id
- Semua outlet tenant-a-i/biz-a-i, place_id unik & benar (Bekasi `ChIJM_0...`, RTM `ChIJV1Rh...`). Tidak ada duplikasi place_id.

---

## D. PERBANDINGAN ANGKA (Bekasi & RTM, terverifikasi)

| Sumber | Bekasi (all-time) | Bekasi (30 hari) | RTM (all-time) | RTM (30 hari) |
|---|---|---|---|---|
| Dashboard summary | 438 / 4.48 | 1 / 5.0* | 71 / 4.83 | 1 / 4.0* |
| Performance outlets | 438 / 4.48 | 1 / 5.0 | 71 / 4.83 | 1 / 4.0 |
| Compare 1v1 | 438 / 4.48 | 1 / 5.0 | 71 / 4.83 | 1 / 4.0 |
| Outlet page (metadata) | 438 (business_review_count) | — | 71 | — |
| AI Advisor | bukti dari review tersimpan | — | — | — |

*30 hari: hanya 1 review per outlet → avg = rating review tunggal itu.

**Kesimpulan angka:** semua sumber KONSISTEN **jika periode sama** (all-time: 438/4.48; 30d: 1/5.0). Inkonsistensi yang dilihat = perbedaan default filter antar halaman.

---

## E. REKOMENDASI PERBAIKAN (DO NOT IMPLEMENT — hanya saran)

1. **Samakan default periode antar halaman** — semua default "Semua Waktu" (atau tampilkan label periode aktif yang jelas di tiap halaman, misal badge "30 hari" di Performance/Compare).
2. **Beri label berbeda** untuk angka metadata vs DB: header outlet "Total di Google: 438" vs KPI "Review tersimpan: 438".
3. **Tambahkan indikator periode** di Performance/Compare (dropdown sudah ada; pastikan default & label terlihat jelas).
4. **Bersihkan data test** (Test Outlet A/C — TST-X1/X3) dari DB live.
5. (Opsional) **Satu source of truth service** untuk angka outlet (query terpusat) agar tidak ada divergensi di masa depan.
6. (Opsional) **Sinkronisasi lengkap** untuk outlet yang belum 100% — agar business_review_count = DB count.

---

STOP — audit selesai. Tidak ada perbaikan yang diterapkan.
