"""Public review source adapter interface.

Any vendor that supplies *public* Google review data (scraping, outscraper,
apify, mscrape, playwright/selenium) must implement :class:`PublicReviewSourceAdapter`.
Business services must never depend on a concrete vendor class.

Contract (GRM_PUBLIC_MONITORING_SKILL §5, §13):
- Adapters return the same normalized schema.
- Every record carries provenance (``source``, ``source_url``).
- A vendor failure must NOT yield fabricated reviews.
- Never silently fall back from production to mock.
"""
from abc import ABC, abstractmethod
from typing import Optional


class PublicReviewSourceAdapter(ABC):
    """Common interface for public Google review collection."""

    #: Stable source label (e.g. ``public_scraping``, ``outscraper``, ``mock``)
    source_name: str = "public"

    @abstractmethod
    def fetch_location(self, place_id: str) -> dict:
        """Fetch public location details for a Google place.

        Returns a normalized dict:
            {
                "place_id": str,
                "business_name": str,
                "full_address": str,
                "latitude": float | None,
                "longitude": float | None,
                "maps_url": str | None,
                "business_rating": float | None,
                "business_review_count": int | None,
                "source": str,
            }
        Raises on vendor failure — must NOT return fabricated data.
        """

    @abstractmethod
    def list_reviews_by_place_id(
        self,
        place_id: str,
        since: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> list[dict]:
        """List public reviews for a Google place.

        ``since`` is an optional ISO-8601 date to only fetch newer reviews.
        Each item is a normalized dict:
            {
                "source_review_id": str,
                "rating": int,
                "review_text": str,          # "" for rating-only
                "review_date": str,          # ISO-8601
                "review_datetime_raw": str,  # raw value as collected
                "owner_reply_text": str | None,
                "owner_reply_date": str | None,
                "source": str,
                "source_url": str | None,
                "reviewer_name_masked": str | None,
                "raw_payload": dict,
            }
        """
