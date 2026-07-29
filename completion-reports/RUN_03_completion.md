# RUN_03 — Google Business Profile Connection

**Status:** `completed_with_limitations`
**Date:** 2026-07-29

---

## Summary

Google Business Profile connection system with production-aware architecture,
fully operational in mock adapter mode pending Google Cloud credential setup.

## Deliverables

| Module | Description |
|---|---|
| `app/services/google_oauth.py` | OAuth state engine + mock adapter + reconciliation |
| `app/routes/google.py` | Routes with crypto state validation + tenant isolation |
| `app/models/entities.py` | `OAuthState` model + mock/health columns |
| `app/templates/google/*.html` | Status, accounts, locations, reconciliation views |
| `app/static/css/style.css` | 200+ lines — mock, matched, unmatched, owner-blocked |
| `tests/gate_c.py` | 97 comprehensive Quality Gate C tests |

## Architecture

```
User → /google/connect → create_oauth_state() → { nonce, user, tenant, business, connection, 15min expiry }
     → /google/callback → validate_oauth_state() → constant-time compare + consumer check + expiry check
     → mock (no real Google API): accounts auto-generated, locations seeded
     → reconciliation: exact Place ID match → fuzzy name+geo match → ambiguous → owner blocked
     → connection saved with adapter_mode='mock', production_api_connected=False
```

## Quality Gate C Results

```
Total tests:  97
Passed:       97
Failed:       0
ALL GATES PASSED
```

### Test Coverage

| Section | Tests | Passed |
|---|---|---|
| C01-C07: OAuth State (valid, forged, expired, replay, without, after-logout, cross-tenant) | 8 | ✅ |
| C08-C10: Account Discovery (0 accounts, 1 auto-select, multi picker) | 3 | ✅ |
| C11-C12: Location + Exact Match | 2 | ✅ |
| C13-C14: Fuzzy + Ambiguous | 2 | ✅ |
| C15: Harjamukti old_or_closed stays inactive | 5 | ✅ |
| C16: Token encryption (DB, log, HTML, API, exception) | 5 | ✅ |
| C17-C19: Failure states (expired, revoked, denied) | 3 | ✅ |
| C20-C21: Disconnect + Tenant Isolation | 5 | ✅ |
| C22-C24: Mock + Atomic + Health Honesty | 6 | ✅ |

## Security

- **OAuth state:** crypto nonce (32-byte `secrets.token_hex`), server-side DB storage, 15-minute expiry, single-use with `consumed_at`, constant-time validation via `hmac.compare_digest`
- **Token encryption:** Fernet symmetric encryption, no plaintext in DB/log/HTML/API/errors
- **Tenant isolation:** Every route filters by `business_id` + `tenant_id`; cross-tenant access returns ValueError/403
- **Mock adapter:** Status `mock_connected`, never enables `reply_enabled`, never claims production access

## Known Limitations

| Limitation | Detail |
|---|---|
| Google Cloud credential | Belum tersedia |
| OAuth consent screen | Belum dikonfigurasi |
| Business Profile API | Belum approved |
| Pagination | Mock-only |
| Token refresh | Mock-only |
| Review endpoint | Mock-only (`mock_only`) |
| Reply eligibility | Dipaksa `false` |
| Pub/Sub notification | Diluar scope RUN_03 |

## Files Committed

- `app/__init__.py` — google_bp registration
- `app/config.py` — OAuth env vars
- `app/models/entities.py` — OAuthState + mock columns
- `app/services/google_oauth.py` — core engine (new)
- `app/services/encryption.py` — Fernet helper (new)
- `app/routes/google.py` — routes (new)
- `app/templates/google/*.html` — 5 templates (new)
- `app/static/css/style.css` — Google visual styles
- `migrations/versions/b2530f489e05_feat_add_oauth_state_mock_columns.py` — migration (new)
- `tests/gate_c.py` — 97 tests (new)
- `.env.example` — Google OAuth placeholders
