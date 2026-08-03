"""Review analysis service — rule-based sentiment, topic, urgency, and risk analysis.

Provides deterministic analysis for review text based on keyword matching
and heuristic rules. Designed to be replaced with an AI/LLM-based analysis
in production while maintaining the same output schema.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app import db
from app.models.entities import Review, ReviewAnalysis, Outlet

logger = logging.getLogger(__name__)

# ─── CONSTANTS ──────────────────────────────────────────────

ANALYSIS_VERSION = 1
POLICY_VERSION = "run05-v1.0"

# ─── KEYWORD LISTS ─────────────────────────────────────────

_POSITIVE_WORDS = {
    "enak", "mantap", "puas", "recommended", "recommend",
    "recommendation", "terbaik", "baik", "ramah", "cepat", "bersih",
    "nyaman", "murah", "pas", "cocok", "suka", "oke",
    "top", "wow", "best", "good", "great", "nice", "excellent",
    "favorite", "favourite", "love", "satisfied", "amazing",
    "delicious", "friendly", "clean", "fast", "comfortable",
    "affordable", "worth", "value",
    "delicioso", "mantap", "enak", "lezat", "nikmat", "gurih", "segar",
    "mantapp",
}

_NEGATIVE_WORDS = {
    "buruk", "parah", "kecewa", "mengecewakan", "lambat", "lamban",
    "mahal", "tidak enak", "tidak puas", "kurang", "jelek", "busuk",
    "basi", "sakit perut", "diare", "mual", "jijik", "tidak ramah",
    "tidak bersih", "kotor", "lama", "tidak nyaman", "sebal",
    "kesal", "marah", "benci", "gak enak", "gak puas", "gak ramah",
    "gak bersih", "no", "bad", "terrible", "awful", "horrible",
    "disgusting", "worst", "poor", "dissatisfied", "unfriendly",
    "rude", "dirty", "slow", "expensive", "overpriced",
    "judes", "kasar", "galak", "cuek", "diabaikan", "tidak respon",
    "tidak sopan", "tidak dilayani", "mengecil", "hambar", "tawar",
    "berubah", "tidak sesuai", "bocor", "tumpah",
}

_NEGATION_PREFIXES = {"tidak", "gak", "nggak", "enggak", "ga", "tak", "bukan"}
_INTENSIFIERS = {"sangat", "terlalu", "begitu"}

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "taste": ["enak", "rasa", "bumbu", "sedap", "gurih", "manis", "asin",
              "asin", "hambar", "tawar", "lezat", "nikmat"],
    "food_quality": ["kualitas", "bahan", "segar", "fresh", "basah", "kering",
                     "matang", "mentah"],
    "temperature": ["panas", "dingin", "hangat", "suam", "dingin"],
    "portion": ["porsi", "sedikit", "banyak", "kekenyangan", "kurang",
                "banyak", "ukuran", "besar", "kecil"],
    "consistency": ["konsisten", "beda", "sama", "berubah", "stabil"],
    "menu_availability": ["habis", "tidak ada", "tersedia", "kosong",
                          "out of stock", "stok", "menu"],
    "friendliness": ["ramah", "sopan", "baik", "senyum", "tidak ramah",
                     "judes", "kasar", "galak", "cuek"],
    "speed": ["cepat", "lambat", "lama", "ngebut", "terlalu lama"],
    "accuracy": ["akurat", "salah", "benar", "cocok", "sesuai", "pesan",
                 "pilihan"],
    "staff_attitude": ["karyawan", "staff", "staf", "pegawai", "kasir",
                       "pelayan", "waiter", "waitress"],
    "complaint_handling": ["komplain", "keluhan", "maaf", "minta ganti",
                           "ganti", "refund", "kembali"],
    "wait_time": ["tunggu", "lama", "ngantri", "antri", "antre", "queue",
                  "menunggu", "nunggu", "delay"],
    "cleanliness": ["bersih", "kotor", "jijik", "liat", "debu", "sampah",
                    "kuman", "higienis"],
    "comfort": ["nyaman", "tidak nyaman", "pengap", "panas", "ac", "sejuk"],
    "atmosphere": ["suasana", "atmosfer", "musik", "dekorasi", "interior",
                   "cahaya", "pencahayaan"],
    "parking": ["parkir", "mobil", "motor", "tempat parkir"],
    "expensive": ["mahal", "kemahalan", "pricey", "overprice", "overpriced"],
    "value_for_money": ["worth", "value", "harga", "murah", "terjangkau",
                        "sebanding", "sesuai"],
    "food_safety": ["basi", "diare", "mual", "muntah", "keracunan",
                    "kesehatan", "kadaluarsa", "kedaluwarsa", "belatung",
                    "ulat", "kecoa", "lalat", "sakit perut"],
    "delivery_delay": ["delivery", "ojol", "gofood", "grab", "shopeefood",
                       "anter", "kurir", "telat sampai"],
    "packaging": ["packaging", "bungkus", "kemasan", "bocor", "tumpah"],
}

_ILLNESS_KEYWORDS = ["sakit perut", "diare", "mual", "muntah", "keracunan", "basi",
                     "demam", "sakit perut"]
_CHEMICAL_KEYWORDS = ["kecoa", "belatung", "ulat", "lalat", "rambut", "kuku"]
_LEGAL_KEYWORDS = ["lapor", "polisi", "pengacara", "hukum", "tuntut",
                   "gugat", "bpom", "dinas"]
_VIRAL_KEYWORDS = ["viral", "share", "sebarkan", "medsos", "tiktok",
                   "instagram", "tagar"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── SENTIMENT DETECTION ─────────────────────────────────

def _detect_sentiment(text: str) -> tuple[str, list[str], float]:
    """Detect sentiment based on token-level keyword matching with negation
    handling and intensifier support.

    Rules:
      1. Compound negatives (bigrams in NEGATIVE_WORDS) are matched first.
      2. "sangat/terlalu X" — X determines polarity.
      3. Negation prefix + positive word = negative.
      4. Single word matching with word boundaries.

    Returns (sentiment_label, reasons, confidence).
    """
    text_lower = text.lower()
    # Strip common punctuation from tokens for matching
    _strip_table = str.maketrans('', '', '.,!?;:()[]{}"\'')
    tokens = [t.translate(_strip_table) for t in text_lower.split() if t.translate(_strip_table)]
    used: set[int] = set()
    pos_count = 0
    neg_count = 0

    # Pass 1: compound negatives (bigrams already in NEGATIVE_WORDS like "tidak enak")
    for i in range(len(tokens) - 1):
        if i in used or i + 1 in used:
            continue
        bigram = tokens[i] + " " + tokens[i + 1]
        if bigram in _NEGATIVE_WORDS:
            neg_count += 1
            used.add(i)
            used.add(i + 1)

    # Pass 2: intensifier + word (sangat/terlalu/begitu X)
    for i in range(len(tokens) - 1):
        if i in used or i + 1 in used:
            continue
        if tokens[i] in _INTENSIFIERS:
            nxt = tokens[i + 1]
            if nxt in _POSITIVE_WORDS:
                pos_count += 1
                used.add(i)
            elif nxt in _NEGATIVE_WORDS:
                neg_count += 1
                used.add(i)

    # Pass 3: negation prefix + positive word = negative
    for i in range(len(tokens) - 1):
        if i in used or i + 1 in used:
            continue
        if tokens[i] in _NEGATION_PREFIXES and tokens[i + 1] in _POSITIVE_WORDS:
            neg_count += 1
            used.add(i)
            used.add(i + 1)

    # Pass 4: single word matching
    for i, token in enumerate(tokens):
        if i in used:
            continue
        if token in _POSITIVE_WORDS:
            pos_count += 1
        elif token in _NEGATIVE_WORDS:
            neg_count += 1

    reasons: list[str] = []
    confidence = 0.9

    if pos_count > 0 and neg_count == 0:
        label = "positive"
        reasons.append("Review mengandung pujian atau ekspresi positif.")
        confidence = min(0.95, 0.8 + pos_count * 0.05)
    elif neg_count > 0 and pos_count == 0:
        label = "negative"
        reasons.append("Review mengandung keluhan atau ekspresi negatif.")
        confidence = min(0.95, 0.8 + neg_count * 0.05)
    elif pos_count > 0 and neg_count > 0:
        label = "mixed"
        reasons.append("Terdapat pujian dan keluhan dalam satu review.")
        confidence = 0.85
    else:
        label = "neutral"
        reasons.append("Review bersifat netral atau informatif.")
        confidence = 0.7

    return label, reasons, confidence


# ─── TOPIC CLASSIFICATION ────────────────────────────────

def _classify_topics(text: str) -> list[dict[str, Any]]:
    """Classify topics based on keyword matching.

    Returns list of {topic, polarity, evidence}.
    """
    text_lower = text.lower()
    topics: list[dict[str, Any]] = []
    seen_topics: set[str] = set()

    for topic, keywords in _TOPIC_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in text_lower]
        if matched:
            # Determine polarity from context
            if any(w in text_lower for w in _NEGATIVE_WORDS):
                # Check if negative word is near the topic keyword
                negative_nearby = any(
                    _word_distance(text_lower, matched[0], neg) < 10
                    for neg in _NEGATIVE_WORDS
                    if neg in text_lower
                )
                polarity = "negative" if negative_nearby else "positive"
            else:
                polarity = "positive"

            seen_topics.add(topic)
            topics.append({
                "topic": topic,
                "polarity": polarity,
                "evidence": matched[0],
            })

    return topics


def _word_distance(text: str, w1: str, w2: str) -> int:
    """Approximate word distance between two words in text."""
    words = text.split()
    try:
        i1 = next(i for i, w in enumerate(words) if w1 in w)
        i2 = next(i for i, w in enumerate(words) if w2 in w)
        return abs(i1 - i2)
    except StopIteration:
        return 999


# ─── URGENCY DETECTION ──────────────────────────────────

def _detect_urgency(
    sentiment: str,
    topics: list[dict],
    text: str,
) -> str:
    """Determine urgency level."""
    text_lower = text.lower()

    # Critical
    if any(kw in text_lower for kw in _ILLNESS_KEYWORDS + _CHEMICAL_KEYWORDS):
        return "critical"

    # High
    if any(kw in text_lower for kw in _LEGAL_KEYWORDS + _VIRAL_KEYWORDS):
        return "critical"

    if sentiment == "negative":
        if any(t["topic"] in ("food_safety", "discrimination", "harassment")
               for t in topics):
            return "high"
        if any(t["topic"] in ("staff_attitude", "cleanliness", "wrong_order")
               for t in topics):
            return "high"
        return "medium"

    # Medium
    if sentiment == "mixed":
        return "medium"

    # Low
    return "low"


# ─── REPUTATION RISK ────────────────────────────────────

def _detect_reputation_risk(
    sentiment: str,
    urgency: str,
    text: str,
    has_rating_text_mismatch: bool,
) -> str:
    """Determine reputation risk level."""
    text_lower = text.lower()

    # Severe triggers
    if any(kw in text_lower for kw in _ILLNESS_KEYWORDS):
        return "severe"

    if any(kw in text_lower for kw in _LEGAL_KEYWORDS + _CHEMICAL_KEYWORDS):
        return "severe"

    if has_rating_text_mismatch and urgency in ("high", "critical"):
        return "elevated"

    if urgency == "critical":
        return "severe"

    if urgency == "high":
        return "elevated"

    if urgency == "medium":
        return "contained"

    return "minimal"


# ─── RESPONSIBLE ROLE ───────────────────────────────────

def _determine_responsible_role(
    topics: list[dict],
    urgency: str,
) -> tuple[str, list[str]]:
    """Determine primary responsible role and supporting roles."""
    topic_names = {t["topic"] for t in topics}

    if "food_safety" in topic_names or urgency == "critical":
        return "owner", ["legal_or_compliance", "quality_control"]

    if "staff_attitude" in topic_names or "friendliness" in topic_names:
        return "human_resources", ["kepala_outlet"]

    if "taste" in topic_names or "food_quality" in topic_names or "temperature" in topic_names:
        return "kepala_dapur", ["quality_control"]

    if "wait_time" in topic_names or "speed" in topic_names:
        return "supervisor_operasional", ["kepala_outlet"]

    if "cleanliness" in topic_names or "comfort" in topic_names:
        return "kepala_outlet", ["supervisor_operasional"]

    if "expensive" in topic_names or "value_for_money" in topic_names:
        return "marketing", ["owner"]

    if "delivery_delay" in topic_names or "packaging" in topic_names:
        return "supervisor_operasional", ["customer_service"]

    return "customer_service", ["kepala_outlet"]


# ─── RATING-TEXT MISMATCH ───────────────────────────────

def _check_rating_text_mismatch(
    star_rating: int,
    sentiment: str,
    text: str,
) -> bool:
    """Detect mismatch between star rating and review text sentiment."""
    if not text or not text.strip():
        return False

    text_lower = text.lower()
    has_neg = any(w in text_lower for w in _NEGATIVE_WORDS)
    has_pos = any(w in text_lower for w in _POSITIVE_WORDS)

    # Rating 4-5 but text is negative
    if star_rating >= 4 and has_neg and not has_pos:
        return True

    # Rating 1-2 but text is positive
    if star_rating <= 2 and has_pos and not has_neg:
        return True

    return False


# ─── REPEAT PATTERN DETECTION ───────────────────────────

def _detect_repeat_patterns(
    tenant_id: str,
    outlet_id: str | None,
    topics: list[dict],
) -> bool:
    """Check if similar reviews exist for the same outlet/topic combination."""
    if not outlet_id or not topics:
        return False

    topic_names = {t["topic"] for t in topics}
    if not topic_names:
        return False

    # Count recent reviews with the same topics at the same outlet
    cutoff = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    # Look at last 30 days
    from datetime import timedelta
    cutoff = cutoff - timedelta(days=30)

    similar_reviews = (
        db.session.query(ReviewAnalysis.review_pk)
        .join(Review, Review.id == ReviewAnalysis.review_pk)
        .filter(
            Review.tenant_id == tenant_id,
            Review.outlet_id == outlet_id,
            ReviewAnalysis.created_at >= cutoff,
        )
        .all()
    )

    return len(similar_reviews) >= 2


# ─── CONFIDENCE ─────────────────────────────────────────

def _calculate_confidence(
    sentiment: str,
    topics: list[dict],
    text: str,
) -> dict[str, float]:
    """Calculate confidence scores."""
    text_len = len(text.strip()) if text else 0

    # Short text = lower confidence
    base = min(0.95, 0.5 + text_len * 0.01)

    if sentiment == "neutral":
        # Neutral is harder to determine
        base = max(0.5, base - 0.2)

    return {
        "sentiment": round(min(0.99, base + 0.05), 2),
        "topics": round(min(0.95, base), 2),
        "urgency": round(min(0.95, base), 2),
        "recommended_route": round(min(0.95, base), 2),
    }


# ─── INTERNAL ACTIONS ───────────────────────────────────

def _generate_internal_actions(
    topics: list[dict],
    urgency: str,
    sentiment: str,
) -> list[str]:
    """Generate recommended internal actions."""
    actions: list[str] = []
    topic_names = {t["topic"] for t in topics}

    if "taste" in topic_names:
        actions.append("Periksa konsistensi rasa dengan standar resep.")
    if "food_quality" in topic_names:
        actions.append("Evaluasi kualitas bahan baku yang digunakan.")
    if "food_safety" in topic_names or urgency == "critical":
        actions.append("⚠️ TINDAKAN SEGERA: Periksa keamanan pangan dan lacak bahan.")
    if "wait_time" in topic_names or "speed" in topic_names:
        actions.append("Tinjau alur kerja dan pembagian tugas saat jam sibuk.")
    if "friendliness" in topic_names or "staff_attitude" in topic_names:
        actions.append("Tindak lanjuti dengan kepala outlet terkait pelayanan staf.")
    if "cleanliness" in topic_names:
        actions.append("Lakukan inspeksi kebersihan area secara menyeluruh.")
    if "expensive" in topic_names or "value_for_money" in topic_names:
        actions.append("Kaji ulang strategi harga dibandingkan pesaing.")
    if "parking" in topic_names:
        actions.append("Evaluasi akses parkir untuk pelanggan.")
    if "delivery_delay" in topic_names:
        actions.append("Koordinasi dengan mitra delivery untuk memperbaiki estimasi waktu.")

    if not actions:
        actions.append("Pantau review lebih lanjut untuk tren.")
    if urgency == "high":
        actions.append("Laporkan temuan ke kepala outlet untuk ditindaklanjuti.")

    return actions


def _generate_public_response_intent(
    sentiment: str,
    urgency: str,
    topics: list[dict],
    has_text: bool,
) -> list[str]:
    """Generate recommended public response intent."""
    if not has_text or sentiment == "not_applicable":
        return []

    intents: list[str] = []

    if sentiment in ("positive",):
        intents.append("Ucapkan terima kasih atas ulasan.")
        intents.append("Sampaikan apresiasi kepada pelanggan.")
        return intents

    intents.append("Akui pengalaman pelanggan.")
    intents.append("Mohon maaf atas ketidaknyamanan.")

    if urgency in ("high", "critical"):
        intents.append("Nyatakan akan menyelidiki secara internal.")
        intents.append("Tawarkan tindak lanjut melalui jalur pribadi.")
    else:
        intents.append("Sampaikan komitmen untuk terus memperbaiki diri.")

    return intents


# ─── MAIN ANALYSIS FUNCTION ─────────────────────────────

def analyze_review(
    tenant_id: str,
    business_id: str,
    review_id: str,
) -> dict[str, Any]:
    """Analyze a single review and store the result in review_analyses.

    Returns the analysis dict.
    """
    review = db.session.get(Review, review_id)
    if not review:
        raise ValueError(f"Review {review_id} not found")

    # Validate tenant ownership
    if review.tenant_id != tenant_id or review.business_id != business_id:
        raise ValueError("Tenant/business mismatch")

    has_text = bool(review.comment and review.comment.strip())
    text = review.comment or ""

    # Rating-only: mark as not_applicable
    if not has_text:
        analysis_entry = ReviewAnalysis(
            review_pk=review_id,
            analysis_version=ANALYSIS_VERSION,
            model_name="rule-based-v1",
            policy_version=POLICY_VERSION,
            sentiment="not_applicable",
            topics_json=[],
            issue_summary="Rating-only review, tidak ada analisis teks.",
            urgency="low",
            reputation_risk="minimal",
            repeat_pattern_candidate=False,
            responsible_role=None,
            recommended_public_response_intent_json=[],
            recommended_internal_action_json=[],
            human_review_required=False,
            confidence_json=json.dumps({
                "sentiment": 1.0,
                "topics": 1.0,
                "urgency": 1.0,
                "recommended_route": 1.0,
            }),
        )
        db.session.add(analysis_entry)

        # Update review status
        review.qualitative_analysis_status = "not_applicable"
        review.analysis_reassessment_required = False
        db.session.commit()

        return _analysis_to_dict(analysis_entry)

    # Has text — perform analysis
    sentiment, sentiment_reasons, sent_confidence = _detect_sentiment(text)
    topics = _classify_topics(text)
    rating_text_mismatch = _check_rating_text_mismatch(
        review.star_rating, sentiment, text
    )
    urgency = _detect_urgency(sentiment, topics, text)
    reputation_risk = _detect_reputation_risk(
        sentiment, urgency, text, rating_text_mismatch
    )
    role, supporting_roles = _determine_responsible_role(topics, urgency)

    # Repeat pattern
    repeat = _detect_repeat_patterns(tenant_id, review.outlet_id, topics)

    # Confidence
    confidence = _calculate_confidence(sentiment, topics, text)

    # Human review check
    human_review = (
        rating_text_mismatch
        or urgency in ("high", "critical")
        or sentiment == "mixed"
        or sentiment == "negative"
        or any(confidence[v] < 0.7 for v in confidence)
    )

    # Issue summary
    if sentiment == "positive":
        issue_summary = "Ulasan positif. "
    elif sentiment == "negative":
        issue_summary = "Ulasan negatif. "
    elif sentiment == "mixed":
        issue_summary = "Terdapat pujian dan keluhan dalam ulasan. "
    else:
        issue_summary = "Ulasan netral. "

    if topics:
        topic_names = [t["topic"] for t in topics]
        issue_summary += f"Topik: {', '.join(topic_names)}."

    internal_actions = _generate_internal_actions(topics, urgency, sentiment)
    response_intents = _generate_public_response_intent(
        sentiment, urgency, topics, has_text
    )

    # Build analysis record
    analysis_entry = ReviewAnalysis(
        review_pk=review_id,
        analysis_version=ANALYSIS_VERSION,
        model_name="rule-based-v1",
        policy_version=POLICY_VERSION,
        sentiment=sentiment,
        topics_json=json.dumps(topics),
        issue_summary=issue_summary,
        urgency=urgency,
        reputation_risk=reputation_risk,
        repeat_pattern_candidate=repeat,
        responsible_role=role,
        recommended_public_response_intent_json=json.dumps(response_intents),
        recommended_internal_action_json=json.dumps(internal_actions),
        human_review_required=human_review,
        confidence_json=json.dumps(confidence),
    )
    db.session.add(analysis_entry)

    # Update review record
    review.qualitative_analysis_status = "analyzed"
    review.analysis_reassessment_required = False
    db.session.commit()

    return _analysis_to_dict(analysis_entry)


def _analysis_to_dict(analysis: ReviewAnalysis) -> dict[str, Any]:
    """Convert ReviewAnalysis model to dict."""
    return {
        "id": analysis.id,
        "review_pk": analysis.review_pk,
        "analysis_version": analysis.analysis_version,
        "model_name": analysis.model_name,
        "policy_version": analysis.policy_version,
        "sentiment": analysis.sentiment,
        "topics_json": analysis.topics_json,
        "issue_summary": analysis.issue_summary,
        "urgency": analysis.urgency,
        "reputation_risk": analysis.reputation_risk,
        "repeat_pattern_candidate": analysis.repeat_pattern_candidate,
        "responsible_role": analysis.responsible_role,
        "recommended_public_response_intent_json": analysis.recommended_public_response_intent_json,
        "recommended_internal_action_json": analysis.recommended_internal_action_json,
        "human_review_required": analysis.human_review_required,
        "confidence_json": analysis.confidence_json,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }


# ─── BATCH ANALYSIS ─────────────────────────────────────

def batch_analyze_pending(
    tenant_id: str,
    business_id: str,
    limit: int = 50,
) -> dict[str, Any]:
    """Analyze all reviews that need analysis."""
    pending = (
        Review.query.filter_by(
            tenant_id=tenant_id,
            business_id=business_id,
            analysis_reassessment_required=True,
        )
        .order_by(Review.update_time.desc())
        .limit(limit)
        .all()
    )

    results = []
    for review in pending:
        try:
            result = analyze_review(tenant_id, business_id, review.id)
            results.append(result)
        except Exception:
            logger.exception("Failed to analyze review %s", review.id)

    return {
        "analyzed": len(results),
        "total_pending": len(pending),
        "results": results,
    }


# ─── DASHBOARD QUERIES ──────────────────────────────────

def get_dashboard_summary(
    tenant_id: str,
    business_id: str,
    outlet_id: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """Get dashboard summary metrics."""
    from datetime import timedelta

    cutoff = _now() - timedelta(days=days)

    base_q = Review.query.filter_by(
        tenant_id=tenant_id,
        business_id=business_id,
    ).filter(Review.create_time >= cutoff)

    if outlet_id:
        base_q = base_q.filter(Review.outlet_id == outlet_id)

    total_reviews = base_q.count()
    all_reviews = base_q.all()

    rating_only = sum(1 for r in all_reviews if not r.has_text)
    with_text = sum(1 for r in all_reviews if r.has_text)

    # Sentiment counts
    positive = 0
    negative = 0
    mixed = 0
    neutral = 0
    sentiments_analyzed = 0

    for r in all_reviews:
        analysis = ReviewAnalysis.query.filter_by(
            review_pk=r.id
        ).order_by(ReviewAnalysis.created_at.desc()).first()
        if analysis:
            sentiments_analyzed += 1
            if analysis.sentiment == "positive":
                positive += 1
            elif analysis.sentiment == "negative":
                negative += 1
            elif analysis.sentiment == "mixed":
                mixed += 1
            elif analysis.sentiment == "neutral":
                neutral += 1

    # Urgency counts
    high_urgency = 0
    critical = 0
    unanswered = 0

    from app.models.entities import ReviewReply
    for r in all_reviews:
        analysis = ReviewAnalysis.query.filter_by(
            review_pk=r.id
        ).order_by(ReviewAnalysis.created_at.desc()).first()
        if analysis:
            if analysis.urgency == "high":
                high_urgency += 1
            if analysis.urgency == "critical":
                critical += 1
        # Check if any reply exists
        reply = ReviewReply.query.filter_by(
            review_pk=r.id
        ).first()
        if not reply:
            unanswered += 1

    # Average rating
    ratings = [r.star_rating for r in all_reviews if r.star_rating]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

    return {
        "period_days": days,
        "total_reviews": total_reviews,
        "average_rating": avg_rating,
        "rating_only_reviews": rating_only,
        "sentiments_analyzed": sentiments_analyzed,
        "sentiments": {
            "positive": positive,
            "negative": negative,
            "mixed": mixed,
            "neutral": neutral,
        },
        "high_urgency_open": high_urgency,
        "critical_open": critical,
        "unanswered_reviews": unanswered,
    }


def get_priority_reviews(
    tenant_id: str,
    business_id: str,
    outlet_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get priority review queue — critical/high urgency + human review required first."""
    base_q = (
        db.session.query(Review, ReviewAnalysis)
        .join(ReviewAnalysis, ReviewAnalysis.review_pk == Review.id)
        .filter(
            Review.tenant_id == tenant_id,
            Review.business_id == business_id,
        )
    )

    if outlet_id:
        base_q = base_q.filter(Review.outlet_id == outlet_id)

    # Order: critical first, then high, then human_review
    from sqlalchemy import case

    urgency_order = case(
        (ReviewAnalysis.urgency == "critical", 0),
        (ReviewAnalysis.urgency == "high", 1),
        (ReviewAnalysis.urgency == "medium", 2),
        else_=3,
    )

    rows = (
        base_q
        .order_by(urgency_order, Review.update_time.desc())
        .limit(limit)
        .all()
    )

    outlets = {
        o.id: o.name
        for o in Outlet.query.filter_by(tenant_id=tenant_id, business_id=business_id).all()
    }

    result = []
    for review, analysis in rows:
        result.append({
            "review_id": review.id,
            "outlet": outlets.get(review.outlet_id, "Unknown"),
            "outlet_id": review.outlet_id,
            "rating": review.star_rating,
            "comment_preview": (review.comment or "")[:120],
            "has_text": review.has_text,
            "review_date": review.create_time.isoformat() if review.create_time else None,
            "sentiment": analysis.sentiment,
            "urgency": analysis.urgency,
            "reputation_risk": analysis.reputation_risk,
            "human_review_required": analysis.human_review_required,
        })

    return result


