# RUN_M1 — SELF-SERVICE ONBOARDING (MINIMUM LOVABLE PRODUCT)

Status: **selesai & deployed**
Tanggal: 2026-08-02
Base: RUN_11 (deploy 551026e) — GRM non-login Apify + AI Advisor

## Tujuan

Owner restoran bisa pakai GRM sendiri tanpa SSH/env/Postman/API:
`Nama bisnis/URL → Cari → Pilih outlet → Konfirmasi → Mulai Sinkronisasi → Selesai → Dashboard`.

## URL Onboarding

- Halaman: **`/onboarding/`** (login dulu; default di port 8083)
- API internal: `/onboarding/discover`, `/onboarding/verify`, `/onboarding/sync`, `/onboarding/status`

## Flow (terverifikasi live)

1. **Tambah Outlet** — input nama bisnis ATAU Google Maps URL + tombol **Cari**
2. **Discovery** — panggil provider (live: Apify Discovery Actor `compass/crawler-google-places`; dev/test: mock search). Tampilkan kandidat: nama, rating, jumlah review, alamat, kota, status buka/tutup + tombol **Pilih Outlet**
3. **Verification** — tampilkan nama, alamat, rating, jumlah review, Place ID + tombol **Konfirmasi**
4. **Sync** — background thread + progress polling (`/onboarding/status`): Discovery ✓ → review diterima → analisis → selesai. **Sudah pernah sync → tawarkan Incremental atau Full Sync**
5. **Selesai** — jumlah review diterima, baru, di-update, durasi + tombol **Lihat Dashboard** + **Prioritas Perbaikan**

Smoke live: `/onboarding/` 200 · discover "Bubur Fay" → 1 kandidat (Bubur Fay, ⭐4.5, 438 review, Bekasi) · verify → outlet Bubur Fay Bekasi, already_synced=True (benar → tawarkan Incremental/Full).

## Error Handling

- Discovery gagal/kosong → pesan jelas ("Tidak ada lokasi ditemukan. Coba nama lain.")
- Timeout → "Pencarian terlalu lama. Coba lagi sebentar."
- Sync gagal → "Terjadi kesalahan. Coba lagi." (tanpa stack trace)
- Tidak ada spinner abadi — semua request punya akhir (error atau done)

## AI ADVISOR

Tidak berubah. Konsep tetap: Outlet | Masalah | Bukti | Saran Tindakan | PIC.

## Batasan

Tidak ada fitur baru di luar onboarding; AI Advisor/analytics/provider/dashboard tidak diubah.
Progress store in-memory (`_SYNC_PROGRESS`) — cukup untuk skala pilot 1 user; untuk multi-user perlu store bersama (catatan, bukan fitur sekarang).

## Quality Gate N

- File: `tests/gate_n.py` (provider mock, deterministik, tanpa live HTTP)
- Tests: **13 PASS / 0 FAIL**
- Cakupan: page render, discovery success/empty/missing-input/timeout-friendly, choose+verify outlet, already_synced flag, sync success/incremental/full, sync fail friendly, progress update, dashboard link

## Regression B–N

- Result: **ALL PASS** (runner non-interaktif + proteksi DB)
- Exit codes: B=0 C=0 D=0 E=0 F=0 G=0 H8=0 I=0 J=0 K=0 L=0 M=0 N=0
- Total duration: 78s · **DB live aman: 100 → 100**

## Deployment

- Restart PID-specific (run/grm.pid) · health 200 · `/onboarding/` render 200
- Flow live terverifikasi via smoke (discover apify → verify)

## Commit

- `<commit>` (diisi setelah commit) · working tree: `<tree>`

## Screenshot

`/home/ubuntu/.hermes/cache/screenshots/browser_screenshot_abd4876b4f5d4deb97c335de37644bd2.png` (halaman Tambah Outlet)
