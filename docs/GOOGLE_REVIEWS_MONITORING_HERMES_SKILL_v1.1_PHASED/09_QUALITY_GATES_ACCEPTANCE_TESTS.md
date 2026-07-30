---
name: quality-gates-and-acceptance-tests
version: 1.0.0
type: testing-skill
status: active
---

# HERMES AGENT SKILL — QUALITY GATES & ACCEPTANCE TESTS

## 1. RULE

Tidak ada fitur yang dianggap selesai hanya karena UI tampil.

Setiap tahap harus lulus functional, data, security, and safety gates.

## 2. GATE A — PROJECT & ENVIRONMENT

Pass jika:

- environment variables terdefinisi;
- API keys tidak di repository;
- database migration berhasil;
- tenant model tersedia;
- health endpoint berhasil;
- error logging tersedia tanpa secret.

Fail action:

- stop;
- report blocking issue;
- jangan lanjut ke API publication test.

## 3. GATE B — BRANCH DISCOVERY

### Test B1 — Brand Query

Input:

```text
Bubur Fay
```

Expected:

- kandidat ditampilkan;
- place ID tersimpan;
- alamat tersedia;
- source marked public discovery;
- tidak otomatis official.

### Test B2 — Owner Verification

Owner memilih:

- cabang benar;
- bukan cabang;
- cabang lama;
- duplicate;
- uncertain.

Expected:

- keputusan tersimpan;
- actor dan timestamp tersimpan;
- dapat direvisi;
- audit log tersedia.

### Test B3 — Duplicate Candidate

Expected:

- location sama dari query berbeda tidak menjadi cabang ganda.

## 4. GATE C — GOOGLE CONNECTION

### Test C1 — OAuth Success

Expected:

- token tersimpan encrypted;
- scope valid;
- account list berhasil.

### Test C2 — Multiple Accounts

Expected:

- owner memilih account;
- sistem tidak memilih diam-diam.

### Test C3 — Location List

Expected:

- pagination;
- location fields;
- place ID bila tersedia;
- match candidate.

### Test C4 — Revoked Token

Expected:

- sync berhenti;
- reply disabled;
- clear reconnect action;
- no credential leakage.

## 5. GATE D — REVIEW INGESTION

### Test D1 — Historical Sync

Expected:

- all pages processed;
- total count reconciled;
- no duplicates.

### Test D2 — Rating-Only

Expected:

- masuk metrics;
- no hallucinated topic;
- qualitative status not applicable.

### Test D3 — NEW_REVIEW Duplicate Event

Send event twice.

Expected:

- one review;
- one analysis;
- maximum one reply action.

### Test D4 — UPDATED_REVIEW

Expected:

- new version stored;
- old version retained;
- reanalysis;
- response reassessment.

### Test D5 — Outscraper Import

Expected:

- raw file retained;
- row report;
- outlet mapping;
- no reply enablement from import alone.

## 6. GATE E — AI ANALYSIS

### Test E1 — Positive

Input:

> Buburnya enak dan pelayanannya ramah.

Expected:

- positive;
- taste + friendliness;
- low urgency.

### Test E2 — Mixed

Input:

> Buburnya enak, tetapi nunggunya lama.

Expected:

- mixed;
- taste positive;
- wait_time negative;
- medium urgency;
- approval route.

### Test E3 — Critical

Input:

> Makanan terasa basi dan setelah makan saya sakit.

Expected:

- critical;
- food_safety/illness allegation;
- severe risk;
- owner escalation;
- no auto-reply.

### Test E4 — Rating/Text Mismatch

Expected:

- mismatch flag;
- human review.

## 7. GATE F — RESPONSE POLICY

### Test F1 — Safe Positive

Conditions:

- 5-star;
- positive;
- no complaint;
- high confidence;
- policy enabled;
- reply-enabled location.

Expected:

- draft valid;
- publish allowed;
- audit record.

### Test F2 — 1-Star

Expected:

- awaiting approval;
- no auto-publish.

### Test F3 — Critical

Expected:

- critical issue;
- owner alert;
- holding draft only;
- no auto-publish.

### Test F4 — Duplicate Publication

Retry same job.

Expected:

- no duplicate reply.

### Test F5 — Reply Rejected

Expected:

- rejection stored;
- policy violation stored;
- human correction route;
- no blind resend.

## 8. GATE G — ISSUE TRACKING

### Test G1 — Create Issue

Expected:

- role assigned;
- status new;
- review linked.

### Test G2 — Reply Published

Expected:

- issue remains open until operational resolution.

### Test G3 — Pattern

Multiple wait-time reviews.

Expected:

- repeat pattern;
- parent issue or linked pattern;
- supporting review IDs.

### Test G4 — Close Issue

Expected:

- action note;
- resolver;
- timestamp;
- required approval.

## 9. GATE H — SECURITY

Test:

- cross-tenant access;
- role violation;
- token leakage;
- webhook/PubSub spoof;
- replay event;
- SQL injection;
- unsafe file upload;
- log redaction;
- approval bypass.

All must pass before production.

## 10. GATE I — DASHBOARD

Expected:

- period filter;
- outlet filter;
- rating metrics;
- sentiment metrics;
- unanswered reviews;
- priority queue;
- outlet comparison;
- issue metrics;
- source limitation label.

## 11. DEFINITION OF DONE CHECKLIST

```yaml
project:
  migrations_passed:
  health_check_passed:
discovery:
  brand_search_passed:
  owner_verification_passed:
  dedup_passed:
connection:
  oauth_passed:
  account_list_passed:
  location_list_passed:
review_ingestion:
  historical_sync_passed:
  event_processing_passed:
  rating_only_passed:
analysis:
  sentiment_passed:
  topic_passed:
  critical_route_passed:
response:
  safe_auto_reply_passed:
  approval_passed:
  escalation_passed:
  moderation_tracking_passed:
operations:
  issue_tracking_passed:
  pattern_detection_passed:
security:
  tenant_isolation_passed:
  secret_redaction_passed:
  approval_bypass_test_passed:
reporting:
  dashboard_passed:
  completion_report_created:
```

## 12. FINAL RULE

Jika satu critical safety/security test gagal:

- implementation status = `not_ready_for_production`;
- jangan menyatakan selesai;
- jangan mengaktifkan auto-reply;
- tuliskan remediation yang spesifik.
