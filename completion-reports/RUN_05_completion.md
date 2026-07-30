# RUN_05 — Review Analysis and Intelligence Dashboard

**Completed:** 2026-07-30
**Branch:** main

---

## Scope

Sentiment analysis, multi-topic detection, urgency classification, reputation risk,
rating-text mismatch, repeat-pattern detection, dashboard summary, priority queue,
outlet comparison, management summary.

## Deliverables

### New Files

| File | Lines | Description |
|------|-------|-------------|
| `app/services/analysis_service.py` | 969 | Analysis engine: sentiment, topic, urgency, risk, confidence, repeat-pattern |
| `app/routes/dashboard.py` | 202 | Intelligence dashboard blueprint + 5 API endpoints |
| `app/templates/dashboard/intelligence.html` | 481 | Dashboard UI template |
| `completion-reports/RUN_05_completion.md` | — | This report |

### Modified Files

| File | Change |
|------|--------|
| `app/templates/base.html` | Added "Intelijen" navbar link |
| `app/services/analysis_service.py` | Rewrote `_detect_sentiment`: token-level matching + negation handling |

### Tests

| Gate | Tests | Status |
|------|-------|--------|
| **Gate E** — AI Review Analysis | 81 | ✅ ALL PASS |
| **Gate I** — Dashboard API | 77 | ✅ ALL PASS |

### Regression

| Gate | Tests | Status |
|------|-------|--------|
| Gate B — Brand Discovery | 9 | ✅ ALL PASS |
| Gate C — Google Connection | 75 | ✅ ALL PASS |
| Gate D — Synchronization | 13 ⚑ | ✅ PASS (silent) |
| Gate E — AI Analysis | 81 | ✅ ALL PASS |
| Gate I — Dashboard API | 77 | ✅ ALL PASS |

### Architecture

```
┌─────────────────────┐
│  Dashboard Blueprint │  /dashboard/intelligence (page)
│  /dashboard/api/... │  5 API endpoints
├─────────────────────┤
│  analysis_service   │  analyze_review() — main entry
│                     │  get_dashboard_summary()
│                     │  get_priority_reviews()
│                     │  get_outlet_comparison()
│                     │  get_management_summary()
│                     │  batch_analyze_pending()
├─────────────────────┤
│  _detect_sentiment  │  Token-based + negation + intensifier
│  _classify_topics   │  Keyword matching → topic/polarity/evidence
│  _detect_urgency    │  Keywords → low/medium/high/critical
│  _detect_reputation │  Illness/legal/mismatch → minimal→severe
│  _check_mismatch    │  Star rating vs text contradiction
│  _detect_repeat     │  Similar reviews at same outlet
└─────────────────────┘
```

### Sentiment Engine Fixes

1. **Removed "sangat" from POSITIVE_WORDS** — handled as intensifier
2. **Token-level matching** — `split()` to avoid substring false matches
3. **Negation handling** — `tidak/gak + positif` counted as negative
4. **Compound negative precedence** — "tidak enak" matched as bigram first
5. **"sangat X" rule** — next word determines polarity
6. **Punctuation stripping** — `. , ! ? ; :` removed from tokens

## Next

- RUN_06 — not started
