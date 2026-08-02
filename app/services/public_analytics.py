"""Public monitoring analytics — filters, aggregation, explorer, export.

Implements the GRM_PUBLIC_MONITORING_SKILL dashboard contract (§10-§12):
- Global filters: period, province, city/regency, district, branch, category,
  rating, sentiment, urgency, source, has_reply, rating_only.
- Modules: executive summary, per-category, per-branch, per-geography,
  period analytics, review explorer, priority insights, export.
- Reviewer masking on every output; rating-only reviews never get fake text
  categories.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app import db
from app.models.entities import Business, Outlet, Review, ReviewAnalysis

logger = logging.getLogger(__name__)

# ─── CATEGORY TAXONOMY (skill §9) ──────────────────────────
# Label → analysis topic ids. Multi-label allowed.
CATEGORY_TOPICS = {
    "rasa/kualitas produk": ["taste", "food_quality", "temperature", "consistency"],
    "pelayanan": ["friendliness", "staff_attitude", "accuracy", "complaint_handling"],
    "kecepatan/waktu tunggu": ["speed", "wait_time"],
    "kebersihan": ["cleanliness"],
    "harga": ["expensive", "value_for_money"],
    "porsi": ["portion"],
    "suasana/tempat": ["comfort", "atmosphere"],
    "parkir": ["parking"],
    "pesanan online/delivery": ["delivery_delay", "packaging"],
    "ketersediaan menu/stok": ["menu_availability"],
    "fasilitas": [],
    "kritis": ["food_safety"],
}

CATEGORY_RECOMMENDATIONS = {
    "rasa/kualitas produk": "Evaluasi resep & kualitas bahan baku di cabang terdampak.",
    "pelayanan": "Tingkatkan pelatihan standar pelayanan & SOP interaksi pelanggan.",
    "kecepatan/waktu tunggu": "Optimalkan antrean & tambah tenaga di jam sibuk.",
    "kebersihan": "Audit kebersihan dapur & area makan, perketat SOP kebersihan.",
    "harga": "Tinjau strategi harga & komunikasikan nilai produk.",
    "porsi": "Standarisasi porsi & lakukan quality check sebelum disajikan.",
    "suasana/tempat": "Perbaiki kenyamanan tempat (AC, pencahayaan, tata ruang).",
    "parkir": "Koordinasikan area parkir & kelancaran akses kendaraan.",
    "pesanan online/delivery": "Perketat pengecekan pesanan online sebelum dikirim.",
    "ketersediaan menu/stok": "Perbaiki perencanaan stok & manajemen ketersediaan menu.",
    "fasilitas": "Evaluasi kelengkapan fasilitas pendukung pelanggan.",
    "kritis": "Tindak lanjut segera: investigasi, komunikasi publik, laporan internal.",
}


def _now():
    return datetime.now(timezone.utc)


def mask_reviewer(name) -> str:
    """Mask a reviewer name — keep first word + initial of second word."""
    if not name or name.strip().lower() in ("", "anonim", "anonymous"):
        return "Anonim"
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0][:1] + "***"
    return parts[0] + " " + parts[1][:1] + "***"


def _parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_filters(args: dict) -> dict:
    """Parse global dashboard filters from query args."""
    f = {}
    f["days"] = None
    days_raw = args.get("days")
    if days_raw and days_raw.isdigit():
        d = int(days_raw)
        f["days"] = d if d in (7, 14, 30, 90) else None

    f["month"] = args.get("month")  # YYYY-MM
    f["start"] = _parse_date(args.get("start_date") or args.get("start"))
    f["end"] = _parse_date(args.get("end_date") or args.get("end"))
    f["compare"] = args.get("compare", "").lower() in ("1", "true", "yes")

    f["province"] = args.get("province") or None
    f["city"] = args.get("city_regency") or args.get("city") or None
    f["district"] = args.get("district") or None
    f["outlet_ids"] = [x for x in (args.get("outlet_id") or "").split(",") if x] or None
    f["category"] = args.get("category") or None
    f["source"] = args.get("source") or None

    ratings = [x for x in (args.get("rating") or "").split(",") if x.isdigit()]
    f["ratings"] = [int(r) for r in ratings] or None
    f["sentiment"] = args.get("sentiment") or None
    f["urgency"] = args.get("urgency") or None

    hr = args.get("has_reply")
    f["has_reply"] = hr.lower() in ("1", "true", "yes") if hr else None
    ro = args.get("rating_only")
    f["rating_only"] = ro.lower() in ("1", "true", "yes") if ro else None
    to = args.get("text_only")
    f["text_only"] = to.lower() in ("1", "true", "yes") if to else None
    return f


def _resolve_period(f: dict):
    """Return (start, end, prev_start, prev_end) datetimes for the filter."""
    end = f.get("end") or _now()
    if f.get("start"):
        start = f["start"]
    elif f.get("month"):
        try:
            m = datetime.strptime(f["month"], "%Y-%m").replace(tzinfo=timezone.utc)
            start = m
            end = (m.replace(month=m.month + 1) - timedelta(seconds=1)) if m.month < 12 else m.replace(year=m.year + 1, month=1) - timedelta(seconds=1)
        except ValueError:
            start = end - timedelta(days=30)
    elif f.get("days"):
        start = end - timedelta(days=f["days"])
    else:
        start = end - timedelta(days=30)

    span = end - start
    prev_start = start - span
    prev_end = start - timedelta(seconds=1)
    return start, end, prev_start, prev_end


def _analysis(review) -> ReviewAnalysis:
    return ReviewAnalysis.query.filter_by(review_pk=review.id).first()


def _categories_for(review, analysis) -> list:
    """Map a review to taxonomy categories (multi-label). Empty for rating-only."""
    if not review.has_text:
        return []
    topics = []
    if analysis and analysis.topics_json:
        topics = analysis.topics_json
        if isinstance(topics, str):
            try:
                topics = json.loads(topics)
            except (ValueError, TypeError):
                topics = []
    topic_names = {
        (t.get("topic") if isinstance(t, dict) else str(t))
        for t in topics
    }
    cats = []
    for label, ids in CATEGORY_TOPICS.items():
        if ids and any(t in topic_names for t in ids):
            cats.append(label)
    return cats


def _sentiment(review, analysis) -> str:
    if not review.has_text:
        return "not_applicable"
    if analysis and analysis.sentiment:
        return analysis.sentiment
    # Fallback: rating-based
    if review.star_rating >= 4:
        return "positive"
    if review.star_rating == 3:
        return "neutral"
    return "negative"


def _urgency(review, analysis) -> str:
    if not review.has_text:
        return "none"
    return (analysis.urgency if analysis and analysis.urgency else "low")


def _base_reviews(tenant_id: str, business_id: str, f: dict, period=None):
    """Query reviews with global filters applied.

    ``period`` overrides the filter's own period (used for comparison).
    Returns list of (Review, Outlet) tuples.
    """
    start, end, _, _ = _resolve_period(f)
    if period:
        start, end = period

    q = (
        db.session.query(Review, Outlet)
        .join(Outlet, Review.outlet_id == Outlet.id)
        .filter(
            Review.tenant_id == tenant_id,
            Review.business_id == business_id,
        )
        .order_by(Review.create_time.desc())
    )
    if start:
        q = q.filter(Review.create_time >= start)
    if end:
        q = q.filter(Review.create_time <= end)
    if f.get("province"):
        q = q.filter(Outlet.province == f["province"])
    if f.get("city"):
        q = q.filter(Outlet.city_regency == f["city"])
    if f.get("district"):
        q = q.filter(Outlet.district == f["district"])
    if f.get("outlet_ids"):
        q = q.filter(Review.outlet_id.in_(f["outlet_ids"]))
    if f.get("ratings"):
        q = q.filter(Review.star_rating.in_(f["ratings"]))
    if f.get("source"):
        q = q.filter(Review.source == f["source"])
    if f.get("has_reply") is True:
        q = q.filter(Review.owner_reply_text.isnot(None))
    elif f.get("has_reply") is False:
        q = q.filter(Review.owner_reply_text.is_(None))
    if f.get("rating_only"):
        q = q.filter(Review.has_text == False)  # noqa: E712
    if f.get("text_only"):
        q = q.filter(Review.has_text == True)  # noqa: E712

    rows = q.all()
    result = []
    for review, outlet in rows:
        analysis = _analysis(review)
        cats = _categories_for(review, analysis)
        if f.get("category") and f["category"] not in cats:
            continue
        sent = _sentiment(review, analysis)
        if f.get("sentiment") and sent != f["sentiment"]:
            continue
        urg = _urgency(review, analysis)
        if f.get("urgency") and urg != f["urgency"]:
            continue
        result.append((review, outlet))
    return result


# ─── EXECUTIVE SUMMARY (§11.1) ─────────────────────────────
def executive_summary(tenant_id: str, business_id: str, f: dict) -> dict:
    start, end, prev_start, prev_end = _resolve_period(f)

    def _summarize(period):
        rows = _base_reviews(tenant_id, business_id, f, period=period)
        total = len(rows)
        if total == 0:
            return {"total": 0, "avg_rating": 0.0, "positive": 0, "neutral": 0,
                    "negative": 0, "mixed": 0, "rating_only": 0, "reviews": []}
        ratings = [r.star_rating for r, _ in rows]
        sent_counts = {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0}
        rating_only = 0
        for r, _ in rows:
            if not r.has_text:
                rating_only += 1
                continue
            s = _sentiment(r, _analysis(r))
            sent_counts[s] = sent_counts.get(s, 0) + 1
        return {
            "total": total,
            "avg_rating": round(sum(ratings) / total, 2),
            "positive": sent_counts["positive"],
            "neutral": sent_counts["neutral"],
            "negative": sent_counts["negative"],
            "mixed": sent_counts["mixed"],
            "rating_only": rating_only,
            "reviews": rows,
        }

    cur = _summarize((start, end))
    prev = _summarize((prev_start, prev_end)) if f.get("compare") else None

    # Category polarity across current period
    cat_polarity = {}
    for r, _ in cur["reviews"]:
        if not r.has_text:
            continue
        a = _analysis(r)
        cats = _categories_for(r, a)
        s = _sentiment(r, a)
        for c in cats:
            cat_polarity.setdefault(c, {"pos": 0, "neg": 0, "n": 0})
            cat_polarity[c]["n"] += 1
            if s == "positive":
                cat_polarity[c]["pos"] += 1
            elif s in ("negative", "mixed"):
                cat_polarity[c]["neg"] += 1

    issues = sorted(
        ((c, v["neg"]) for c, v in cat_polarity.items() if v["neg"] > 0),
        key=lambda x: x[1], reverse=True,
    )
    strengths = sorted(
        ((c, v["pos"]) for c, v in cat_polarity.items() if v["pos"] > 0),
        key=lambda x: x[1], reverse=True,
    )

    outlets = (
        Outlet.query.filter_by(tenant_id=tenant_id, business_id=business_id)
        .filter(Outlet.status != "old_or_closed")
        .all()
    )
    active_regions = sorted({o.city_regency for o in outlets if o.city_regency and o.city_regency != "unknown"})

    biz = Business.query.filter_by(id=business_id, tenant_id=tenant_id).first()

    priority_actions = [f"Tindak lanjut {c}" for c, _ in issues[:3]] or [
        "Tidak ada isu negatif signifikan pada periode ini"
    ]

    return {
        "business_name": biz.name if biz else "",
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "active_regions": active_regions,
        "branch_count": len(outlets),
        "total_reviews": cur["total"],
        "avg_rating": cur["avg_rating"],
        "positive": cur["positive"],
        "neutral": cur["neutral"],
        "negative": cur["negative"],
        "mixed": cur["mixed"],
        "rating_only": cur["rating_only"],
        "top_issues": [c for c, _ in issues[:3]],
        "top_strengths": [c for c, _ in strengths[:3]],
        "priority_actions": priority_actions,
        "comparison": (
            {
                "total_reviews": prev["total"],
                "avg_rating": prev["avg_rating"],
                "review_delta": cur["total"] - prev["total"],
                "rating_delta": round(cur["avg_rating"] - prev["avg_rating"], 2),
            }
            if prev
            else None
        ),
    }


# ─── CATEGORY BREAKDOWN (§11.2) ────────────────────────────
def category_breakdown(tenant_id: str, business_id: str, f: dict) -> dict:
    start, end, prev_start, prev_end = _resolve_period(f)
    rows = _base_reviews(tenant_id, business_id, f, period=(start, end))
    text_rows = [(r, o) for r, o in rows if r.has_text]

    counts = {c: [] for c in CATEGORY_TOPICS}
    for r, o in text_rows:
        a = _analysis(r)
        for c in _categories_for(r, a):
            counts[c].append((r, o))

    total_text = len(text_rows) or 1
    categories = []
    for label, items in counts.items():
        if not items:
            categories.append({
                "category": label, "count": 0, "percent_of_text": 0.0,
                "dominant_sentiment": "n/a", "avg_rating": 0.0, "trend": "flat",
                "top_cities": [], "top_districts": [], "top_branches": [],
                "example_reviews": [], "recommendation": CATEGORY_RECOMMENDATIONS[label],
            })
            continue
        sent = {}
        ratings = []
        cities, districts, branches = {}, {}, {}
        for r, o in items:
            a = _analysis(r)
            s = _sentiment(r, a)
            sent[s] = sent.get(s, 0) + 1
            ratings.append(r.star_rating)
            if o.city_regency and o.city_regency != "unknown":
                cities[o.city_regency] = cities.get(o.city_regency, 0) + 1
            if o.district and o.district != "unknown":
                districts[o.district] = districts.get(o.district, 0) + 1
            branches[o.name] = branches.get(o.name, 0) + 1
        dominant = max(sent.items(), key=lambda x: x[1])[0] if sent else "n/a"
        examples = [
            {
                "rating": r.star_rating,
                "snippet": (r.comment or "")[:160],
                "branch": o.name,
                "date": r.create_time.isoformat() if r.create_time else None,
                "reviewer": mask_reviewer(r.reviewer_display_name),
                "has_owner_reply": bool(r.owner_reply_text),
            }
            for r, o in sorted(items, key=lambda x: x[0].create_time or datetime.min, reverse=True)[:2]
        ]
        categories.append({
            "category": label,
            "count": len(items),
            "percent_of_text": round(len(items) / total_text * 100, 1),
            "dominant_sentiment": dominant,
            "avg_rating": round(sum(ratings) / len(ratings), 2),
            "trend": "up" if sent.get("negative", 0) < sent.get("positive", 0) else "down",
            "top_cities": sorted(cities.items(), key=lambda x: x[1], reverse=True)[:3],
            "top_districts": sorted(districts.items(), key=lambda x: x[1], reverse=True)[:3],
            "top_branches": sorted(branches.items(), key=lambda x: x[1], reverse=True)[:3],
            "example_reviews": examples,
            "recommendation": CATEGORY_RECOMMENDATIONS[label],
        })

    categories.sort(key=lambda x: x["count"], reverse=True)
    return {"categories": categories, "total_text_reviews": total_text}


# ─── BRANCH BREAKDOWN (§11.3) ──────────────────────────────
def branch_breakdown(tenant_id: str, business_id: str, f: dict) -> dict:
    start, end, prev_start, prev_end = _resolve_period(f)
    rows = _base_reviews(tenant_id, business_id, f, period=(start, end))
    by_outlet = {}
    for r, o in rows:
        by_outlet.setdefault(o.id, {"outlet": o, "reviews": []})
        by_outlet[o.id]["reviews"].append((r, o))

    branches = []
    for oid, entry in by_outlet.items():
        o = entry["outlet"]
        revs = entry["reviews"]
        ratings = [r.star_rating for r, _ in revs]
        sent = {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0}
        cat_pol = {}
        priority = []
        for r, _ in revs:
            if not r.has_text:
                continue
            a = _analysis(r)
            s = _sentiment(r, a)
            sent[s] = sent.get(s, 0) + 1
            for c in _categories_for(r, a):
                cat_pol.setdefault(c, {"pos": 0, "neg": 0})
                if s == "positive":
                    cat_pol[c]["pos"] += 1
                elif s in ("negative", "mixed"):
                    cat_pol[c]["neg"] += 1
            if r.star_rating <= 2:
                priority.append({
                    "rating": r.star_rating,
                    "snippet": (r.comment or "")[:140],
                    "date": r.create_time.isoformat() if r.create_time else None,
                    "urgency": _urgency(r, a),
                })
        praise = sorted(cat_pol.items(), key=lambda x: x[1]["pos"], reverse=True)[:3]
        complaints = sorted(cat_pol.items(), key=lambda x: x[1]["neg"], reverse=True)[:3]
        repeat_issues = [c for c, v in cat_pol.items() if v["neg"] >= 2][:5]
        branches.append({
            "branch_id": o.id,
            "branch_name": o.name,
            "city_regency": o.city_regency,
            "district": o.district,
            "review_count": len(revs),
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
            "sentiment_distribution": sent,
            "top_praise_categories": [c for c, _ in praise],
            "top_complaint_categories": [c for c, _ in complaints],
            "repeat_issues": repeat_issues,
            "priority_reviews": sorted(priority, key=lambda x: x["date"] or "", reverse=True)[:2],
        })

    branches.sort(key=lambda x: x["avg_rating"], reverse=True)
    for i, b in enumerate(branches):
        b["rank"] = i + 1
    return {"branches": branches}


# ─── GEOGRAPHIC BREAKDOWN (§11.4) ──────────────────────────
def geographic_breakdown(tenant_id: str, business_id: str, f: dict) -> dict:
    start, end, _, _ = _resolve_period(f)
    rows = _base_reviews(tenant_id, business_id, f, period=(start, end))
    cities, districts = {}, {}
    for r, o in rows:
        key = o.city_regency or "unknown"
        cities.setdefault(key, {"reviews": [], "branches": set()})
        cities[key]["reviews"].append((r, o))
        cities[key]["branches"].add(o.id)
        dkey = o.district or "unknown"
        districts.setdefault(dkey, {"reviews": [], "branches": set()})
        districts[dkey]["reviews"].append((r, o))
        districts[dkey]["branches"].add(o.id)

    def _agg(entry):
        revs = entry["reviews"]
        ratings = [r.star_rating for r, _ in revs]
        sent = {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0}
        cat_pol = {}
        for r, _ in revs:
            if not r.has_text:
                continue
            a = _analysis(r)
            s = _sentiment(r, a)
            sent[s] = sent.get(s, 0) + 1
            for c in _categories_for(r, a):
                cat_pol.setdefault(c, {"pos": 0, "neg": 0})
                if s == "positive":
                    cat_pol[c]["pos"] += 1
                elif s in ("negative", "mixed"):
                    cat_pol[c]["neg"] += 1
        praise = sorted(cat_pol.items(), key=lambda x: x[1]["pos"], reverse=True)[:3]
        complaints = sorted(cat_pol.items(), key=lambda x: x[1]["neg"], reverse=True)[:3]
        return {
            "total_reviews": len(revs),
            "branch_count": len(entry["branches"]),
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
            "sentiment": sent,
            "top_praise": [c for c, _ in praise],
            "top_complaints": [c for c, _ in complaints],
        }

    city_list = [{"city_regency": k, **_agg(v)} for k, v in sorted(cities.items(), key=lambda x: len(x[1]["reviews"]), reverse=True)]
    district_list = [{"district": k, **_agg(v)} for k, v in sorted(districts.items(), key=lambda x: len(x[1]["reviews"]), reverse=True)]
    return {"cities": city_list, "districts": district_list}


# ─── PERIOD ANALYTICS (§11.5) ──────────────────────────────
def period_analytics(tenant_id: str, business_id: str, f: dict) -> dict:
    start, end, prev_start, prev_end = _resolve_period(f)
    rows = _base_reviews(tenant_id, business_id, f, period=(start, end))

    days = {}
    for r, o in rows:
        day = (r.create_time or _now()).date().isoformat()
        days.setdefault(day, {"total": 0, "ratings": [], "sentiment": {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0}})
        days[day]["total"] += 1
        days[day]["ratings"].append(r.star_rating)
        if r.has_text:
            a = _analysis(r)
            s = _sentiment(r, a)
            days[day]["sentiment"][s] = days[day]["sentiment"].get(s, 0) + 1

    trend = []
    for day in sorted(days.keys()):
        d = days[day]
        trend.append({
            "date": day,
            "review_count": d["total"],
            "avg_rating": round(sum(d["ratings"]) / len(d["ratings"]), 2),
            "sentiment": d["sentiment"],
        })

    # Category trend vs previous period
    cat_counts = {}
    cat_prev = {}
    for r, o in _base_reviews(tenant_id, business_id, f, period=(start, end)):
        if not r.has_text:
            continue
        for c in _categories_for(r, _analysis(r)):
            cat_counts[c] = cat_counts.get(c, 0) + 1
    for r, o in _base_reviews(tenant_id, business_id, f, period=(prev_start, prev_end)):
        if not r.has_text:
            continue
        for c in _categories_for(r, _analysis(r)):
            cat_prev[c] = cat_prev.get(c, 0) + 1

    rising = sorted(
        ((c, cat_counts.get(c, 0) - cat_prev.get(c, 0)) for c in set(cat_counts) | set(cat_prev)),
        key=lambda x: x[1], reverse=True,
    )
    rising_complaints = [c for c, d in rising if d > 0][:5]
    rising_praise = []
    for c, _ in rising:
        # praise = positive-heavy categories gaining volume
        pass
    branch_now = {b["branch_name"]: b["avg_rating"] for b in branch_breakdown(tenant_id, business_id, f)["branches"]}

    return {
        "trend": trend,
        "rising_categories": [c for c, _ in rising][:5],
        "rising_complaint_categories": rising_complaints,
        "branch_ratings": branch_now,
    }


# ─── REVIEW EXPLORER (§11.6) ───────────────────────────────
def review_explorer(tenant_id: str, business_id: str, f: dict, page: int = 1, per_page: int = 20) -> dict:
    start, end, _, _ = _resolve_period(f)
    rows = _base_reviews(tenant_id, business_id, f, period=(start, end))
    total = len(rows)
    start_i = (page - 1) * per_page
    slice_rows = rows[start_i:start_i + per_page]

    items = []
    for r, o in slice_rows:
        a = _analysis(r)
        items.append({
            "date": r.create_time.isoformat() if r.create_time else None,
            "branch": o.name,
            "city_regency": o.city_regency,
            "district": o.district,
            "rating": r.star_rating,
            "sentiment": _sentiment(r, a),
            "categories": _categories_for(r, a),
            "urgency": _urgency(r, a),
            "snippet": (r.comment or "")[:200],
            "owner_reply_status": "yes" if r.owner_reply_text else "no",
            "source": r.source,
            "reviewer": mask_reviewer(r.reviewer_display_name),
            "is_rating_only": not r.has_text,
        })

    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": (total + per_page - 1) // per_page}


# ─── PRIORITY INSIGHTS (§11.7) ─────────────────────────────
def priority_insights(tenant_id: str, business_id: str, f: dict) -> dict:
    start, end, _, _ = _resolve_period(f)
    rows = _base_reviews(tenant_id, business_id, f, period=(start, end))

    negative = [(r, o) for r, o in rows if r.has_text and _sentiment(r, _analysis(r)) in ("negative", "mixed")]
    critical = [(r, o) for r, o in rows if r.has_text and _urgency(r, _analysis(r)) == "critical"]
    newest_negative = sorted(negative, key=lambda x: x[0].create_time or datetime.min, reverse=True)[:5]

    # Repeat issues per branch
    repeat = {}
    for r, o in negative:
        for c in _categories_for(r, _analysis(r)):
            repeat.setdefault((o.name, c), {"branch": o.name, "category": c, "count": 0})
            repeat[(o.name, c)]["count"] += 1
    repeat_issues = sorted(repeat.values(), key=lambda x: x["count"], reverse=True)[:5]

    cat_now = {}
    cat_prev = {}
    for r, o in rows:
        if not r.has_text:
            continue
        for c in _categories_for(r, _analysis(r)):
            cat_now[c] = cat_now.get(c, 0) + 1
    return {
        "recent_negative": [
            {
                "branch": o.name,
                "rating": r.star_rating,
                "snippet": (r.comment or "")[:160],
                "date": r.create_time.isoformat() if r.create_time else None,
                "categories": _categories_for(r, _analysis(r)),
                "urgency": _urgency(r, _analysis(r)),
                "reviewer": mask_reviewer(r.reviewer_display_name),
            }
            for r, o in newest_negative
        ],
        "critical_reviews": len(critical),
        "repeat_issues": repeat_issues,
        "reputation_risk": "severe" if len(critical) > 0 else ("elevated" if len(negative) >= 5 else "contained"),
    }


# ─── EXPORT (§12) ──────────────────────────────────────────
def export_rows(tenant_id: str, business_id: str, f: dict) -> list:
    start, end, _, _ = _resolve_period(f)
    rows = _base_reviews(tenant_id, business_id, f, period=(start, end))
    out = []
    for r, o in rows:
        a = _analysis(r)
        out.append({
            "tanggal": r.create_time.isoformat() if r.create_time else "",
            "cabang": o.name,
            "kota_kabupaten": o.city_regency,
            "kecamatan": o.district,
            "rating": r.star_rating,
            "sentimen": _sentiment(r, a),
            "kategori": "; ".join(_categories_for(r, a)),
            "urgensi": _urgency(r, a),
            "review": r.comment or "",
            "owner_reply_status": "ada" if r.owner_reply_text else "tidak ada",
            "sumber": r.source,
            "reviewer": mask_reviewer(r.reviewer_display_name),
            "rating_only": "ya" if not r.has_text else "tidak",
        })
    return out
