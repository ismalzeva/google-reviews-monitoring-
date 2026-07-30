"""Reconciliation service — compare current source state with DB, detect changes."""

import logging
from datetime import datetime, timezone

from app import db
from app.models.entities import Outlet, Review, ReviewVersion, AuditLog, SyncReport
from app.services.review_source_adapter import get_adapter
from app.services.review_service import normalize_review, upsert_review

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def reconcile_reviews(
    tenant_id: str,
    business_id: str,
    outlet_ids: list = None,
    mark_unavailable: bool = True,
) -> dict:
    """Reconcile reviews for one or more outlets.

    Compares current DB state with source adapter (mock),
    updates changed reviews, marks deleted reviews as unavailable.
    """
    report = {
        "outlets_checked": 0,
        "reviews_in_db": 0,
        "reviews_verified": 0,
        "reviews_updated": 0,
        "reviews_marked_unavailable": 0,
        "errors": [],
        "started_at": _now().isoformat(),
        "completed_at": None,
    }

    adapter = get_adapter("mock")

    query = Outlet.query.filter(
        Outlet.tenant_id == tenant_id,
        Outlet.business_id == business_id,
        Outlet.monitor_enabled == True,
        Outlet.status != "old_or_closed",
    )
    if outlet_ids:
        query = query.filter(Outlet.id.in_(outlet_ids))

    outlets = query.all()

    for outlet in outlets:
        try:
            result = _reconcile_outlet(tenant_id, business_id, outlet, adapter, mark_unavailable)
            report["outlets_checked"] += 1
            report["reviews_in_db"] += result["in_db"]
            report["reviews_verified"] += result["verified"]
            report["reviews_updated"] += result["updated"]
            report["reviews_marked_unavailable"] += result["marked_unavailable"]
        except Exception as e:
            logger.exception("Reconciliation failed for outlet %s: %s", outlet.name, e)
            report["errors"].append({"outlet": outlet.name, "error": str(e)})

    report["completed_at"] = _now().isoformat()

    # Audit log
    audit = AuditLog(
        tenant_id=tenant_id,
        action="reconciliation.completed",
        entity_type="reconciliation",
        reason=str({
            "outlets_checked": report["outlets_checked"],
            "reviews_updated": report["reviews_updated"],
            "reviews_marked_unavailable": report["reviews_marked_unavailable"],
        }),
    )
    db.session.add(audit)
    db.session.commit()

    return report


def _reconcile_outlet(tenant_id, business_id, outlet, adapter, mark_unavailable):
    """Reconcile a single outlet."""
    result = {"in_db": 0, "verified": 0, "updated": 0, "marked_unavailable": 0}

    # Get all reviews in DB for this outlet
    db_reviews = Review.query.filter_by(
        tenant_id=tenant_id,
        business_id=business_id,
        outlet_id=outlet.id,
        source_visibility_status="available",
    ).all()

    result["in_db"] = len(db_reviews)

    # Build set of source_review_names known in DB
    db_review_names = {r.source_review_name for r in db_reviews}

    # Fetch all reviews from source (handle pagination)
    source_review_names = set()
    page_token = None
    while True:
        page = adapter.list_reviews(
            business_id=business_id,
            location_id=outlet.gbp_location_id,
            page_token=page_token,
            page_size=50,
        )
        for review in page.get("reviews", []):
            rn = review.get("review_name", "")
            source_review_names.add(rn)
            result["verified"] += 1

            # Check if this review exists in DB
            if rn in db_review_names:
                db_review = next((r for r in db_reviews if r.source_review_name == rn), None)
                if db_review:
                    # Compare and update if changed
                    new_rating = review.get("star_rating")
                    new_comment = review.get("comment")
                    has_changed = (
                        db_review.star_rating != new_rating
                        or db_review.comment != new_comment
                    )
                    if has_changed:
                        normalized = normalize_review(
                            tenant_id, business_id, outlet.id, 'mock', review
                        )
                        upsert_review(
                            tenant_id=tenant_id,
                            business_id=business_id,
                            outlet_id=outlet.id,
                            source="mock",
                            source_review_name=rn,
                            normalized=normalized,
                            raw_payload=review,
                        )
                        result["updated"] += 1

        page_token = page.get("next_page_token")
        if not page_token:
            break

    # Mark reviews not found in source as unavailable
    if mark_unavailable:
        for db_review in db_reviews:
            if db_review.source_review_name not in source_review_names:
                db_review.source_visibility_status = "unavailable"
                db_review.last_seen_at = _now()
                db.session.add(db_review)
                result["marked_unavailable"] += 1

        if result["marked_unavailable"] > 0:
            db.session.commit()

    return result
