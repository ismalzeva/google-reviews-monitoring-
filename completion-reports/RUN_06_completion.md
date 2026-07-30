# RUN_06 — Rapid Response & Approval Workflow

**Status:** `completed_with_limitations`
**Date:** 2026-07-30

## Summary

Implemented routing logic, draft creation, approval/reject/publish workflow, moderation, escalation, tenant isolation, and response metrics for Google Reviews monitoring.

## Features Delivered

- **Routing engine** (`determine_route`): auto, approval, escalation based on sentiment, rating, urgency, risk, confidence, topics
- **Draft generation** (`generate_draft_text`): brand-tone templates for positive/mixed/negative/critical
- **Approval workflow** (`approve_reply`, `reject_reply`, `publish_reply`): full lifecycle with idempotent operations
- **Moderation** (`update_moderation`): published/rejected/pending_review with policy_violation tracking
- **Escalation** (`create_escalation`): creates Issue + holding draft for critical reviews
- **Edit existing replies** (`update_existing_reply`): version increment, reset approval, re-approve
- **Response metrics** (`get_response_metrics`): per-tenant, with publication rate, avg response time
- **Audit trail**: all actions logged via `AuditLog`
- **Tenant isolation**: tenants only see own replies/metrics
- **All draft approval_status = 'pending'** regardless of route (auto-reply OFF by default)
- **Mock publication**: no Google API calls in test mode

## Gate Test Results

| Gate | Tests | Pass | Fail |
|------|-------|------|------|
| B    | 9     | 9    | 0    |
| C    | 75    | 75   | 0    |
| D    | 70    | 70   | 0    |
| E    | 81    | 81   | 0    |
| F    | 101   | 101  | 0    |

## Limitations

1. **Auto-reply OFF by default** — `outlet._auto_reply_enabled` must be explicitly enabled per outlet; always falls back to approval
2. **Google API mocked** — `publish_reply` only updates DB state, no actual Google My Business API call
3. **Pub/Sub mocked** — moderation status updates via direct `update_moderation()` call, not via Google event
4. **reply_enabled = False** — all outlets have replies disabled; routing still works but no real publication
5. **Harjamukti excluded** — outlet has `monitor_enabled=False`, `status='inactive'`
6. **No template customization** — brand tone templates hardcoded in `response_service.py`
7. **Metrics on SQLite** — `avg_response_time` uses timestamp math; may behave differently on PostgreSQL

## Files Modified

- `app/services/response_service.py` — New file (593 lines): routing, draft, approval, publish, moderate, escalate, metrics
- `app/routes/response.py` — New file (245 lines): 11 REST endpoints
- `app/__init__.py` — Register `response_bp` blueprint
- `tests/gate_f.py` — New file (659 lines): 101 integration tests

## Commit Hash

(RUN_07 is NOT yet started — next phase)
