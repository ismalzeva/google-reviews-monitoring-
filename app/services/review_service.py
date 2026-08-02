"""Review service — normalize, upsert, query, and lifecycle operations.

Provides the core CRUD layer for the ``Review`` entity and its associated
version-history (``ReviewVersion``) and raw-payload (``ReviewRawPayload``)
tables. Every public function enforces tenant isolation.
"""
import hashlib
import json
import logging
import re
from datetime import datetime, timezone

from app import db
from app.models.entities import Review, ReviewVersion, ReviewRawPayload

logger = logging.getLogger(__name__)


def _parse_iso_datetime(value):
    """Parse ISO-8601 string to timezone-aware datetime, or return as-is."""
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return value
    return value


# Regex to parse a Google Business Profile review resource name:
#   accounts/{accountId}/locations/{locationId}/reviews/{reviewId}
_REVIEW_NAME_RE = re.compile(
    r"^accounts/([^/]+)/locations/([^/]+)/reviews/([^/]+)$"
)


# ─── HELPERS ──────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_review_name(source_review_name: str) -> dict:
    """Extract *account_id*, *location_id*, and *review_id* from a GBP review name."""
    m = _REVIEW_NAME_RE.match(source_review_name)
    if m:
        return {
            "source_account_id": m.group(1),
            "source_location_id": m.group(2),
            "review_id": m.group(3),
        }
    # Fallback for non-GBP formats or malformed names
    return {
        "source_account_id": None,
        "source_location_id": None,
        "review_id": source_review_name,
    }


def _save_raw_payload(
    review: Review,
    tenant_id: str,
    business_id: str,
    source: str,
    source_review_name: str,
    raw_payload: dict,
) -> None:
    """Insert a ``ReviewRawPayload`` row inside a savepoint."""
    parsed = _parse_review_name(source_review_name)
    entry = ReviewRawPayload(
        tenant_id=tenant_id,
        business_id=business_id,
        review_pk=review.id,
        source=source,
        source_account_id=parsed["source_account_id"],
        source_location_id=parsed["source_location_id"],
        source_review_name=source_review_name,
        raw_payload_hash=review.raw_payload_hash,
        raw_payload=raw_payload,
    )
    db.session.add(entry)


# ─── NORMALIZE ────────────────────────────────────────────────


