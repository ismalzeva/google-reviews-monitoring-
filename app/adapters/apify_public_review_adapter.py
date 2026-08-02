"""Apify public review adapter (RUN_11 — Apify provider).

Source of truth: skill `grm-apify-public-review-provider`.

Actors (schema verified from Apify Store 2026-08-02):
- Review:    compass/google-maps-reviews-scraper
             Input: startUrls[{url}], placeIds[], maxReviews, reviewsSort,
                    reviewsStartDate, reviewsFilterString
             Output: text, textTranslated, publishAt, publishedAtDate (ISO),
                     likesCount, reviewId, reviewUrl, stars (1-5),
                     responseFromOwnerDate, responseFromOwnerText,
                     reviewImageUrls, reviewOrigin, name, reviewerId,
                     reviewerUrl, reviewerNumberOfReviews, reviewerPhotoUrl,
                     isLocalGuide, title, placeId, address, location,
                     categories, totalScore, permanentlyClosed,
                     temporarilyClosed, reviewsCount
- Discovery: compass/crawler-google-places
             Input: searchStringsArray, maxCrawledPlacesPerSearch

Flow: POST /v2/acts/{actorId}/runs → poll run status → defaultDatasetId →
      GET dataset items (offset/limit). Only SUCCEEDED continues.

Safety:
- token only via env; never logged; never in errors (redacted)
- no silent fallback to mock
- placeholder Place IDs rejected
- reviewer names masked; no profile photos stored
- retry only 429/transient 5xx; never 401/403
"""
import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from app.adapters.public_review_source_adapter import PublicReviewSourceAdapter
from app.services import public_provider

logger = logging.getLogger(__name__)

APIFY_API_BASE = "https://api.apify.com/v2"

RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Mock-dataset place IDs use slug patterns like ChIJ0-depok-margonda-001.
# Real Google place IDs are base64-ish without slug dashes.
_PLACEHOLDER_PLACE_ID_RE = re.compile(r"^ChIJ0-[a-z]+(-[a-z]+)+-\d{3}$")


def _utc_now():
    return datetime.now(timezone.utc)


def _encode_actor_id(actor_id: str) -> str:
    """Encode canonical actor id (slash) to API path form (tilde)."""
    return actor_id.strip().replace("/", "~")


def _mask_name(name) -> str:
    if not name or not str(name).strip():
        return "Anonim"
    parts = str(name).strip().split()
    if len(parts) == 1:
        return parts[0][:1] + "***"
    return parts[0] + " " + parts[1][:1] + "***"


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


def _deterministic_review_id(place_id: str, item: dict) -> str:
    payload = "|".join(
        [
            str(place_id or ""),
            str(item.get("reviewerId") or ""),
            str(item.get("publishedAtDate") or item.get("publishAt") or ""),
            str(item.get("stars") or ""),
            str(item.get("text") or ""),
        ]
    )
    return "hash_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _is_placeholder_place_id(place_id: str) -> bool:
    return bool(place_id and _PLACEHOLDER_PLACE_ID_RE.match(place_id))


