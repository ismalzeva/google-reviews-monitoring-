---
name: ai-review-analysis-rules
version: 1.0.0
type: analysis-skill
status: active
---

# HERMES AGENT SKILL — AI REVIEW ANALYSIS RULES

## 1. PURPOSE

Mengubah teks review menjadi analisis terstruktur tanpa mengubah fakta asli.

## 2. INPUT

```yaml
review_id:
outlet:
star_rating:
comment:
review_language:
review_date:
existing_owner_reply:
context:
  business_type:
  brand_name:
  approved_topic_library:
  approved_risk_policy:
```

## 3. OUTPUT PRINCIPLE

Pisahkan:

1. Fakta eksplisit dalam review.
2. Interpretasi AI.
3. Ketidakpastian.
4. Rekomendasi balasan publik.
5. Rekomendasi tindakan internal.

AI tidak boleh:

- mengarang kejadian;
- menuduh karyawan;
- menyimpulkan penyebab tanpa bukti;
- menganggap reviewer benar atau salah tanpa verifikasi;
- mengungkap chain-of-thought.

## 4. SENTIMENT LABELS

- `positive`
- `neutral`
- `negative`
- `mixed`
- `not_applicable`

`mixed` digunakan ketika terdapat pujian dan keluhan material dalam satu review.

## 5. TOPIC LIBRARY

### Product

- taste
- food_quality
- temperature
- portion
- consistency
- presentation
- topping_completeness
- menu_availability

### Service

- friendliness
- speed
- accuracy
- communication
- staff_attitude
- complaint_handling
- upselling

### Operations

- wait_time
- queue
- wrong_order
- incomplete_order
- opening_hours
- stock_availability
- production_speed

### Place

- cleanliness
- comfort
- atmosphere
- seating
- parking
- location_access
- accessibility

### Price

- expensive
- affordable
- value_for_money
- promotion
- online_offline_price_difference

### Online Order

- delivery_delay
- packaging
- wrong_item
- food_condition_on_arrival
- courier
- missing_item

### Reputation/Safety

- food_safety
- illness_allegation
- fraud_allegation
- discrimination
- harassment
- legal_threat
- viral_threat
- privacy_issue

Satu review dapat memiliki beberapa topik.

## 6. URGENCY LEVEL

### low

- pujian;
- saran kecil;
- preferensi pribadi;
- tidak ada dampak operasional material.

### medium

- pelayanan lambat tunggal;
- porsi;
- ekspektasi produk;
- keluhan yang perlu diperiksa tetapi tidak sensitif.

### high

- staf tidak ramah;
- pesanan salah;
- kebersihan;
- keluhan berulang;
- rating rendah dengan penjelasan jelas;
- potensi dampak reputasi.

### critical

- makanan basi/keracunan atau risiko kesehatan;
- penipuan;
- pelecehan;
- diskriminasi;
- ancaman hukum;
- konflik serius;
- potensi viral;
- keselamatan;
- data pribadi sensitif.

## 7. REPUTATION RISK

- `minimal`
- `contained`
- `elevated`
- `severe`

Pertimbangkan:

- severity;
- specificity;
- evidence described;
- repeat pattern;
- star rating;
- public sensitivity;
- legal/health/safety terms;
- potential virality.

## 8. RESPONSIBLE ROLE

Pilih satu primary owner dan optional supporting roles:

- owner
- supervisor_operasional
- kepala_outlet
- kepala_dapur
- customer_service
- marketing
- human_resources
- quality_control
- legal_or_compliance

## 9. CONFIDENCE

```yaml
confidence:
  sentiment: 0.00-1.00
  topics: 0.00-1.00
  urgency: 0.00-1.00
  recommended_route: 0.00-1.00
```

Jika confidence di bawah threshold konfigurasi:

- `human_review_required: true`.

## 10. EVIDENCE SNIPPET

Gunakan kutipan pendek dari review sebagai evidence.

Rules:

- tidak lebih panjang dari yang diperlukan;
- tidak mengubah makna;
- tidak memuat data pribadi yang tidak dibutuhkan;
- boleh kosong untuk rating-only review.

## 11. STRUCTURED OUTPUT

```json
{
  "review_id": "",
  "has_text": true,
  "language": "id",
  "sentiment": "mixed",
  "sentiment_reasons": [
    "Pelanggan memuji rasa",
    "Pelanggan mengeluhkan waktu tunggu"
  ],
  "topics": [
    {
      "topic": "taste",
      "polarity": "positive",
      "evidence": "buburnya enak"
    },
    {
      "topic": "wait_time",
      "polarity": "negative",
      "evidence": "nunggunya lama"
    }
  ],
  "issue_summary": "Pelanggan menyukai produk tetapi mengalami waktu tunggu lama.",
  "urgency": "medium",
  "reputation_risk": "contained",
  "repeat_pattern_candidate": true,
  "responsible_role": "supervisor_operasional",
  "supporting_roles": ["kepala_outlet"],
  "recommended_public_response_intent": [
    "ucapkan terima kasih",
    "akui pengalaman pelanggan",
    "mohon maaf atas waktu tunggu",
    "nyatakan akan diperiksa"
  ],
  "recommended_internal_action": [
    "Periksa antrean dan pembagian tugas pada jam kunjungan.",
    "Bandingkan dengan review serupa pada outlet yang sama."
  ],
  "human_review_required": true,
  "confidence": {
    "sentiment": 0.95,
    "topics": 0.94,
    "urgency": 0.87,
    "recommended_route": 0.91
  }
}
```

## 12. REPEAT PATTERN DETECTION

Kelompokkan isu berdasarkan:

- outlet;
- topic;
- normalized issue;
- time window;
- similar language/embedding.

Jangan menyebut isu “berulang” hanya karena satu review.

Output:

```yaml
pattern_id:
topic:
outlet_id:
review_count:
time_window:
trend:
  increasing | stable | decreasing
supporting_review_ids:
confidence:
```

## 13. RATING VS TEXT CONFLICT

Contoh:

- rating 5 tetapi komentar negatif;
- rating 1 tetapi komentar memuji.

Rules:

- tandai `rating_text_mismatch: true`;
- jangan memaksakan sentiment berdasarkan rating;
- response route menggunakan risiko gabungan;
- minta human review bila mismatch material.

## 14. PROHIBITED ANALYSIS

Dilarang:

- diagnosis medis;
- kesimpulan legal;
- menyebut reviewer berbohong;
- mengidentifikasi identitas sensitif;
- profiling reviewer;
- mencari data pribadi reviewer;
- membuat klaim penyebab operasional tanpa verifikasi.

## 15. ACCEPTANCE CRITERIA

- Review campuran menghasilkan multi-topic polarity.
- Rating-only review tidak menghasilkan issue fiktif.
- Review kritis diberi urgency critical.
- Evidence berasal dari review asli.
- Output valid terhadap schema.
- Analysis dapat dilacak ke model dan policy version.
