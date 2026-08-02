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

PROVIDERS = ("mock", "outscraper")


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

    raise ValueError(
        f"Public review provider {provider!r} tidak didukung. "
        f"Gunakan: {', '.join(PROVIDERS)}"
    )
