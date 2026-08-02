"""Public review provider configuration (RUN_10).

Runtime env:
- PUBLIC_REVIEW_PROVIDER  : mock | outscraper   (default: mock)
- OUTSCRAPER_API_KEY      : required for outscraper mode
- PUBLIC_REVIEW_TIMEOUT   : request timeout seconds (default 30)
- PUBLIC_REVIEW_MAX_RETRIES : retry count (default 3)
- PUBLIC_REVIEW_PAGE_SIZE : reviews per provider page (default 100)
- PUBLIC_REVIEW_MAX_REVIEWS : cap per sync (default 0 = unlimited)

Rules (GRM_PUBLIC_MONITORING_SKILL §5, §13):
- Production mode must NOT silently fall back to mock.
- Missing API key fails safely with a clear error.
- API keys are never logged.
"""
import logging
import os

logger = logging.getLogger(__name__)

PROVIDERS = ("mock", "outscraper", "apify")


def get_public_review_provider() -> str:
    """Return the configured public review provider label."""
    provider = os.environ.get("PUBLIC_REVIEW_PROVIDER", "mock").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(
            f"PUBLIC_REVIEW_PROVIDER={provider!r} tidak dikenal. "
            f"Gunakan salah satu: {', '.join(PROVIDERS)}"
        )
    return provider


def get_outscraper_api_key() -> str:
    """Return the Outscraper API key, or raise when missing."""
    key = os.environ.get("OUTSCRAPER_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "OUTSCRAPER_API_KEY belum diset. "
            "Set env OUTSCRAPER_API_KEY untuk mode outscraper. "
            "Tidak ada fallback diam-diam ke mock."
        )
    return key


def get_apify_token() -> str:
    """Return the Apify API token, or raise when missing."""
    token = os.environ.get("APIFY_API_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "APIFY_API_TOKEN belum diset. "
            "Set env APIFY_API_TOKEN untuk mode apify. "
            "Tidak ada fallback diam-diam ke mock."
        )
    return token


def get_apify_review_actor_id() -> str:
    return os.environ.get(
        "APIFY_REVIEW_ACTOR_ID", "compass/google-maps-reviews-scraper"
    ).strip()


def get_apify_discovery_actor_id() -> str:
    return os.environ.get(
        "APIFY_DISCOVERY_ACTOR_ID", "compass/crawler-google-places"
    ).strip()


def get_apify_timeout_seconds() -> int:
    try:
        return max(1, int(os.environ.get("APIFY_TIMEOUT_SECONDS", "180")))
    except (TypeError, ValueError):
        return 180


def get_apify_poll_interval_seconds() -> int:
    try:
        return max(1, int(os.environ.get("APIFY_POLL_INTERVAL_SECONDS", "3")))
    except (TypeError, ValueError):
        return 3


def get_apify_max_reviews() -> int:
    try:
        return max(1, min(1000, int(os.environ.get("APIFY_MAX_REVIEWS", "100"))))
    except (TypeError, ValueError):
        return 100


def get_apify_max_places() -> int:
    try:
        return max(1, min(100, int(os.environ.get("APIFY_MAX_PLACES", "10"))))
    except (TypeError, ValueError):
        return 10


def get_public_review_timeout() -> int:
    try:
        return max(1, int(os.environ.get("PUBLIC_REVIEW_TIMEOUT", "30")))
    except (TypeError, ValueError):
        return 30


def get_public_review_max_retries() -> int:
    try:
        return max(0, int(os.environ.get("PUBLIC_REVIEW_MAX_RETRIES", "3")))
    except (TypeError, ValueError):
        return 3


def get_public_review_page_size() -> int:
    try:
        return max(1, min(200, int(os.environ.get("PUBLIC_REVIEW_PAGE_SIZE", "100"))))
    except (TypeError, ValueError):
        return 100


def get_public_review_max_reviews() -> int:
    """0 = unlimited."""
    try:
        return max(0, int(os.environ.get("PUBLIC_REVIEW_MAX_REVIEWS", "0")))
    except (TypeError, ValueError):
        return 0


def build_public_review_adapter(source: str = None):
    """Build the public review adapter for the configured provider.

    ``source`` overrides the provider label (used by tests / explicit API calls).
    Raises ValueError on unknown provider or missing credentials — never
    silently falls back to mock.
    """
    provider = (source or get_public_review_provider()).strip().lower()

    if provider == "mock":
        from app.adapters.mock_public_review_adapter import MockPublicReviewAdapter
        return MockPublicReviewAdapter()

    if provider == "outscraper":
        from app.adapters.outscraper_public_review_adapter import OutscraperPublicReviewAdapter
        api_key = get_outscraper_api_key()
        return OutscraperPublicReviewAdapter(api_key=api_key)

    if provider == "apify":
        from app.adapters.apify_public_review_adapter import ApifyPublicReviewAdapter
        return ApifyPublicReviewAdapter(
            token=get_apify_token(),
            review_actor_id=get_apify_review_actor_id(),
            discovery_actor_id=get_apify_discovery_actor_id(),
            timeout_seconds=get_apify_timeout_seconds(),
            poll_interval_seconds=get_apify_poll_interval_seconds(),
            max_reviews=get_apify_max_reviews(),
            max_places=get_apify_max_places(),
        )

    raise ValueError(
        f"Public review provider {provider!r} tidak didukung. "
        f"Gunakan: {', '.join(PROVIDERS)}"
    )