def get_outlet_comparison(
    tenant_id: str,
    business_id: str,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Get outlet comparison data."""
    from datetime import timedelta

    cutoff = _now() - timedelta(days=days)

    outlets = Outlet.query.filter_by(
        tenant_id=tenant_id, business_id=business_id,
        monitor_enabled=True,
    ).all()

    result = []
    for outlet in outlets:
        reviews = Review.query.filter_by(
            tenant_id=tenant_id,
            business_id=business_id,
            outlet_id=outlet.id,
        ).filter(Review.create_time >= cutoff).all()

        if not reviews:
            continue

        ratings = [r.star_rating for r in reviews if r.star_rating]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

        negative_count = 0
        high_urgency_count = 0
        critical_count = 0

        for r in reviews:
            analysis = ReviewAnalysis.query.filter_by(
                review_pk=r.id
            ).order_by(ReviewAnalysis.created_at.desc()).first()
            if analysis:
                if analysis.sentiment == "negative":
                    negative_count += 1
                if analysis.urgency == "high":
                    high_urgency_count += 1
                if analysis.urgency == "critical":
                    critical_count += 1

        total = len(reviews)
        negative_pct = round(negative_count / total * 100, 1) if total else 0.0

        result.append({
            "outlet_id": outlet.id,
            "outlet_name": outlet.name,
            "average_rating": avg_rating,
            "new_reviews": total,
            "negative_percentage": negative_pct,
            "high_urgency_count": high_urgency_count,
            "critical_count": critical_count,
        })

    # Sort by avg rating ascending (worst first)
    result.sort(key=lambda x: x["average_rating"])
    return result


def get_management_summary(
    tenant_id: str,
    business_id: str,
    days: int = 30,
) -> dict[str, Any]:
    """Generate management summary."""
    from datetime import timedelta

    cutoff = _now() - timedelta(days=days)
    prev_cutoff = cutoff - timedelta(days=days)

    # Current period
    current_reviews = Review.query.filter_by(
        tenant_id=tenant_id, business_id=business_id,
    ).filter(Review.create_time >= cutoff).all()

    # Previous period
    previous_reviews = Review.query.filter_by(
        tenant_id=tenant_id, business_id=business_id,
    ).filter(
        Review.create_time >= prev_cutoff,
        Review.create_time < cutoff,
    ).all()

    current_ratings = [r.star_rating for r in current_reviews if r.star_rating]
    prev_ratings = [r.star_rating for r in previous_reviews if r.star_rating]

    current_avg = round(sum(current_ratings) / len(current_ratings), 2) if current_ratings else 0.0
    prev_avg = round(sum(prev_ratings) / len(prev_ratings), 2) if prev_ratings else 0.0
    change = round(current_avg - prev_avg, 2)

    # Count sentiments
    sent_counts = {"positive": 0, "negative": 0, "mixed": 0, "neutral": 0}
    for r in current_reviews:
        a = ReviewAnalysis.query.filter_by(review_pk=r.id).order_by(
            ReviewAnalysis.created_at.desc()
        ).first()
        if a and a.sentiment in sent_counts:
            sent_counts[a.sentiment] += 1

    # Top praises and complaints
    outlet_data = get_outlet_comparison(tenant_id, business_id, days)

    priority = get_priority_reviews(tenant_id, business_id, limit=5)

    return {
        "period_days": days,
        "executive_summary": (
            f"Rata-rata rating {current_avg} dalam {days} hari terakhir "
            f"({'+' if change >= 0 else ''}{change} dari periode sebelumnya). "
            f"Total {len(current_reviews)} review baru diterima."
        ),
        "rating": {
            "current": current_avg,
            "previous": prev_avg,
            "change": change,
        },
        "reviews": {
            "total_new": len(current_reviews),
            "positive": sent_counts["positive"],
            "negative": sent_counts["negative"],
            "mixed": sent_counts["mixed"],
            "neutral": sent_counts["neutral"],
        },
        "outlet_comparison": outlet_data,
        "priority_reviews": priority[:5],
        "recommended_management_actions": [
            "Tinjau outlet dengan rating terendah untuk perbaikan operasional.",
            "Prioritaskan review kritis yang memerlukan respon segera.",
            "Pantau tren sentiment untuk mendeteksi perubahan reputasi.",
        ],
        "data_limitations": [
            "Analisis menggunakan model rule-based, belum AI/LLM.",
            "Google API masih dalam mode mock.",
        ],
        "generated_at": _now().isoformat(),
    }
