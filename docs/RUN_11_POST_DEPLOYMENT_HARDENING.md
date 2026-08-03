# RUN_11 — POST DEPLOYMENT HARDENING AUDIT

Tanggal: 2026-08-02
Base: commit 551026e (deploy) — live pilot Bubur Fay Bekasi (100 review Apify)
Sifat: audit menyeluruh pasca-deployment. TANPA fitur baru. Bug yang ditemukan diperbaiki.

---

## PHASE 1 — LIVE VALIDATION

| Item | Hasil | Bukti |
|---|---|---|
| 100 review muncul di dashboard | ✅ | `_base_reviews(all-period)` = 100, query 71ms |
| Sampling 20 review | ✅ | rating 20/20 valid (1–5), tanggal 20/20, masking 20/20; distribusi: 18×5⭐, 1×4⭐, 1×2⭐ (konsisten rating place 4.5); owner reply: 9/20 ada, 11/20 tidak |
| Owner reply & review context | ✅ | tersimpan (owner_reply_text/date); reviewContext/reviewDetailedRating di raw_payload |
| Duplicate setelah sync ketiga | ✅ | sync-3: inserted 0, skipped 1, total tetap 100 |
| Incremental tidak tarik ulang lama | ✅ | sync-3 hanya `received 1` (≥ since boundary), bukan 100 |

Catatan keterbatasan: perbandingan visual langsung dengan Google Maps tidak dilakukan otomatis
(URL review actor butuh sesi browser); validasi berbasis konsistensi internal + provenance Apify.
Rekomendasi: 1× spot-check manual owner ke Google Maps untuk konfirmasi visual.

## PHASE 2 — AI ADVISOR QUALITY

Evaluasi per dimensi (berbasis data live + Gate M dengan data negatif):

- Evidence cukup? ✅ — count + periode + 1–3 kutipan asli; rating-only excluded.
- PIC tepat? ✅ — mapping sesuai skill (Crew/Supervisor/Kitchen/Owner) teruji.
- Tindakan bisa dieksekusi? ✅ — 1–3 saran konkret per masalah.
- Terlalu generik? ⚠️ Sedang — beberapa saran (mis. "Standarisasi resep") generik namun actionable.
- Hallucination? ❌ Tidak ada — masalah hanya muncul dari kategori review nyata; 0 issues saat data positif.
- False positive? ⚠️ Rendah — sentiment rule-based bisa salah klasifikasi di kasus sarkasme; mitigated via `needs_human_review` pada count<2.

Tidak ada perubahan konsep (5-field terkunci dipertahankan). Perbaikan template (saran lebih spesifik) = prioritas Low, bukan bug.

## PHASE 3 — UX REVIEW ("30 detik, apa yang saya pahami?")

**Bug UX ditemukan & DIPERBAIKI**: dashboard index masih teks era RUN_04 — "Hubungkan akun Google Business Profile" + "fitur akan tersedia pada fase berikutnya" — menyesatkan untuk produk non-login. Fixed di `templates/dashboard/index.html` + `app/templates/dashboard/index.html` (ChoiceLoader memprioritaskan app/templates → keduanya disinkronkan): teks baru "tanpa login Google Business Profile" + link ke Advisor. Terverifikasi render 200.

Yang membingungkan / friction lain (belum diperbaiki — bukan bug, usulan):
1. Dashboard index hanya 3 angka statistik; tidak ada navigasi jelas ke analitik/advisor (base nav perlu ditambah link).
2. Istilah "Issue Terbuka" tidak dijelaskan; untuk owner UMKM lebih baik "Keluhan yang perlu ditindak".
3. Advisor halaman bagus tapi tanpa penjelasan "mengapa ini muncul" (sumber: review 30 hari).
4. Tidak ada tombol "Sync Sekarang" di UI (sync hanya via API) → owner tidak bisa memicu refresh sendiri.

## PHASE 4 — PERFORMANCE

| Operasi | Waktu | Keterangan |
|---|---|---|
| Discovery (actor run) | ±40–60s | actor run + poll; biaya ±$0.02/10 places |
| Review sync (100 review) | ±40s (full) / 22s (incremental) | didominasi actor run + poll; BUKAN DB |
| AI analysis (rule-based, 58 text) | <1s | post-sync, tidak jadi bottleneck |
| Render/query dashboard (all-period) | 71ms | JOIN Review+Outlet cepat; tidak ada query lambat |

