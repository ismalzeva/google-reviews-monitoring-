# RUN_04 — Completion Report

**Date:** 2026-07-30  
**Status:** `completed_with_limitations`  
**Branch:** `main`  
**Head commit:** `a4e2583`

---

## Summary

RUN_04 completes the Google Reviews Monitoring platform foundation:
- OAuth state machine (Gate C)
- Branch discovery (Gate B)
- Review ingestion pipeline (Gate D)
- Mock adapter for GBP + Pub/Sub (no production API active)

---

## Quality Gate Results

| Gate | Tests | Passed | Failed | Status |
|------|-------|--------|--------|--------|
| **Gate B** (Branch Discovery) | 9 | 9 | 0 | ✅ PASS |
| **Gate C** (GBP Connection) | 75 | 75 | 0 | ✅ PASS |
| **Gate D** (Review Ingestion) | 70 | 70 | 0 | ✅ PASS |
| **Total** | **154** | **154** | **0** | ✅ |

---

## Key Fixes in This Run

### 1. DetachedInstanceError fix (Gate C)
**Root cause:** Helper functions `usr()`, `biz_tenant()`, `mkcxn()` returned ORM objects that became detached when used across different `app.app_context()` boundaries.

**Fix:** All helpers return scalar IDs only:
- `usr()` returns `user_id` (int), not User object
- `biz_tenant()` returns `(business_id, tenant_id)` tuple
- `mkcxn()` accepts scalar IDs, returns `connection_id` (string)
- All test assertions use `db.session.get()` to re-attach objects

### 2. SQLite timezone compatibility (google_oauth.py)
**Root cause:** `OAuthState.expires_at` and `GoogleConnection.token_expiry` were naive datetime objects in some contexts, causing `TypeError: can't compare offset-naive and offset-aware datetimes` in SQLite testing.

**Fix:** Added explicit `timezone.utc` conversion in:
- `handle_oauth_callback()` — `state.expires_at.replace(tzinfo=...)`
- `check_connection_health()` — `c.token_expiry.replace(tzinfo=...)`

### 3. Database contamination via `instance/` folder
**Root cause:** `sqlite:///gate_c_regression.db` resolves relative to Flask's `instance/` folder, not project root. Running `rm -f gate_c_regression.db` in project root leaves `instance/gate_c_regression.db` intact, causing stale data contamination.

**Fix:** All test scripts now:
- Use absolute path (`/tmp/grm_*.db`)
- Call `db.drop_all()` + `db.create_all()` before seeding
- Assert 0 records before inserting test data
- Print `db.engine.url` for diagnostics

### 4. monitor_enabled consistency (google_oauth.py)
**Root cause:** `save_reconciliation()` set `monitor_enabled=True` for owner_confirmed existing outlets, but `False` for new outlets — inconsistent behavior.

**Fix:** New outlets now inherit `monitor_enabled = (owner_verification_status in ('verified', 'owner_confirmed'))`.

### 5. Test harness portability (gate_b.py)
Added `drop_all()` + `create_all()` with `DATABASE_URL` override for fresh SQLite testing.

---

## Migration Smoke Test

- `flask db upgrade` → 3 migrations applied
- `flask db current` → `cd11cd29cadf (head)`
- `flask db heads` → `cd11cd29cadf (head)` (single head, no branching)
- Database: fresh SQLite at `/tmp/grm_migration_test.db`

---

## Known Limitations

| Limitation | Details |
|------------|---------|
| **Google API** | Production API not active. All GBP operations run in mock mode. |
| **Pub/Sub** | Review event notifications use mock adapter. No real Pub/Sub integration. |
| **`reply_enabled`** | Always `False` in mock mode. Requires production GBP API for reply capability. |
| **Harjamukti** | Excluded from monitoring (`owner_verification_status = old_or_closed`). |
| **RUN_05** | Not started. Review ingestion topics, real API activation, tenant onboarding. |

---

## Files Modified

| File | Change |
|------|--------|
| `tests/gate_c.py` | Scalar ID refactor + `drop_all`/`create_all` setup + absolute DB path |
| `tests/gate_b.py` | Added `drop_all`/`create_all` setup + absolute DB path |
| `app/services/google_oauth.py` | Timezone fix + `monitor_enabled` consistency |
| `completion-reports/RUN_04_completion.md` | This report |

---

## Next (RUN_05)

Not started. Items for RUN_05:
- Real Google Places API integration
- Real Pub/Sub notification handling  
- Review ingestion from live GBP
- Tenant onboarding flow
- Reply enablement for production accounts