class ApifyError(Exception):
    """Normalized Apify vendor error."""

    def __init__(self, message: str, status_code: int = None, retryable: bool = False,
                 code: str = None, payload: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.code = code or ("APIFY_ERROR" if status_code else "APIFY_ERROR")
        self.payload = payload or {}

    def to_dict(self):
        return {
            "error": self.message,
            "provider": "apify",
            "status_code": self.status_code,
            "retryable": self.retryable,
            "code": self.code,
        }


class ApifyPublicReviewAdapter(PublicReviewSourceAdapter):
    """Production public review adapter backed by Apify actors."""

    source_name = "apify"

    def __init__(
        self,
        token: str = None,
        review_actor_id: str = None,
        discovery_actor_id: str = None,
        timeout_seconds: Optional[int] = None,
        poll_interval_seconds: Optional[int] = None,
        max_reviews: Optional[int] = None,
        max_places: Optional[int] = None,
        base_url: str = APIFY_API_BASE,
    ):
        self.token = token or public_provider.get_apify_token()
        self.review_actor_id = review_actor_id or public_provider.get_apify_review_actor_id()
        self.discovery_actor_id = discovery_actor_id or public_provider.get_apify_discovery_actor_id()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else public_provider.get_apify_timeout_seconds()
        self.poll_interval = poll_interval_seconds if poll_interval_seconds is not None else public_provider.get_apify_poll_interval_seconds()
        self.max_reviews = max_reviews if max_reviews is not None else public_provider.get_apify_max_reviews()
        self.max_places = max_places if max_places is not None else public_provider.get_apify_max_places()
        self.base_url = base_url
        # Cache: (place_id, since) -> normalized items (one actor run per sync)
        self._run_cache = {}

    # ─── HTTP plumbing ─────────────────────────────────────
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, params: dict = None, json_body: dict = None):
        """HTTP call with retry for 429/transient 5xx; never retry 401/403."""
        url = f"{self.base_url}{path}"
        last_exc = None
        for attempt in range(3):  # bounded retries (configurable via env default 3)
            try:
                resp = requests.request(
                    method, url, params=params, headers=self._headers(),
                    json=json_body, timeout=self.timeout_seconds,
                )
            except requests.exceptions.Timeout as exc:
                last_exc = ApifyError("apify timeout", retryable=True, code="TIMEOUT")
                logger.warning("Apify timeout (attempt %s): %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise last_exc
            except requests.exceptions.RequestException as exc:
                last_exc = ApifyError(f"apify request failed: {exc}", retryable=True)
                logger.warning("Apify request error (attempt %s): %s", attempt + 1, exc)
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise last_exc

            if resp.status_code in (401, 403):
                raise ApifyError(
                    f"apify auth failed (HTTP {resp.status_code})",
                    status_code=resp.status_code, retryable=False, code="AUTH_FAILED",
                )
            if resp.status_code == 404:
                raise ApifyError(
                    "apify resource not found", status_code=404, retryable=False, code="NOT_FOUND"
                )
            if resp.status_code in RETRYABLE_STATUS:
                if attempt < 2:
                    logger.warning("Apify HTTP %s (attempt %s), backing off", resp.status_code, attempt + 1)
                    time.sleep(2 ** attempt)
                    continue
                raise ApifyError(
                    f"apify HTTP {resp.status_code}", status_code=resp.status_code,
                    retryable=True, code="RATE_LIMITED" if resp.status_code == 429 else "SERVER_ERROR",
                )
            if resp.status_code != 200 and resp.status_code != 201:
                raise ApifyError(
                    f"apify HTTP {resp.status_code}", status_code=resp.status_code,
                    retryable=False, code="HTTP_ERROR",
                )
            try:
                return resp.json()
            except ValueError as exc:
                raise ApifyError("apify returned non-JSON payload", status_code=200,
                                 retryable=False, code="MALFORMED")

        raise last_exc or ApifyError("apify request failed")

    # ─── Actor run helpers ─────────────────────────────────
    def _run_actor(self, actor_id: str, input_body: dict) -> dict:
        """Start an async actor run, poll to completion, return run info."""
        encoded = _encode_actor_id(actor_id)
        run = self._request("POST", f"/acts/{encoded}/runs", json_body=input_body)
        run_id = run.get("data", {}).get("id")
        if not run_id:
            raise ApifyError("apify run did not return an id", code="RUN_NO_ID")

        deadline = time.monotonic() + self.timeout_seconds
        while True:
            if time.monotonic() > deadline:
                raise ApifyError("apify run timed out", retryable=True, code="TIMED_OUT")
            status_data = self._request("GET", f"/actor-runs/{run_id}")
            status = status_data.get("data", {}).get("status")
            if status == "SUCCEEDED":
                return status_data.get("data", {})
            if status in ("FAILED", "TIMED-OUT", "ABORTED"):
                raise ApifyError(
                    f"apify run {status}", code=status,
                    payload={"runId": run_id, "status": status},
                )
            time.sleep(self.poll_interval)

    def _get_dataset_items(self, dataset_id: str, offset: int = 0, limit: int = 1000) -> list:
        data = self._request(
            "GET", f"/datasets/{dataset_id}/items",
            params={"offset": offset, "limit": limit, "clean": "false"},
        )
        if data is None:
            return []
        if isinstance(data, dict) and data.get("error"):
            raise ApifyError(f"apify dataset error: {data['error']}", code="DATASET_ERROR")
        if not isinstance(data, list):
            raise ApifyError("apify dataset items malformed", code="DATASET_MALFORMED")
        return data

    # ─── Normalization (verified actor output schema) ──────
    def _normalize_item(self, place_id: str, item: dict, run_id: str, dataset_id: str,
                        collected_at: str) -> dict:
        stars = _safe_int(item.get("stars"))
        text = item.get("text") or item.get("textTranslated") or ""
        loc = item.get("location") or {}
        lat = _safe_float(loc.get("lat")) if isinstance(loc, dict) else _safe_float(loc)
        lng = _safe_float(loc.get("lng")) if isinstance(loc, dict) else None

        rid = (
            item.get("reviewId")
            or item.get("reviewUrl")
            or _deterministic_review_id(place_id, item)
        )
        return {
            "source_review_id": rid,
            "rating": stars if stars else 3,
            "review_text": text,
            "review_date": item.get("publishedAtDate"),
            "review_datetime_raw": item.get("publishAt") or "",
            "owner_reply_text": item.get("responseFromOwnerText"),
            "owner_reply_date": item.get("responseFromOwnerDate"),
            "source": self.source_name,
            "source_url": item.get("reviewUrl"),
            "reviewer_name_masked": _mask_name(item.get("name")),
            "raw_payload": {
                **item,
                "_collected_at": collected_at,
                "_provider": self.source_name,
                "_run_id": run_id,
                "_dataset_id": dataset_id,
            },
            "place_id": item.get("placeId") or place_id,
            "business_name": item.get("title") or "",
            "full_address": item.get("address") or "",
            "latitude": lat,
            "longitude": lng,
            "province": None,
            "city_regency": None,
            "district": None,
            "business_rating": _safe_float(item.get("totalScore")),
            "business_review_count": _safe_int(item.get("reviewsCount")),
            "maps_url": (
                f"https://www.google.com/maps/place/?q=place_id:{(item.get('placeId') or place_id)}"
            ),
        }

    def _reviews_for_place(self, place_id: str, since: Optional[str] = None) -> list:
        """Run the review actor once per (place_id, since); cache per instance."""
        _is_placeholder_place_id(place_id) and self._reject_placeholder(place_id)
        cache_key = (place_id, since)
        if cache_key in self._run_cache:
            return self._run_cache[cache_key]

        input_body = {
            "placeIds": [place_id],
            "maxReviews": self.max_reviews,
            "reviewsSort": "newest",
        }
        if since:
            input_body["reviewsStartDate"] = since  # requires reviewsSort=newest
        run = self._run_actor(self.review_actor_id, input_body)
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            raise ApifyError("apify run missing defaultDatasetId", code="NO_DATASET")

        collected_at = _utc_now().isoformat()
        items = []
        offset = 0
        seen = set()
        while True:
            page = self._get_dataset_items(dataset_id, offset=offset, limit=1000)
            if not page:
                break
            dict_items = [i for i in page if isinstance(i, dict)]
            page_ids = {i.get("reviewId") for i in dict_items if i.get("reviewId")}
            if page_ids and page_ids.issubset(seen):
                break  # no-progress guard
            seen.update(page_ids)
            for item in dict_items:
                items.append(
                    self._normalize_item(place_id, item, run.get("id"), dataset_id, collected_at)
                )
            if len(page) < 1000:
                break
            offset += len(page)

        items.sort(key=lambda x: x["review_date"] or "", reverse=True)
        self._run_cache[cache_key] = items
        return items

    def _reject_placeholder(self, place_id: str):
        raise ApifyError(
            f"placeholder place id tidak diizinkan untuk live: {place_id!r}. "
            "Gunakan Place ID asli hasil discovery nyata.",
            code="PLACEHOLDER_REJECTED",
        )

    # ─── PublicReviewSourceAdapter interface ───────────────
    def fetch_location(self, place_id: str) -> dict:
        """Fetch public location details via the review actor (maxReviews=1)."""
        _is_placeholder_place_id(place_id) and self._reject_placeholder(place_id)
        input_body = {"placeIds": [place_id], "maxReviews": 1, "reviewsSort": "newest"}
        run = self._run_actor(self.review_actor_id, input_body)
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            raise ApifyError("apify run missing defaultDatasetId", code="NO_DATASET")
        page = self._get_dataset_items(dataset_id, offset=0, limit=1)
        if not page or not isinstance(page[0], dict):
            raise ApifyError(f"lokasi tidak ditemukan: {place_id}", code="LOCATION_NOT_FOUND")
        item = page[0]
        loc = item.get("location") or {}
        lat = _safe_float(loc.get("lat")) if isinstance(loc, dict) else None
        lng = _safe_float(loc.get("lng")) if isinstance(loc, dict) else None
        return {
            "place_id": item.get("placeId") or place_id,
            "business_name": item.get("title") or "",
            "full_address": item.get("address") or "",
            "latitude": lat,
            "longitude": lng,
            "maps_url": f"https://www.google.com/maps/place/?q=place_id:{(item.get('placeId') or place_id)}",
            "business_rating": _safe_float(item.get("totalScore")),
            "business_review_count": _safe_int(item.get("reviewsCount")),
            "province": None,
            "city_regency": None,
            "district": None,
            "source": self.source_name,
        }

    def list_reviews_by_place_id(
        self,
        place_id: str,
        since: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> list[dict]:
        """List public reviews for a place (one actor run per place/since)."""
        items = self._reviews_for_place(place_id, since=since)
        offset = int(kwargs.get("offset") or 0)
        window = items[offset:offset + limit] if limit > 0 else items[offset:]
        return window

    # ─── Discovery (actor compass/crawler-google-places) ───
    def discover(self, business_name: str, city: str = None, max_places: int = None) -> list[dict]:
        """Search public locations via the discovery actor."""
        search_term = f"{business_name} {city}".strip() if city else business_name
        max_places = max_places or self.max_places
        input_body = {
            "searchStringsArray": [search_term],
            "maxCrawledPlacesPerSearch": max_places,
        }
        run = self._run_actor(self.discovery_actor_id, input_body)
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            raise ApifyError("apify discovery missing dataset", code="NO_DATASET")
        page = self._get_dataset_items(dataset_id, offset=0, limit=max_places)
        results = []
        for item in page:
            if not isinstance(item, dict):
                continue
            loc = item.get("location") or {}
            results.append({
                "place_id": item.get("placeId") or item.get("id"),
                "display_name": item.get("title") or item.get("name") or "",
                "formatted_address": item.get("address") or "",
                "latitude": _safe_float(loc.get("lat")) if isinstance(loc, dict) else None,
                "longitude": _safe_float(loc.get("lng")) if isinstance(loc, dict) else None,
                "business_status": "OPERATIONAL",
                "google_maps_uri": (
                    f"https://www.google.com/maps/place/?q=place_id:{(item.get('placeId') or item.get('id'))}"
                ),
                "rating": _safe_float(item.get("totalScore")),
                "review_count": _safe_int(item.get("reviewsCount")),
                "source": self.source_name,
            })
        return results

    # ─── Health ────────────────────────────────────────────
    def health_check(self) -> dict:
        return {
            "provider": self.source_name,
            "configured": True,
            "token_present": bool(self.token),
            "review_actor_id": self.review_actor_id,
            "discovery_actor_id": self.discovery_actor_id,
            "live_request_allowed": bool(self.token),
        }
