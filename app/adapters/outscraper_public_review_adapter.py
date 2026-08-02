"""Outscraper public review adapter (RUN_10).

Fetches real public Google reviews through the Outscraper Google Maps API:
    GET https://api.app.outscraper.com/maps/reviews-v3

Features:
- Place ID or Google Maps URL input
- limit / sort order / pagination (offset) / timeout
- retry with exponential backoff, rate-limit handling
- vendor error normalization
- raw payload preservation
- source label ``outscraper``, collected_at, provenance
- deterministic fallback review ID when vendor ID is missing

Safety:
- API key read from env (never logged)
- No fabricated reviews on failure
- No silent fallback to mock (handled by public_provider)
"""
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from app.adapters.public_review_source_adapter import PublicReviewSourceAdapter
from app.services import public_provider

logger = logging.getLogger(__name__)

OUTSCRAPER_BASE_URL = "https://api.app.outscraper.com/maps/reviews-v3"

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _utc_now():
    return datetime.now(timezone.utc)


def _mask_name(name) -> str:
    """Mask a reviewer name — keep first word + initial of second word."""
    if not name or not str(name).strip():
        return "Anonim"
    parts = str(name).strip().split()
    if len(parts) == 1:
        return parts[0][:1] + "***"
    return parts[0] + " " + parts[1][:1] + "***"


def _iso_from_timestamp(ts):
    """Convert unix timestamp or ISO string to ISO-8601 string, or None."""
    if ts is None or ts == "":
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).isoformat()
    except (ValueError, TypeError):
        return str(ts)


def _parse_iso_aware(value):
    """Parse ISO string to tz-aware datetime, or None."""
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except (ValueError, TypeError):
        return None


def _deterministic_review_id(place_id: str, review: dict) -> str:
    """Deterministic content hash fallback for reviews without a vendor ID."""
    payload = "|".join(
        [
            str(place_id or ""),
            str(review.get("author_title") or ""),
            str(review.get("review_timestamp") or review.get("review_datetime_utc") or ""),
            str(review.get("review_rating") or ""),
            str(review.get("review_text") or ""),
        ]
    )
    return "hash_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