def normalize_review(
    tenant_id: str,
    business_id: str,
    outlet_id: str | None,
    source: str,
    raw_data: dict,
) -> dict:
    """Convert raw adapter data into the internal review dict ready for upsert.

    The returned dict mirrors the ``Review`` columns and is designed to be
    unpacked as keyword arguments to ``Review(**data)``.

    Validation performed:

    * ``star_rating`` — clamped to the 1‑5 integer range.
    * ``has_text`` — derived from whether *comment* has non‑whitespace content.
    * ``qualitative_analysis_status`` — set to ``'not_applicable'`` when
      *has_text* is ``False``; otherwise ``'pending'``.
    * ``raw_payload_hash`` — SHA‑256 hex digest of
      ``json.dumps(raw_data, sort_keys=True, default=str)``.
    * ``source_visibility_status`` — always ``'available'`` for a fresh
      normalisation.
    """
    star_rating = raw_data.get("star_rating")
    if star_rating is not None:
        star_rating = max(1, min(5, int(star_rating)))

    comment = raw_data.get("comment") or ""
    has_text = bool(comment.strip())

    # Accept common key variants for cross-adapter compatibility
    review_name = (
        raw_data.get("source_review_name")
        or raw_data.get("name")
        or raw_data.get("review_name")
        or ""
    )

    create_time = raw_data.get("create_time") or raw_data.get("createTime")
    update_time = raw_data.get("update_time") or raw_data.get("updateTime")

    # Normalize ISO-8601 strings to datetime objects
    create_time = _parse_iso_datetime(create_time)
    update_time = _parse_iso_datetime(update_time)

    payload_hash = hashlib.sha256(
        json.dumps(raw_data, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    return {
        "tenant_id": tenant_id,
        "business_id": business_id,
        "outlet_id": outlet_id,
        "source": source,
        "source_review_name": review_name,
        "review_id": _parse_review_name(review_name)["review_id"],
        "reviewer_display_name": raw_data.get("reviewer_display_name")
        or raw_data.get("reviewer", {}).get("displayName", ""),
        "reviewer_is_anonymous": raw_data.get("reviewer_is_anonymous", False),
        "star_rating": star_rating,
        "comment": comment,
        "has_text": has_text,
        "owner_reply_text": raw_data.get("owner_reply_text"),
        "owner_reply_date": _parse_iso_datetime(raw_data.get("owner_reply_date")),
        "source_url": raw_data.get("source_url"),
        "create_time": create_time,
        "update_time": update_time,
        "source_visibility_status": "available",
        "raw_payload_hash": payload_hash,
        "qualitative_analysis_status": (
            "not_applicable" if not has_text else "pending"
        ),
    }


# ─── UPSERT ───────────────────────────────────────────────────


def upsert_review(
    tenant_id: str,
    business_id: str,
    outlet_id: str | None,
    source: str,
    source_review_name: str,
    normalized: dict,
    raw_payload: dict,
) -> dict:
    """Idempotently create or update a review and its version history.

    Lookup is by the unique triple ``(tenant_id, source, source_review_name)``.

    * **Not found** → creates a new ``Review`` at version 1 with a
      ``ReviewVersion`` snapshot and stores the raw payload.
    * **Found + unchanged** → returns ``{'status': 'unchanged'}``.
    * **Found + changed** → archives the current state as a new
      ``ReviewVersion``, bumps ``current_version`` on the review, updates
      fields, and sets ``review_updated`` / ``analysis_reassessment_required``
      to ``True``.

    Parameters
    ----------
    normalized : dict
        The output of :func:`normalize_review`.
    raw_payload : dict
        The original payload from the adapter (stored verbatim).

    Returns
    -------
    dict
        ``{'status': 'created'|'updated'|'unchanged', 'review': Review, 'version': int}``

    Raises
    ------
    Exception
        On any database error — transaction is rolled back before re-raising.
    """
    try:
        existing = Review.query.filter_by(
            tenant_id=tenant_id,
            source=source,
            source_review_name=source_review_name,
        ).first()

        if existing is None:
            # ── Create new review ──────────────────────────────────
            review = Review(**normalized)
            review.current_version = 1
            db.session.add(review)
            db.session.flush()  # populate review.id

            # First version snapshot
            db.session.add(
                ReviewVersion(
                    review_pk=review.id,
                    version=1,
                    star_rating=normalized.get("star_rating"),
                    comment=normalized.get("comment"),
                    source_update_time=normalized.get("update_time"),
                    raw_payload_hash=normalized.get("raw_payload_hash"),
                )
            )

            with db.session.begin_nested():
                _save_raw_payload(
                    review,
                    tenant_id,
                    business_id,
                    source,
                    source_review_name,
                    raw_payload,
                )

            db.session.commit()
            return {"status": "created", "review": review, "version": 1}

        # ── Existing review — detect changes ──────────────────────
        old_rating = existing.star_rating
        old_comment = existing.comment
        old_update_time = existing.update_time

        new_rating = normalized.get("star_rating")
        new_comment = normalized.get("comment")
        new_update_time = normalized.get("update_time")

        # SQLite may return naive datetime even with timezone=True
        # Safely normalise both to UTC-aware for comparison
        def _utc_aware(dt):
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        old_ut = _utc_aware(old_update_time)
        new_ut = _utc_aware(new_update_time)

        rating_changed = old_rating != new_rating
        comment_changed = old_comment != new_comment
        time_changed = new_ut is not None and (
            old_ut is None or new_ut > old_ut
        )

        if not (rating_changed or comment_changed or time_changed):
            # No meaningful change — skip
            return {
                "status": "unchanged",
                "review": existing,
                "version": existing.current_version,
            }

        # ── Changes detected — bump version ───────────────────────
        old_version = existing.current_version
        new_version = old_version + 1

        # Archive current state
        db.session.add(
            ReviewVersion(
                review_pk=existing.id,
                version=old_version,
                star_rating=old_rating,
                comment=old_comment,
                source_update_time=old_update_time,
                raw_payload_hash=existing.raw_payload_hash,
            )
        )

        # Apply new values
        existing.current_version = new_version
        existing.star_rating = new_rating
        existing.comment = new_comment
        existing.has_text = normalized.get(
            "has_text", bool((new_comment or "").strip())
        )
        existing.create_time = normalized.get("create_time", existing.create_time)
        existing.update_time = new_update_time or existing.update_time
        existing.raw_payload_hash = normalized.get("raw_payload_hash")
        existing.review_updated = True
        existing.analysis_reassessment_required = True
        existing.qualitative_analysis_status = normalized.get(
            "qualitative_analysis_status"
        ) or (
            "not_applicable" if not (new_comment or "").strip()
            else existing.qualitative_analysis_status
        )

        with db.session.begin_nested():
            _save_raw_payload(
                existing,
                tenant_id,
                business_id,
                source,
                source_review_name,
                raw_payload,
            )

        db.session.commit()
        return {"status": "updated", "review": existing, "version": new_version}

    except Exception:
        db.session.rollback()
        logger.exception(
            "Failed to upsert review (tenant=%s, source=%s, name=%s)",
            tenant_id,
            source,
            source_review_name,
        )
        raise


# ─── QUERY ────────────────────────────────────────────────────


def get_reviews_for_outlet(
    outlet_id: str,
    tenant_id: str,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Return paginated reviews for an outlet, newest ``update_time`` first.

    Returns
    -------
    dict
        ``{'items': [Review, ...], 'total': int, 'page': int,
        'per_page': int, 'pages': int}``
    """
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20

    base_q = Review.query.filter_by(
        outlet_id=outlet_id,
        tenant_id=tenant_id,
    ).order_by(Review.update_time.desc().nullslast())

    total = base_q.count()
    pages = max(1, (total + per_page - 1) // per_page)

    items = base_q.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


def get_review_by_source(
    tenant_id: str,
    source: str,
    source_review_name: str,
) -> Review | None:
    """Look up a review by its tenant, source, and source review name."""
    return Review.query.filter_by(
        tenant_id=tenant_id,
        source=source,
        source_review_name=source_review_name,
    ).first()


def mark_review_unavailable(
    review_id: str,
    tenant_id: str,
    business_id: str,
) -> dict:
    """Mark a review as unavailable in the source system.

    Sets ``source_visibility_status`` to ``'unavailable'`` and records
    ``last_seen_at`` to the current UTC timestamp.

    Returns
    -------
    dict
        ``{'status': 'unavailable', 'review': Review}``

    Raises
    ------
    ValueError
        If the review is not found for the given tenant + business pair.
    """
    try:
        review = Review.query.filter_by(
            id=review_id,
            tenant_id=tenant_id,
            business_id=business_id,
        ).first()

        if review is None:
            raise ValueError(
                f"Review {review_id} not found for tenant {tenant_id}"
            )

        review.source_visibility_status = "unavailable"
        review.last_seen_at = _now()
        db.session.commit()

        return {"status": "unavailable", "review": review}

    except Exception:
        db.session.rollback()
        logger.exception(
            "Failed to mark review unavailable (review=%s, tenant=%s)",
            review_id,
            tenant_id,
        )
        raise
