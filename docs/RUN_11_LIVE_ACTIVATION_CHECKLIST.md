# RUN_11 — LIVE ACTIVATION CHECKLIST (Outscraper)

Status: BLOCKED — `OUTSCRAPER_API_KEY` belum tersedia
Diperbarui: 2026-08-02

> Jangan klaim live sebelum semua item di bawah selesai. Jangan pernah
> menaruh API key di repository / log / completion report.

## Prasyarat Akun

- [ ] 1. Daftar/punya akun Outscraper → https://app.outscraper.com
- [ ] 2. Salin API key dari dashboard (format `sk-...`)
- [ ] 3. (Opsional) Cek kuota/cost plan — pastikan cukup untuk pull 50–100 review per outlet

## Konfigurasi Server (VPS 43.134.112.7)

- [ ] 4. Set key di `.env` GRM dengan mode aman:
      ```bash
      cd /home/ubuntu/google-reviews-monitoring
      echo 'OUTSCRAPER_API_KEY=sk-...' >> .env   # ganti dengan nilai asli
      echo 'PUBLIC_REVIEW_PROVIDER=outscraper' >> .env
      chmod 600 .env
      ```
- [ ] 5. Pastikan `.env` TIDAK tracked: `git ls-files | grep '^\.env$'` → kosong
- [ ] 6. Cek env aman: `PUBLIC_REVIEW_TIMEOUT=30`, `PUBLIC_REVIEW_MAX_RETRIES=3`,
      `PUBLIC_REVIEW_PAGE_SIZE=100`, `PUBLIC_REVIEW_MAX_REVIEWS=100` (batasi initial pull)
- [ ] 7. Restart app: `kill <pid>; cd /home/ubuntu/google-reviews-monitoring && venv/bin/python run.py &`
- [ ] 8. Verifikasi: `curl -s http://127.0.0.1:8083/api/public/locations` (login dulu)
      → `configured_provider` harus `outscraper`

## Pilot (Bubur Fay — Depok)

- [ ] 9. Discovery: `POST /api/public/discover {"query":"Bubur Fay","city":"Depok"}`
- [ ] 10. Verify lokasi Depok: `POST /api/public/verify {"candidate_id":"...","decision":"owner_confirmed"}`
      (HARUS pakai kandidat "Bubur Fay Depok" / Margonda — JANGAN Harjamukti)
- [ ] 11. Catat identitas lokasi:
      - Business name: `Bubur Fay Depok`
      - Maps URL: `https://www.google.com/maps/place/?q=place_id:ChIJ0-depok-margonda-001`
      - Place ID: `ChIJ0-depok-margonda-001`
      - Kota/Kabupaten: Depok (Jawa Barat)
      - Kecamatan: ditentukan via geo enrichment / provider

## Live Collection

- [ ] 12. Sync pertama (terbatas): `POST /api/public/sync {"outlet_ids":["..."]}`
      → catat `received`, `inserted`, `updated`, `skipped`, `failed`, `pages`, `duration`
- [ ] 13. Sync kedua (incremental): `POST /api/public/sync {"outlet_ids":["..."]}`
      → `inserted` harus 0, `skipped` > 0 (tidak menggandakan)
- [ ] 14. `full_sync` terbatas: `POST /api/public/sync {"outlet_ids":["..."],"full_sync":true}`
      → verifikasi update detection

## Validasi Data (manual — evidence nyata)

- [ ] 15. Lokasi sesuai outlet (nama/alamat/maps_url benar)
- [ ] 16. `source_review_id` stabil antar sync
- [ ] 17. Rating & tanggal masuk akal; text tidak tertukar
- [ ] 18. Owner reply terambil bila tersedia
- [ ] 19. Rating-only tersimpan benar (has_text=false)
- [ ] 20. Reviewer name termasking (pola `Nama B***`)
- [ ] 21. Source label = `outscraper`; provenance tersimpan (ReviewRawPayload)
- [ ] 22. Kota/kabupaten benar; kecamatan benar atau `unknown` (jangan mengarang)
- [ ] 23. Tidak ada review silang antar-cabang; tidak ada duplicate
- [ ] 24. Dashboard: summary/kategori/cabang/geografi/periode/explorer/priority
- [ ] 25. Export CSV/XLSX dengan filter uji:
      (a) rentang waktu tertentu; (b) kombinasi kota/kabupaten + kecamatan + kategori

## Audit Record

- [ ] 26. Simpan live-pilot audit record (provider, timestamp, outlet, limit,
      received/inserted/updated/skipped/failed, duration, pages, redacted error) —
      di completion report, TANPA secret
- [ ] 27. Jangan commit raw response live ke repo; raw payload hanya di DB
      (ReviewRawPayload) tanpa API key/header

## Selesai

- [ ] 28. Update completion report RUN_11 → status `completed` / `completed_with_limitations`
- [ ] 29. Jangan mulai RUN_12