Bottleneck utama: **actor run latency (22–60s)** — inherent provider, bukan bug. Optimasi mungkin:
run cache per (place,since) sudah ada; untuk refresh rutin bisa jadwal sync berkala (roadmap, bukan fitur baru sekarang).

## PHASE 5 — PRODUCTION READINESS

| Area | Status | Catatan |
|---|---|---|
| Backup | ✅ | pg_dump otomatis sebelum deploy; file di /tmp (bukan repo) |
| Recovery | ⚠️ | backup ada, tapi DRLL belum pernah diuji restore |
| Logging | ✅ | log service + SyncReport + AuditLog; token tidak pernah di-log |
| Retry | ✅ | 429/5xx backoff (Outscraper & Apify), no-retry 401/403 |
| Timeout | ✅ | per-provider timeout + poll deadline |
| Cache | ⚠️ | run-cache per instance saja; belum cache dashboard/query |
| Pagination | ✅ | dataset + explorer + export |
| Health check | ✅ | /health 200 |
| Monitoring | ⚠️ | belum ada alert (disk/cost/actor-fail); hanya log |
| Graceful failure | ✅ | rollback per outlet; data lama dipertahankan; no silent fallback |

## PHASE 6 — GTM READINESS

"Owner restoran yang belum pernah memakai GRM bisa…?"

1. Menambahkan outlet — ⚠️ **friction**: UI discovery masih memakai mock search; belum ada flow self-service discovery+verify untuk provider apify (hanya API).
2. Menjalankan sync — ❌ **friction**: tidak ada tombol/UI; perlu API/CLI.
3. Melihat dashboard — ✅ bisa (index + advisor render; login dengan akun owner).
4. Mengerti AI Advisor — ✅ format sederhana, bahasa Indonesia, 5 kolom.
5. Mengambil tindakan — ✅ saran actionable + PIC; status Open (belum workflow).

**Kesimpulan**: belum siap self-service penuh untuk customer tanpa pendampingan. Siap untuk
**pilot customer dengan onboarding assisted** (Hermes/owner melakukan discovery+sync).

---

## PRIORITAS PERBAIKAN

**Critical** — tidak ada (tidak ditemukan bug kritis; data aman, test hijau, deploy stabil).

**High**
1. UI self-service: tombol Discovery + Verify + Sync (provider apify) — friction GTM utama.
2. Monitoring/alert dasar (sync gagal, cost threshold, disk).

**Medium**
3. Konsolidasi template duplikat (app/templates vs root templates/) — sudah terbukti menyebabkan divergensi; jadikan satu sumber.
4. Nav bar: link Analitik + Advisor dari dashboard.
5. Recovery drill (uji restore backup sekali).

**Low**
6. Penyempurnaan teks saran AI Advisor (kurangi generik).
7. Rename UI "Issue Terbuka" → istilah lebih ramah owner.
8. Penjelasan "mengapa rekomendasi ini muncul" di Advisor.
9. Cache query dashboard (Redis/memoized) — belum perlu di skala pilot.

## ROADMAP IMPLEMENTASI

- **M1 (High)**: UI discovery/verify/sync apify + nav link + monitoring alert.
- **M2 (Medium)**: konsolidasi template + recovery drill + dashboard polish.
- **M3 (Low)**: teks advisor + cache + dokumentasi GTM.

## ESTIMASI EFFORT

- High: 1–2 hari (UI flow + endpoint verify/sync sudah ada; tinggal frontend + tombol).
- Medium: 0.5–1 hari (template cleanup, nav, drill restore).
- Low: 0.5 hari (teks, cache sederhana).

## REKOMENDASI

**Layak dipakai pilot customer DENGAN onboarding assisted** — dashboard + AI Advisor + data live
berfungsi dan teruji; namun UI self-service discovery/sync (High) harus ada sebelum skala lebih luas.
Tidak direkomendasikan self-service penuh tanpa M1.

---

## PERUBAHAN DILAKUKAN (hanya bug)

- `templates/dashboard/index.html` + `app/templates/dashboard/index.html`: teks onboarding menyesatkan (referensi Google Business Profile / fitur fase berikutnya) → diperbaiki ke flow non-login + link Advisor.
- Tidak ada fitur baru; konsep AI Advisor tidak diubah.

## COMMIT

- commit: `e1c5212` fix: correct post-deployment dashboard onboarding copy · working tree: clean
