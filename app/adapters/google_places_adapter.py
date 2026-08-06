"""Google Places API adapter — text search & place details.

Uses Google Places API (legacy text search for simplicity).
Endpoint: https://maps.googleapis.com/maps/api/place/textsearch/json
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google Places API adapter
# ---------------------------------------------------------------------------

class GooglePlacesAdapter:
    """Thin wrapper around Google Places API text search."""

    BASE_URL = "https://maps.googleapis.com/maps/api/place"

    def __init__(self, api_key: str, timeout: int = 8):
        self.api_key = api_key
        self.timeout = timeout

    # ------------------------------------------------------------------
    # text search
    # ------------------------------------------------------------------

    def search_places(
        self,
        query: str,
        region: str = "id",
        language: str = "id",
        max_results: int = 10,
    ) -> list[dict]:
        """Search Google Places by text query.

        Returns list of place dicts:
          - place_id, name, formatted_address, rating, user_ratings_total,
            types, geometry (lat/lng), photos
        """
        url = f"{self.BASE_URL}/textsearch/json"
        params = {
            "query": query,
            "region": region,
            "language": language,
            "key": self.api_key,
        }

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Google Places text search HTTP error: %s", exc)
            return []

        data = resp.json()

        status = data.get("status", "UNKNOWN_ERROR")
        if status not in ("OK", "ZERO_RESULTS"):
            error_msg = data.get("error_message", status)
            logger.error("Google Places API error: %s", error_msg)
            return []

        results = data.get("results", [])
        return [_normalize_place(p) for p in results[:max_results]]

    # ------------------------------------------------------------------
    # place details
    # ------------------------------------------------------------------

    def get_place_details(
        self,
        place_id: str,
        fields: Optional[list[str]] = None,
        language: str = "id",
    ) -> Optional[dict]:
        """Fetch details for a single place.

        Default fields: reviews, rating, user_ratings_total, name,
                        formatted_address, formatted_phone_number,
                        opening_hours, website, url, photos, geometry.
        """
        if fields is None:
            fields = [
                "name",
                "rating",
                "user_ratings_total",
                "formatted_address",
                "formatted_phone_number",
                "opening_hours",
                "website",
                "url",
                "photos",
                "geometry",
                "reviews",
            ]

        url = f"{self.BASE_URL}/details/json"
        params = {
            "place_id": place_id,
            "fields": ",".join(fields),
            "language": language,
            "key": self.api_key,
        }

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Google Place Details HTTP error: %s", exc)
            return None

        data = resp.json()

        if data.get("status") != "OK":
            logger.error("Google Place Details error: %s", data.get("status"))
            return None

        result = data.get("result", {})
        return _normalize_place_details(result)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _normalize_place(raw: dict) -> dict:
    """Normalize a text-search result dict to our internal shape."""
    geometry = raw.get("geometry", {}) or {}
    location = geometry.get("location", {}) or {}
    photos = raw.get("photos", []) or []

    return {
        "place_id": raw.get("place_id", ""),
        "name": raw.get("name", ""),
        "formatted_address": raw.get("formatted_address", ""),
        "rating": raw.get("rating"),
        "user_ratings_total": raw.get("user_ratings_total", 0),
        "types": raw.get("types", []),
        "latitude": location.get("lat"),
        "longitude": location.get("lng"),
        "photo_count": len(photos),
        "business_status": raw.get("business_status"),
    }


def _normalize_place_details(raw: dict) -> dict:
    """Normalize a place-details result dict."""
    geometry = raw.get("geometry", {}) or {}
    location = geometry.get("location", {}) or {}
    hours = raw.get("opening_hours", {}) or {}
    photos = raw.get("photos", []) or []
    reviews_raw = raw.get("reviews", []) or []

    reviews = []
    for r in reviews_raw:
        reviews.append({
            "author_name": r.get("author_name", ""),
            "rating": r.get("rating", 0),
            "text": r.get("text", ""),
            "relative_time_description": r.get("relative_time_description", ""),
            "time": r.get("time"),
        })

    return {
        "place_id": raw.get("place_id", ""),
        "name": raw.get("name", ""),
        "formatted_address": raw.get("formatted_address", ""),
        "formatted_phone": raw.get("formatted_phone_number"),
        "rating": raw.get("rating"),
        "user_ratings_total": raw.get("user_ratings_total", 0),
        "website": raw.get("website"),
        "google_maps_url": raw.get("url"),
        "latitude": location.get("lat"),
        "longitude": location.get("lng"),
        "types": raw.get("types", []),
        "photo_count": len(photos),
        "open_now": hours.get("open_now"),
        "opening_hours": hours.get("weekday_text", []),
        "reviews": reviews,
        "review_count": len(reviews),
    }
