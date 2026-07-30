---
name: completion-report-template
version: 1.0.0
type: reporting-skill
status: active
---

# HERMES AGENT SKILL — COMPLETION REPORT TEMPLATE

Gunakan format ini setelah implementasi, perbaikan, migrasi, atau testing.

# COMPLETION REPORT

## 1. IDENTITAS

```yaml
project: Google Reviews Monitoring & Intelligence
pilot: Bubur Fay
task:
version:
environment:
started_at:
completed_at:
executed_by:
```

## 2. TUJUAN

Jelaskan tujuan pekerjaan secara singkat.

## 3. SCOPE YANG DIKERJAKAN

- modul;
- endpoint;
- database;
- UI;
- agent;
- integration;
- tests.

## 4. FILE YANG DIBUAT/DIUBAH

| File | Perubahan | Status |
|---|---|---|

## 5. DATABASE CHANGES

- migration;
- table;
- index;
- unique constraint;
- backfill;
- rollback status.

## 6. API/INTEGRATION CHANGES

- Google Places;
- Google Business Profile;
- OAuth;
- Pub/Sub;
- review endpoint;
- reply endpoint.

Jangan menampilkan secrets.

## 7. QUALITY GATE RESULT

| Gate | Result | Evidence |
|---|---|---|
| Project & Environment | pass/fail | |
| Branch Discovery | pass/fail | |
| Google Connection | pass/fail | |
| Review Ingestion | pass/fail | |
| AI Analysis | pass/fail | |
| Response Policy | pass/fail | |
| Issue Tracking | pass/fail | |
| Security | pass/fail | |
| Dashboard | pass/fail | |

## 8. ACCEPTANCE TEST RESULT

| Test | Expected | Actual | Status |
|---|---|---|---|

Minimum wajib mencakup:

- query `Bubur Fay`;
- owner verifies candidate;
- account/location list;
- review sync;
- duplicate event;
- positive safe route;
- negative approval route;
- critical escalation;
- moderation rejection;
- tenant isolation.

## 9. KNOWN LIMITATIONS

Tuliskan hanya limitation nyata.

Contoh category:

- API approval pending;
- location not verified;
- notification not configured;
- historical import only;
- moderation state unavailable;
- test data limitation.

## 10. BLOCKERS

```yaml
blockers:
  - issue:
    impact:
    owner:
    required_action:
```

## 11. DATA MIGRATION / BACKFILL

- records processed;
- created;
- updated;
- skipped;
- failed;
- reconciliation result.

## 12. SECURITY CHECK

```yaml
secrets_in_repo: false
secrets_in_log: false
tenant_isolation_test:
oauth_token_encrypted:
approval_bypass_test:
```

## 13. FINAL STATUS

Pilih satu:

- `completed`
- `completed_with_limitations`
- `not_ready_for_production`
- `blocked`

## 14. NEXT REQUIRED ACTION

Hanya tindakan yang benar-benar diperlukan untuk menutup scope atau blocker.

Jangan menambahkan ide produk baru di luar scope v1.0.
