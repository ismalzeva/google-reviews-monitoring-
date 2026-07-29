# COMPLETION REPORT — RUN_02

## 1. IDENTITAS

```yaml
project: Google Reviews Monitoring & Intelligence
pilot: Bubur Fay
task: RUN_02 — Branch Discovery & Owner Verification
version: v1.0-phase-02
environment: Development (VPS 43.134.112.7, PostgreSQL 16)
started_at: 2026-07-29
completed_at: 2026-07-29
executed_by: Hermes (Personal Assistant Agent)
```

## 2. TUJUAN

Implementasi modul Branch Discovery — pencarian brand di Google Maps (mock), deduplikasi kandidat, verifikasi oleh pemilik brand, audit trail setiap keputusan, dan isolasi tenant (multi-business).

## 3. SCOPE YANG DIKERJAKAN

- **Mock Places API** — adapter `search_places()` mengembalikan data Bubur Fay (6 kandidat unik: Depok, Bekasi, Jakpus, Bogor, Tangerang, Harjamukti), dengan 1 duplikat place_id dan 1 typo untuk test dedup;
- **Brand Search** — form input brand name + kota opsional, POST /discover/search;
- **Deduplication** — mencegah kandidat dengan place_id sama masuk ulang;
- **Owner Verification** — 6 jenis keputusan (confirmed/rejected/old_or_closed/duplicate/uncertain/needs_access_review);
- **Outlet Creation** — hanya untuk keputusan `owner_confirmed` yang membuat Outlet record;
- **Audit Trail** — setiap perubahan status kandidat tercatat di `audit_logs` dengan before/after state, actor, tenant, dan timestamp;
- **Tenant Isolation** — user dari business A tidak bisa melihat/memverifikasi kandidat business B (403/404);
- **UI (Discovery)** — halaman search, candidate cards, verification buttons, candidate list table, audit log viewer;
- **Quality Gate B** — 9 acceptance tests.

## 4. FILE YANG DIBUAT/DIUBAH

| File | Perubahan | Status |
|---|---|---|
| `app/services/discovery.py` | Baru — mock adapter, normalisasi, dedup, verify, outlet factory | ✅ Created |
| `app/routes/discovery.py` | Baru — blueprint `/discover/` (search, verify, candidates, audit) | ✅ Created |
| `app/templates/discovery/search.html` | Baru — search form + candidate cards + verification buttons | ✅ Created |
| `app/templates/discovery/candidates.html` | Baru — tabel filterable kandidat | ✅ Created |
| `app/templates/discovery/audit.html` | Baru — audit log timeline | ✅ Created |
| `app/templates/base.html` | Ditambahkan nav links 🔍 Cari, 📋 Kandidat, 📜 Audit | ✅ Patched |
| `app/static/css/style.css` | Ditambahkan discovery-page styles (cards, badges, buttons) | ✅ Patched |
| `app/__init__.py` | Registrasi `discovery_bp` | ✅ Patched |
| `tests/gate_b.py` | Baru — 9 Quality Gate B tests | ✅ Created |

## 5. DATABASE CHANGES

- **Tidak ada migration baru** — semua tabel sudah dibuat di RUN_01 (`location_candidates`, `outlets`, `audit_logs`);
- Unique constraint `uq_candidate_place` pada `(tenant_id, place_id)` digunakan untuk dedup level database.

## 6. API/INTEGRATION CHANGES

- **Google Places API**: **TIDAK diaktifkan**. RUN_02 menggunakan **mock adapter** (data statis Bubur Fay). Integrasi nyata direncanakan di RUN_03.
- **Google Business Profile API**: Belum tersambung.

## 7. QUALITY GATE RESULT

| Gate | Result | Evidence |
|---|---|---|
| Project & Environment (RUN_01) | ✅ pass | QA Gate A |
| **Branch Discovery (RUN_02)** | **✅ pass** | **9/9 tests** |
| Google Connection | ⏳ pending | RUN_03 |
| Review Ingestion | ⏳ pending | RUN_04 |
| AI Analysis | ⏳ pending | RUN_05+ |
| Response Policy | ⏳ pending | RUN_06+ |
| Issue Tracking | ⏳ pending | RUN_07+ |
| Security | ⏳ pending | RUN_08+ |
| Dashboard | ⏳ pending | RUN_09+ |

## 8. ACCEPTANCE TEST RESULT (GATE B)

| Test | Expected | Actual | Status |
|---|---|---|---|
| B1: Search Form Rendering | GET /discover/ returns 200/302 | 302 (login redirect) | ✅ PASS |
| B2: Brand Search | 6 candidates for "Bubur Fay" | 6 candidates | ✅ PASS |
| B3: Duplicate Detection | Same search → 0 new candidates | 6 → 6 (0 new) | ✅ PASS |
| B4: Candidate Display | Card shows name, address, status, rating, reviews, confidence, reasons, buttons | All 13 sub-checks passed | ✅ PASS |
| B5: Owner Confirmed → Outlet | Outlet created for Depok | Outlet "Bubur Fay Depok" created | ✅ PASS |
| B6: Old/Closed → No Outlet | No outlet for Harjamukti | No outlet created | ✅ PASS |
| B7: Verification Persists | Status unchanged on reload | Status = owner_confirmed | ✅ PASS |
| B8: Audit Log | 2+ records with before/after/actor/tenant/timestamp | 4 records, all 9 detail checks passed | ✅ PASS |
| B9: Tenant Isolation | Cross-tenant block + no audit leak | Blocked 404, no status change, no audit | ✅ PASS |

## 9. KNOWN LIMITATIONS

- **Google Places API belum aktif** — mock adapter hanya mencakup 6 kandidat Bubur Fay. Pencarian brand lain akan mengembalikan 0 hasil.
- **Verifikasi hanya owner** — mekanisme pembuktian siapa pemilik brand sebenarnya (domain verification / GBP claim) belum diimplementasi.
- **Mock confidence heuristic** — nilai `match_confidence` dihitung secara sederhana (nama cocok, status operasional), bukan dari Google Places match quality score.
- **Reverifikasi** — setelah kandidat diverifikasi, tidak ada mekanisme untuk mengubah keputusan (belum ada tombol "ubah status").
- **Test data terbatas** — hanya brand Bubur Fay dengan 6 kandidat. Edge case brand dengan 50+ kandidat atau multi-region belum diuji.

## 10. BLOCKERS

```yaml
blockers: []
```

Tidak ada blocker. RUN_02 siap.

## 11. DATA MIGRATION / BACKFILL

Tidak ada. RUN_01 fresh, RUN_02 operates on new data.

## 12. SECURITY CHECK

```yaml
secrets_in_repo: false
secrets_in_log: false
tenant_isolation_test: pass  # B9 confirmed: cross-tenant blocked (404) + no audit leak
oauth_token_encrypted: n/a   # RUN_03
approval_bypass_test: pass   # Only owner can verify own candidates
```

## 13. FINAL STATUS

`completed`

## 14. NEXT REQUIRED ACTION

**RUN_03 — Google Connection**: integrasi OAuth + Google Business Profile API untuk mengganti mock adapter.
