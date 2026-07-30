---
name: data-contracts-and-output-schema
version: 1.0.0
type: data-contract-skill
status: active
---

# HERMES AGENT SKILL — DATA CONTRACTS & OUTPUT SCHEMA

## 1. PURPOSE

Menetapkan kontrak data minimum agar seluruh agent, database, API, dashboard, dan laporan menggunakan struktur yang konsisten.

## 2. MULTI-TENANT RULE

Semua business data harus memiliki:

```yaml
tenant_id:
business_id:
```

Outlet, review, analysis, reply, approval, issue, event, dan audit log harus terikat pada tenant.

Tidak boleh ada cross-tenant query tanpa role platform super admin.

## 3. PRIMARY ENTITIES

### businesses

```yaml
id:
tenant_id:
name:
brand_name:
country:
timezone:
default_language:
status:
created_at:
updated_at:
```

### outlets

```yaml
id:
tenant_id:
business_id:
name:
address:
latitude:
longitude:
public_place_id:
gbp_account_id:
gbp_location_id:
owner_verification_status:
gbp_match_status:
monitor_enabled:
reply_enabled:
status:
created_at:
updated_at:
```

### location_candidates

Lihat schema pada file discovery.

### google_connections

```yaml
id:
tenant_id:
business_id:
google_subject_id:
selected_account_id:
encrypted_access_token_ref:
encrypted_refresh_token_ref:
token_expiry:
scopes:
status:
connected_by:
connected_at:
last_health_check:
```

Token asli tidak boleh muncul di API response internal umum.

### import_batches

```yaml
id:
tenant_id:
business_id:
source:
file_name:
status:
rows_total:
rows_valid:
rows_invalid:
duplicates:
started_at:
completed_at:
error_report_ref:
```

### reviews

```yaml
id:
tenant_id:
business_id:
outlet_id:
source:
source_review_name:
review_id:
reviewer_display_name:
reviewer_is_anonymous:
star_rating:
comment:
has_text:
create_time:
update_time:
source_visibility_status:
current_version:
raw_payload_hash:
created_at:
updated_at:
```

### review_versions

```yaml
id:
review_pk:
version:
star_rating:
comment:
source_update_time:
raw_payload_hash:
captured_at:
```

### review_analyses

```yaml
id:
review_pk:
analysis_version:
model_name:
policy_version:
sentiment:
topics_json:
issue_summary:
urgency:
reputation_risk:
repeat_pattern_candidate:
responsible_role:
recommended_public_response_intent_json:
recommended_internal_action_json:
human_review_required:
confidence_json:
created_at:
```

### review_replies

```yaml
id:
review_pk:
draft_version:
draft_text:
route:
approval_status:
approved_text:
publication_status:
google_reply_update_time:
review_reply_state:
policy_violation:
review_reply_url:
published_by:
published_at:
created_at:
updated_at:
```

### approvals

```yaml
id:
tenant_id:
review_reply_id:
decision:
actor_user_id:
edited_text:
note:
decided_at:
```

### issues

Lihat file issue.

### pubsub_events

```yaml
id:
tenant_id:
google_account_id:
event_type:
review_name:
location_name:
message_id:
publish_time:
payload_hash:
processing_status:
retry_count:
received_at:
processed_at:
```

### audit_logs

```yaml
id:
tenant_id:
actor_type:
actor_id:
action:
entity_type:
entity_id:
before_json:
after_json:
reason:
trace_id:
created_at:
```

## 4. UNIQUE CONSTRAINTS

Minimum:

```text
reviews(tenant_id, source, source_review_name)
pubsub_events(google_account_id, message_id)
outlets(tenant_id, gbp_location_id) where gbp_location_id is not null
location_candidates(tenant_id, place_id)
```

## 5. API OUTPUT ENVELOPE

Success:

```json
{
  "success": true,
  "data": {},
  "meta": {
    "trace_id": "",
    "timestamp": "",
    "pagination": null
  },
  "errors": []
}
```

Failure:

```json
{
  "success": false,
  "data": null,
  "meta": {
    "trace_id": "",
    "timestamp": ""
  },
  "errors": [
    {
      "code": "",
      "message": "",
      "field": null,
      "retryable": false
    }
  ]
}
```

## 6. DASHBOARD METRICS

### Summary

- average_rating;
- total_reviews;
- new_reviews;
- rating_only_reviews;
- positive_reviews;
- negative_reviews;
- mixed_reviews;
- unanswered_reviews;
- awaiting_approval;
- high_urgency_open;
- critical_open.

### Trends

- rating by period;
- review count by period;
- sentiment by period;
- topic frequency;
- reply time;
- issue resolution time.

### Outlet Comparison

```yaml
outlet_id:
outlet_name:
average_rating:
new_reviews:
negative_percentage:
unanswered_count:
high_urgency_count:
critical_count:
top_positive_topic:
top_negative_topic:
reply_median_time:
open_issue_count:
```

## 7. MANAGEMENT SUMMARY OUTPUT

```yaml
period:
business:
executive_summary:
rating:
  current:
  previous:
  change:
reviews:
  total_new:
  positive:
  neutral:
  negative:
  mixed:
top_praises: []
top_complaints: []
increasing_issues: []
outlet_comparison: []
priority_reviews: []
unanswered_reviews:
open_issues:
recommended_management_actions: []
data_limitations: []
generated_at:
```

## 8. REVIEW QUEUE OUTPUT

```yaml
review_id:
outlet:
rating:
comment_preview:
review_date:
sentiment:
primary_topic:
urgency:
reputation_risk:
reply_status:
approval_required:
issue_status:
```

## 9. DATA LINEAGE

Setiap review harus dapat ditelusuri:

```text
Source
→ Import/Sync/Event
→ Raw Payload
→ Normalized Review
→ Review Version
→ AI Analysis
→ Draft Reply
→ Approval
→ Publication
→ Moderation
→ Issue
→ Resolution
```

## 10. RETENTION AND DELETE

- Original review record tidak hard-delete melalui workflow biasa.
- Token mengikuti security retention.
- Disconnect tidak otomatis menghapus historical analytics.
- User deletion request mengikuti policy produk dan hukum yang berlaku.
- Audit log tidak dapat diedit pengguna biasa.
- Soft delete untuk entities yang perlu dipertahankan secara historis.

## 11. OUTPUT VALIDATION

Hermes wajib:

- validasi enum;
- validasi required field;
- validasi rating;
- validasi timestamp;
- validasi tenant;
- validasi reference;
- menolak unknown write fields;
- menangani unknown future API enum secara aman.

## 12. ACCEPTANCE CRITERIA

- Schema konsisten antar-agent.
- Tenant ID tersedia.
- Unique constraints mencegah duplicate.
- Reply memiliki version dan approval lineage.
- Dashboard dapat dihitung dari database.
- Audit trail lengkap.