class OutscraperError(Exception):
    """Normalized Outscraper vendor error."""

    def __init__(self, message: str, status_code: int = None, retryable: bool = False, payload: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.payload = payload or {}

    def to_dict(self):
        return {
            "error": self.message,
            "provider": "outscraper",
            "status_code": self.status_code,
            "retryable": self.retryable,
        }


class OutscraperPublicReviewAdapter(PublicReviewSourceAdapter):
    """Production public review adapter backed by Outscraper."""

    source_name = "outscraper"

    def __init__(
        self,
        api_key: str = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        page_size: Optional[int] = None,
        max_reviews: Optional[int] = None,
        base_url: str = OUTSCRAPER_BASE_URL,
    ):
        self.api_key = api_key or public_provider.get_outscraper_api_key()
        self.timeout = timeout if timeout is not None else public_provider.get_public_review_timeout()
        self.max_retries = max_retries if max_retries is not None else public_provider.get_public_review_max_retries()
        self.page_size = page_size if page_size is not None else public_provider.get_public_review_page_size()
        self.max_reviews = max_reviews if max_reviews is not None else public_provider.get_public_review_max_reviews()
        self.base_url = base_url

    # ─── HTTP plumbing ─────────────────────────────────────
    def _request(self, params: dict) -> dict:
        """GET with retry + exponential backoff + rate-limit handling."""
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.get(
                    self.base_url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.exceptions.Timeout as exc:
                last_exc = OutscraperError("outscraper timeout", retryable=True)
                logger.warning("Outscraper timeout (attempt %s): %s", attempt + 1, exc)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise last_exc
            except requests.exceptions.RequestException as exc:
                last_exc = OutscraperError(f"outscraper request failed: {exc}", retryable=True)
                logger.warning("Outscraper request error (attempt %s): %s", attempt + 1, exc)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise last_exc

            if resp.status_code in RETRYABLE_STATUS:
                if attempt < self.max_retries:
                    logger.warning("Outscraper HTTP %s (attempt %s), backing off", resp.status_code, attempt + 1)
                    time.sleep(2 ** attempt)
                    continue
                raise OutscraperError(
                    f"outscraper HTTP {resp.status_code}", status_code=resp.status_code, retryable=True
                )
            if resp.status_code != 200:
                raise OutscraperError(
                    f"outscraper HTTP {resp.status_code}", status_code=resp.status_code, retryable=False
                )

            try:
                data = resp.json()
            except ValueError as exc:
                raise OutscraperError("outscraper returned non-JSON payload", status_code=200, retryable=False)

            # Outscraper sometimes returns {"error": "..."} with 200
            if isinstance(data, dict) and data.get("error"):
                raise OutscraperError(
                    f"outscraper error: {data['error']}", status_code=200, retryable=False, payload=data
                )
            return data

        raise last_exc or OutscraperError("outscraper request failed")

    def _first_place(self, data: dict) -> Optional[dict]:
        rows = data.get("data") or []
        if not rows:
            return None
        return rows[0] if isinstance(rows[0], dict) else None

    # ─── PublicReviewSourceAdapter ─────────────────────────
    def fetch_location(self, place_id: str) -> dict:
        data = self._request(
            {"query": place_id, "limit": 1, "reviewsType": "only_location", "language": "id"}
        )
        place = self._first_place(data)
        if place is None:
            raise OutscraperError(f"lokasi tidak ditemukan: {place_id}", status_code=404)

        # Outscraper returns the requested place id under several keys
        pid = (
            place.get("place_id")
            or place.get("placeId")
            or place.get("query")
            or place_id
        )
        lat = place.get("latitude")
        lon = place.get("longitude")
        try:
            lat = float(lat) if lat not in (None, "") else None
            lon = float(lon) if lon not in (None, "") else None
        except (TypeError, ValueError):
            lat = lon = None

        return {
            "place_id": pid,
            "business_name": place.get("name") or place.get("title") or "",
            "full_address": place.get("full_address") or place.get("address") or "",
            "latitude": lat,
            "longitude": lon,
            "maps_url": place.get("maps_url") or place.get("link") or None,
            "business_rating": _safe_float(place.get("rating")),
            "business_review_count": _safe_int(place.get("reviews") or place.get("reviews_count")),
            "province": place.get("state") or None,
            "city_regency": place.get("city") or None,
            "district": place.get("district") or place.get("suburb") or None,
            "source": self.source_name,
        }

    def list_reviews_by_place_id(
        self,
        place_id: str,
        since: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> list[dict]:
        """List one page of public reviews for a Google place.

        Single-page semantics: the caller drives pagination via ``offset``.
        ``limit`` caps the returned items; ``offset`` selects the page window.
        """
        collected_at = _utc_now().isoformat()
        sort = kwargs.get("sort") or "newest"
        offset = int(kwargs.get("offset") or 0)
        page_size = min(self.page_size, max(1, limit))
        max_reviews = self.max_reviews or 0
        since_dt = _parse_iso_aware(since)

        data = self._request(
            {
                "query": place_id,
                "limit": page_size,
                "offset": offset,
                "sort": sort,
                "reviewsType": "only_reviews",
                "language": "id",
            }
        )
        place = self._first_place(data)
        reviews = (place or {}).get("reviews_data") or []

        items = []
        for rv in reviews:
            review_date = _iso_from_timestamp(
                rv.get("review_datetime_utc") or rv.get("review_timestamp")
            )
            review_dt = _parse_iso_aware(review_date)
            if since_dt and review_dt and review_dt < since_dt:
                continue
            owner_date = _iso_from_timestamp(
                rv.get("owner_answer_datetime_utc") or rv.get("owner_answer_timestamp")
            )
            raw_rid = rv.get("review_id") or rv.get("id") or ""
            rid = raw_rid or _deterministic_review_id(place_id, rv)
            items.append(
                {
                    "source_review_id": rid,
                    "rating": _safe_int(rv.get("review_rating"), default=3),
                    "review_text": rv.get("review_text") or "",
                    "review_date": review_date,
                    "review_datetime_raw": str(
                        rv.get("review_datetime_utc")
                        or rv.get("review_timestamp")
                        or ""
                    ),
                    "owner_reply_text": rv.get("owner_answer"),
                    "owner_reply_date": owner_date,
                    "source": self.source_name,
                    "source_url": f"https://www.google.com/maps/contrib/{rid}" if rid else None,
                    "reviewer_name_masked": _mask_name(
                        rv.get("author_title") or rv.get("author_name")
                    ),
                    "raw_payload": {**rv, "_collected_at": collected_at, "_provider": self.source_name},
                }
            )
            if max_reviews and len(items) >= max_reviews:
                break

        return items[:limit] if limit > 0 else items


def _safe_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _safe_int(value, default=None):
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default
