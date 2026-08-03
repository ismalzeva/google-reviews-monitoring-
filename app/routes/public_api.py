"""Public API — GRM-005.

GET /api/public/preview?place_id=xxx — JSON preview analytics (no auth).
Rate limit: 20 req/menit per IP.
Cache: 24 jam (shared dengan app.services.preview).
Fallback: 202 jika data belum tersedia.
Analytics: track preview_started events.
"""

import collections
import logging
import time

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import TooManyRequests

from app.services.preview import get_all_branches, get_preview_data

logger = logging.getLogger(__name__)

bp = Blueprint("public_api", __name__, url_prefix="/api/public")

# ---------------------------------------------------------------------------
# Rate limiter: 20 req/menit per IP
# ---------------------------------------------------------------------------
_rate_window = 60  # 1 menit
_rate_limit = 20
_rate_buckets: dict[str, collections.deque] = {}


def _check_rate(ip: str) -> bool:
    now = time.monotonic()
    bucket = _rate_buckets.get(ip)
    if bucket is None:
        _rate_buckets[ip] = collections.deque([now])
        return True

    while bucket and bucket[0] < now - _rate_window:
        bucket.popleft()

    if len(bucket) < _rate_limit:
        bucket.append(now)
        return True
    return False


# ---------------------------------------------------------------------------
# Analytics tracker
# ---------------------------------------------------------------------------
_preview_events: list[dict] = []


def _track_event(event_type: str, place_id: str, ip: str) -> None:
    _preview_events.append(
        {
            "event": event_type,
            "place_id": place_id,
            "ip": ip,
            "timestamp": time.time(),
        }
    )
    logger.info("analytics|%s|%s|%s", event_type, place_id, ip)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@bp.route("/preview")
def preview_api():
    place_id = request.args.get("place_id", "").strip()
    ip = request.remote_addr or "unknown"

    if not _check_rate(ip):
        raise TooManyRequests("Terlalu banyak permintaan. Coba lagi nanti.")

    if not place_id:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Parameter place_id wajib diisi.",
                    "data": None,
                }
            ),
            400,
        )

    data = get_preview_data(place_id)  # MockPreview or None

    if data is None:
        _track_event("preview_not_found", place_id, ip)
        return (
            jsonify(
                {
                    "status": "fetching",
                    "message": "Data belum tersedia. Sedang mengumpulkan data...",
                    "data": None,
                    "retry_after_seconds": 300,
                }
            ),
            202,
        )

    _track_event("preview_started", place_id, ip)

    # Hitung sentimen
    total = data.review_count or 1
    positive = data.distribution.get(5, 0) + data.distribution.get(4, 0)
    neutral = data.distribution.get(3, 0)
    negative = data.distribution.get(2, 0) + data.distribution.get(1, 0)
    pos_ratio = positive / total

    result = {
        "rating": data.rating,
        "total_review": data.review_count,
        "distribution": data.distribution,
        "top_issues": data.top_issues,
        "sentiment_summary": {
            "positive_pct": round(positive / total * 100, 1),
            "neutral_pct": round(neutral / total * 100, 1),
            "negative_pct": round(negative / total * 100, 1),
            "label": "puas" if pos_ratio >= 0.85 else ("cukup puas" if pos_ratio >= 0.70 else "perlu perbaikan"),
        },
        "display_name": data.display_name,
        "formatted_address": data.formatted_address,
        "branch_selector": _branch_list(place_id),
    }

    return jsonify({"status": "success", "data": result})


def _branch_list(place_id: str) -> list[dict]:
    """Return branch selector untuk multi-cabang, current di depan."""
    branches = get_all_branches()
    current = None
    others = []
    for b in branches:
        entry = {"place_id": b.place_id, "name": b.display_name, "rating": b.rating}
        if b.place_id == place_id:
            current = entry
        else:
            others.append(entry)
    if current:
        return [current] + others[:5]
    return [{"place_id": b.place_id, "name": b.display_name, "rating": b.rating} for b in branches[:3]]
