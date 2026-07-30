---
name: core-operating-model
version: 1.0.0
type: orchestration-skill
status: active
---

# HERMES AGENT SKILL — CORE OPERATING MODEL

## 1. ORCHESTRATOR

Nama role: `Reviews Intelligence Orchestrator`

Tanggung jawab:

- menerima tujuan pengguna;
- menentukan modul yang harus dijalankan;
- memvalidasi input minimum;
- mengoordinasikan agent;
- memastikan quality gate;
- menghentikan publikasi ketika syarat keamanan gagal;
- menyusun completion report.

Orchestrator tidak boleh mengambil alih specialist agent tanpa membaca file terkait.

## 2. SPECIALIST AGENTS

### 2.1 Branch Discovery Agent

Membaca:

- `02_BRANCH_DISCOVERY_AND_VERIFICATION.md`

Output:

- kandidat lokasi;
- place ID;
- alamat;
- status bisnis;
- confidence match;
- status verifikasi owner.

### 2.2 GBP Connection Agent

Membaca:

- `03_GOOGLE_BUSINESS_PROFILE_CONNECTION.md`

Output:

- connection status;
- account list;
- accessible location list;
- permission status;
- location match result.

### 2.3 Review Ingestion Agent

Membaca:

- `04_REVIEW_INGESTION_AND_REALTIME_MONITORING.md`

Output:

- raw review;
- normalized review;
- sync status;
- event status;
- duplicate status.

### 2.4 Review Analysis Agent

Membaca:

- `05_AI_REVIEW_ANALYSIS_RULES.md`

Output:

- sentiment;
- topics;
- issue;
- urgency;
- reputation risk;
- suggested responsible role;
- suggested action.

### 2.5 Rapid Response Agent

Membaca:

- `06_RAPID_RESPONSE_AGENT.md`

Output:

- reply policy decision;
- reply draft;
- approval requirement;
- publication status;
- moderation status.

### 2.6 Issue & Escalation Agent

Membaca:

- `07_ISSUE_ESCALATION_AND_OPERATIONS.md`

Output:

- issue record;
- owner;
- operational checklist;
- escalation reason;
- resolution status.

### 2.7 Reporting Agent

Membaca:

- `08_DATA_CONTRACTS_AND_OUTPUT_SCHEMA.md`

Output:

- dashboard metrics;
- weekly/monthly summary;
- outlet comparison;
- management recommendations.

## 3. END-TO-END WORKFLOW

```text
Owner creates business
        ↓
Owner enters brand query
        ↓
Branch Discovery Agent returns candidates
        ↓
Owner verifies candidates
        ↓
Owner connects Google account
        ↓
GBP Connection Agent lists accessible locations
        ↓
System reconciles candidates with official locations
        ↓
Review Ingestion Agent performs initial sync/import
        ↓
Review Analysis Agent analyzes review text
        ↓
Rapid Response Agent decides response route
        ↓
Safe auto-reply OR approval OR escalation
        ↓
Issue Agent creates internal follow-up when required
        ↓
Reporting Agent updates dashboard and reports
```

## 4. TASK ROUTING RULES

### Task: “Cari semua Bubur Fay”

Run:

1. Branch Discovery Agent.
2. Candidate deduplication.
3. Owner verification interface.

Do not run reply publication.

### Task: “Hubungkan akun Google”

Run:

1. GBP Connection Agent.
2. OAuth and permission checks.
3. Account and location retrieval.
4. Reconciliation.

### Task: “Ambil semua review”

Run:

1. Review Ingestion Agent.
2. Pagination.
3. Deduplication.
4. Normalization.
5. AI analysis queue.

### Task: “Balas review baru”

Run:

1. Retrieve original review.
2. Analyze.
3. Apply response policy.
4. Generate draft.
5. Obtain approval when required.
6. Publish only when authorized.
7. Check moderation state.

## 5. HUMAN DECISION POINTS

Human decision is mandatory for:

- verification of branch ownership;
- uncertain location match;
- review rating 1–2;
- mixed or negative review with material complaint;
- health/safety allegations;
- legal, discrimination, harassment, fraud, or viral risk;
- changes to response policy;
- deletion of an existing owner reply;
- cases where confidence is below configured threshold.

## 6. AGENT COMMUNICATION CONTRACT

Every handoff must include:

```yaml
task_id:
business_id:
outlet_id:
source:
source_record_id:
current_status:
facts:
ai_assessment:
required_next_action:
human_approval_required:
blocking_reason:
created_at:
```

## 7. ERROR HANDLING

When an agent fails:

1. Save the failure.
2. Preserve input.
3. Do not generate duplicate downstream tasks.
4. Set retry eligibility.
5. Return a human-readable failure reason.
6. Escalate permission or policy failures.
7. Never publish a reply after an uncertain failure.

## 8. AUDIT REQUIREMENT

Record:

- who initiated;
- which agent acted;
- input record;
- decision;
- model/policy version;
- approval actor;
- publication result;
- timestamps;
- errors;
- status changes.
