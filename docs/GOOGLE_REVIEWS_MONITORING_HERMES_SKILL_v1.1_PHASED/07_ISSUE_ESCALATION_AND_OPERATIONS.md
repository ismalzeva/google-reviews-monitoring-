---
name: issue-escalation-and-operations
version: 1.0.0
type: operational-follow-up-skill
status: active
---

# HERMES AGENT SKILL — ISSUE ESCALATION & OPERATIONS

## 1. PURPOSE

Mengubah keluhan yang relevan menjadi tindakan internal yang dapat ditugaskan, dipantau, dan diselesaikan.

## 2. PUBLIC REPLY VS INTERNAL ACTION

Public reply bertujuan:

- merespons pelanggan;
- menunjukkan kepedulian;
- tidak membuka detail internal.

Internal action bertujuan:

- memeriksa fakta;
- menemukan akar masalah;
- memperbaiki proses;
- mencatat bukti tindakan;
- mencegah pengulangan.

Keduanya wajib disimpan terpisah.

## 3. ISSUE CREATION RULE

Buat issue ketika:

- urgency high atau critical;
- topic membutuhkan pemeriksaan;
- review 1–2 dengan keluhan;
- masalah terdeteksi berulang;
- owner/supervisor menandai review;
- review update meningkatkan risiko;
- reply membutuhkan follow-up.

Pujian tidak wajib membuat issue.

## 4. ISSUE DATA

```yaml
issue_id:
business_id:
outlet_id:
review_id:
pattern_id:
title:
issue_summary:
category:
urgency:
reputation_risk:
source_facts:
ai_assessment:
primary_owner_role:
assigned_user_id:
supporting_roles:
status:
due_at:
action_checklist:
internal_notes:
evidence_attachments:
resolution_summary:
created_at:
updated_at:
resolved_at:
```

## 5. RESPONSIBILITY MAPPING

### Product/Rasa/Konsistensi

Primary:

- kepala_dapur atau quality_control

Support:

- supervisor_operasional;
- kepala_outlet.

### Pelayanan/Staf

Primary:

- kepala_outlet atau supervisor_operasional

Support:

- human_resources bila pola perilaku/discipline.

### Pesanan Salah/Antrean

Primary:

- supervisor_operasional

Support:

- kepala_outlet;
- tim terkait proses order.

### Kebersihan

Primary:

- kepala_outlet

Support:

- supervisor_operasional;
- quality_control.

### Food Safety/Illness

Primary:

- owner dan quality_control

Support:

- supervisor_operasional;
- kepala_dapur;
- legal_or_compliance bila diperlukan.

### Reputation/Viral/Legal

Primary:

- owner

Support:

- customer_service;
- marketing;
- legal_or_compliance.

## 6. DEFAULT RESPONSE TARGETS

Target harus dapat dikonfigurasi oleh admin.

Default operational target:

| Level | Acknowledgement | Assignment |
|---|---:|---:|
| low | dalam 24 jam | bila diperlukan |
| medium | dalam 12 jam | dalam 12 jam |
| high | dalam 2 jam | dalam 2 jam |
| critical | segera | segera |

Target ini adalah konfigurasi sistem, bukan janji publik kepada pelanggan.

## 7. OPERATIONAL CHECKLIST EXAMPLES

### Wait Time

- periksa jam dan outlet;
- periksa pola review serupa;
- periksa staffing;
- periksa antrean;
- periksa pembagian tugas;
- catat tindakan.

### Wrong Order

- periksa alur pencatatan;
- periksa label/order number;
- periksa handoff;
- periksa channel order;
- lakukan corrective action.

### Product Consistency

- periksa gramasi/SOP;
- periksa batch produksi;
- periksa shift;
- periksa bahan baku;
- lakukan sampling supervisor.

### Cleanliness

- periksa log cleaning;
- inspeksi outlet;
- identifikasi area;
- lakukan tindakan;
- dokumentasikan hasil.

### Food Safety

- preserve evidence;
- identifikasi tanggal/jam/menu;
- tahan asumsi;
- periksa batch dan bahan;
- eskalasi owner;
- dokumentasikan pemeriksaan;
- jangan membuat diagnosis.

## 8. ISSUE STATUS FLOW

```text
new
 ↓
under_review
 ↓
assigned
 ↓
in_progress
 ↓
resolved
 ↓
closed
```

Issue dapat `reopened` jika:

- keluhan serupa muncul kembali;
- tindakan tidak efektif;
- owner menolak resolution;
- review diperbarui dengan informasi baru.

## 9. ESCALATION RULES

Escalate kepada owner ketika:

- critical;
- due target terlewati;
- issue berulang meningkat;
- lokasi gagal merespons;
- reply moderation rejected pada kasus sensitif;
- terdapat potensi legal/media;
- cross-outlet systemic issue.

## 10. CLOSURE RULE

Issue tidak boleh closed hanya karena reply sudah dipublikasikan.

Closure membutuhkan:

- tindakan internal tercatat;
- resolution summary;
- resolver identity;
- timestamp;
- evidence atau note yang memadai;
- owner/supervisor approval sesuai policy.

## 11. PATTERN-TO-ISSUE

Jika beberapa review menjadi pattern:

- buat satu parent issue;
- hubungkan supporting reviews;
- jangan membuat tindakan terpisah yang tidak perlu;
- ukur trend;
- tentukan outlet-specific atau systemic.

## 12. MANAGEMENT OUTPUT

```yaml
open_issues:
critical_open:
overdue:
repeat_patterns:
outlets_needing_attention:
actions_completed:
issues_reopened:
```

## 13. ACCEPTANCE CRITERIA

- Review negatif dapat membuat issue.
- Public reply tidak menandai issue resolved otomatis.
- Responsible role sesuai category.
- Critical issue mengirim escalation.
- Issue history tidak dapat hilang.
- Pattern dapat menghubungkan beberapa review.
- Closure memiliki bukti tindakan.
