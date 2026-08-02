"""Sync service — historical review synchronization with progress tracking."""

import hashlib
import json
import logging
from datetime import datetime, timezone

from app import db
from app.models.entities import (
    Business, Outlet, Review, GoogleConnection, SyncReport, AuditLog
)
from app.services.review_service import normalize_review, upsert_review
from app.services.review_source_adapter import get_adapter

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def sync_reviews(
    tenant_id: str,
    business_id: str,
    source: str = "mock",
    outlet_ids: list = None,
    upsert_callback=None,
) -> dict:
    """Historical sync for one or more outlets. Returns sync report."""
    if upsert_callback is None:
        upsert_callback = upsert_review

    report = SyncReport(
        tenant_id=tenant_id,
        business_id=business_id,
        source=source,
        started_at=_now(),
        locations_requested=0,
        locations_succeeded=0,
        locations_failed=0,
        reviews_received=0,
        reviews_created=0,
        reviews_updated=0,
        reviews_unchanged=0,
        rating_only_reviews=0,
        duplicates_skipped=0,
        analysis_jobs_created=0,
    )

    adapter = get_adapter(source)
    connection = GoogleConnection.query.filter_by(
        tenant_id=tenant_id, business_id=business_id
    ).first()

    # Determine which outlets to process
    query = Outlet.query.filter(
        Outlet.tenant_id == tenant_id,
        Outlet.business_id == business_id,
        Outlet.monitor_enabled == True,
    )
    if outlet_ids:
        query = query.filter(Outlet.id.in_(outlet_ids))

    outlets = query.all()
    report.locations_requested = len(outlets)

    for outlet in outlets:
        if outlet.status == "old_or_closed":
            logger.info("Skipping old_or_closed outlet: %s", outlet.name)
            continue

        location_id = outlet.gbp_location_id
        if not location_id:
            report.locations_failed += 1
            if not report.errors:
                report.errors = []
            report.errors.append({"outlet": outlet.name, "error": "No google_location_id"})
            continue

        try:
            result = _sync_location(
                tenant_id, business_id, outlet, source, adapter, upsert_callback
            )
            report.reviews_received += result.get("received", 0)
            report.reviews_created += result.get("created", 0)
            report.reviews_updated += result.get("updated", 0)
            report.reviews_unchanged += result.get("unchanged", 0)
            report.rating_only_reviews += result.get("rating_only", 0)
            report.duplicates_skipped += result.get("duplicates", 0)
            report.locations_succeeded += 1
        except Exception as e:
            logger.exception("Sync failed for outlet %s: %s", outlet.name, e)
            report.locations_failed += 1
            if not report.errors:
                report.errors = []
            report.errors.append({"outlet": outlet.name, "error": str(e)})

    report.completed_at = _now()
    db.session.add(report)
    db.session.commit()

    # Audit log
    audit = AuditLog(
        tenant_id=tenant_id,
        actor_type="system",
        action="sync.completed",
        entity_type="sync_report",
        entity_id=report.id,
        after_json={
            "source": source,
            "business_id": business_id,
            "locations_succeeded": report.locations_succeeded,
            "locations_failed": report.locations_failed,
            "reviews_created": report.reviews_created,
            "reviews_updated": report.reviews_updated,
        },
    )
    db.session.add(audit)
    db.session.commit()

    return {
        "report_id": report.id,
        "source": source,
        "locations_requested": report.locations_requested,
        "locations_succeeded": report.locations_succeeded,
        "locations_failed": report.locations_failed,
        "reviews_received": report.reviews_received,
        "reviews_created": report.reviews_created,
        "reviews_updated": report.reviews_updated,
        "reviews_unchanged": report.reviews_unchanged,
        "rating_only_reviews": report.rating_only_reviews,
        "duplicates_skipped": report.duplicates_skipped,
        "errors": report.errors,
        "started_at": report.started_at.isoformat(),
        "completed_at": report.completed_at.isoformat(),
    }


def _sync_location(
    tenant_id, business_id, outlet, source, adapter, upsert_callback
):
    """Sync a single location via paginated adapter calls."""
    result = {
        "received": 0, "created": 0, "updated": 0,
        "unchanged": 0, "rating_only": 0, "duplicates": 0,
    }

    page_token = None
    while True:
        page = adapter.list_reviews(
            business_id=business_id,
            location_id=outlet.gbp_location_id,
            page_token=page_token,
            page_size=10,
        )

        if page.get("error"):
            raise RuntimeError(page["error"])

        for review_data in page.get("reviews", []):
            result["received"] += 1

            # Build raw payload
            raw_payload = review_data.copy()

            # Prepare source_review_name for counting
            source_review_name = review_data.get("review_name", f"mock/{outlet.id}/{result['received']}")

            # Normalize via shared normalizer (handles datetime parsing etc.)
            normalized = normalize_review(
                tenant_id, business_id, outlet.id, source, review_data
            )
            # Preserve the source_review_name from raw data
            normalized["source_review_name"] = source_review_name

            # Check if rating-only
            has_text = bool(review_data.get("comment"))
            if not has_text:
                result["rating_only"] += 1

            # Call upsert
            upsert_result = upsert_callback(
                tenant_id=tenant_id,
                business_id=business_id,
                outlet_id=outlet.id,
                source=source,
                source_review_name=source_review_name,
                normalized=normalized,
                raw_payload=raw_payload,
            )

            status = upsert_result.get("status", "unchanged")
            if status == "created":
                result["created"] += 1
            elif status == "updated":
                result["updated"] += 1
            elif status == "unchanged":
                result["unchanged"] += 1
            elif status == "duplicate":
                result["duplicates"] += 1

        page_token = page.get("next_page_token")
        if not page_token:
            break

    # Update connection last_sync
    conn = GoogleConnection.query.filter_by(
        tenant_id=tenant_id, business_id=business_id
    ).first()
    if conn:
        conn.last_sync = _now()
        db.session.add(conn)
        db.session.commit()

    return result


def get_sync_report(report_id: str, tenant_id: str) -> dict:
    """Get a sync report by ID with tenant isolation."""
    report = SyncReport.query.filter_by(id=report_id, tenant_id=tenant_id).first()
    if not report:
        return None
    return {
        "id": report.id,
        "tenant_id": report.tenant_id,
        "business_id": report.business_id,
        "source": report.source,
        "locations_requested": report.locations_requested,
        "locations_succeeded": report.locations_succeeded,
        "locations_failed": report.locations_failed,
        "reviews_received": report.reviews_received,
        "reviews_created": report.reviews_created,
        "reviews_updated": report.reviews_updated,
        "reviews_unchanged": report.reviews_unchanged,
        "rating_only_reviews": report.rating_only_reviews,
        "duplicates_skipped": report.duplicates_skipped,
        "errors": report.errors,
        "started_at": report.started_at.isoformat() if report.started_at else None,
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
    }


def list_sync_reports(tenant_id: str, business_id: str = None, limit: int = 20) -> list:
    """List recent sync reports for a tenant."""
    query = SyncReport.query.filter_by(tenant_id=tenant_id)
    if business_id:
        query = query.filter_by(business_id=business_id)
    query = query.order_by(SyncReport.created_at.desc()).limit(limit)
    reports = []
    for r in query:
        reports.append({
            "id": r.id,
            "business_id": r.business_id,
            "source": r.source,
            "locations_succeeded": r.locations_succeeded,
            "locations_failed": r.locations_failed,
            "reviews_created": r.reviews_created,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        })
    return reports


def sync_public_reviews(
    tenant_id: str,
    business_id: str,
    outlet_ids: list = None,
    source: str = None,
    adapter=None,
) -> dict:
    """Public-mode review sync using a :class:`PublicReviewSourceAdapter`.

    Unlike :func:`sync_reviews`, this path requires **no Google OAuth** and no
    ``gbp_location_id``: it sources reviews from a public adapter
    (mock/outscraper/apify/playwright) keyed by the outlet's ``public_place_id``.

    Contract (GRM_PUBLIC_MONITORING_SKILL §5, §13, §14):
    - Every record carries provenance (``source`` = adapter label).
    - Vendor failure → outlet marked failed, no fabricated reviews, other
      outlets unaffected (rollback per outlet).
    - Location metadata (rating, review count, maps URL) refreshed from the
      public source; geographic fields enriched when missing.
    - ``old_or_closed`` outlets are skipped.
    """
    from app.adapters.mock_public_review_adapter import MockPublicReviewAdapter

    if adapter is None:
        adapter = MockPublicReviewAdapter()
    if source is None:
        source = adapter.source_name

    report = SyncReport(
        tenant_id=tenant_id,
        business_id=business_id,
        source=source,
        started_at=_now(),
        locations_requested=0,
        locations_succeeded=0,
        locations_failed=0,
        reviews_received=0,
        reviews_created=0,
        reviews_updated=0,
        reviews_unchanged=0,
        rating_only_reviews=0,
        duplicates_skipped=0,
        analysis_jobs_created=0,
    )

    query = Outlet.query.filter(
        Outlet.tenant_id == tenant_id,
        Outlet.business_id == business_id,
        Outlet.monitor_enabled == True,
    )
    if outlet_ids:
        query = query.filter(Outlet.id.in_(outlet_ids))

    outlets = query.all()
    report.locations_requested = len(outlets)

    for outlet in outlets:
        if outlet.status == "old_or_closed":
            logger.info("Skipping old_or_closed outlet (public): %s", outlet.name)
            continue

        place_id = outlet.public_place_id
        if not place_id:
            report.locations_failed += 1
            if not report.errors:
                report.errors = []
            report.errors.append({"outlet": outlet.name, "error": "No public_place_id"})
            continue

        result = {
            "received": 0, "created": 0, "updated": 0,
            "unchanged": 0, "rating_only": 0, "duplicates": 0,
        }
        try:
            # 1) Refresh public location metadata
            try:
                loc = adapter.fetch_location(place_id)
            except Exception as exc:
                logger.warning("fetch_location failed for %s: %s", outlet.name, exc)
                loc = None
            if loc:
                outlet.address = loc.get("full_address") or outlet.address
                outlet.maps_url = loc.get("maps_url") or outlet.maps_url
                outlet.business_rating = loc.get("business_rating") or outlet.business_rating
                outlet.business_review_count = loc.get("business_review_count") or outlet.business_review_count
                if loc.get("latitude"):
                    outlet.latitude = loc.get("latitude")
                if loc.get("longitude"):
                    outlet.longitude = loc.get("longitude")
                if not (outlet.province and outlet.city_regency and outlet.district):
                    from app.services.geo_service import enrich_location
                    enrich_location(outlet, commit=False)
                db.session.add(outlet)

            # 2) Fetch + upsert public reviews
            reviews = adapter.list_reviews_by_place_id(place_id)
            for rv in reviews:
                result["received"] += 1
                source_review_name = f"public:{place_id}:{rv['source_review_id']}"

                reviewer_name = rv.get("reviewer_name_masked") or ""
                review_data = {
                    "source_review_name": source_review_name,
                    "reviewer_display_name": reviewer_name,
                    "reviewer_is_anonymous": reviewer_name in ("", "Anonim"),
                    "star_rating": rv.get("rating"),
                    "comment": rv.get("review_text") or "",
                    "create_time": rv.get("review_date"),
                    "update_time": rv.get("review_date"),
                    "owner_reply_text": rv.get("owner_reply_text"),
                    "owner_reply_date": rv.get("owner_reply_date"),
                    "source_url": rv.get("source_url"),
                }
                normalized = normalize_review(
                    tenant_id, business_id, outlet.id, source, review_data
                )
                normalized["source_review_name"] = source_review_name

                if not normalized["has_text"]:
                    result["rating_only"] += 1

                upsert_result = upsert_review(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    outlet_id=outlet.id,
                    source=source,
                    source_review_name=source_review_name,
                    normalized=normalized,
                    raw_payload=rv,
                )
                status = upsert_result.get("status", "unchanged")
                if status == "created":
                    result["created"] += 1
                elif status == "updated":
                    result["updated"] += 1
                elif status == "unchanged":
                    result["unchanged"] += 1
                elif status == "duplicate":
                    result["duplicates"] += 1

            db.session.commit()
            report.reviews_received += result["received"]
            report.reviews_created += result["created"]
            report.reviews_updated += result["updated"]
            report.reviews_unchanged += result["unchanged"]
            report.rating_only_reviews += result["rating_only"]
            report.duplicates_skipped += result["duplicates"]
            report.locations_succeeded += 1
        except Exception as exc:
            db.session.rollback()
            logger.exception("Public sync failed for outlet %s: %s", outlet.name, exc)
            report.locations_failed += 1
            if not report.errors:
                report.errors = []
            report.errors.append({"outlet": outlet.name, "error": str(exc)})

    report.completed_at = _now()
    db.session.add(report)
    db.session.commit()

    # Ensure text reviews carry rule-based analysis (skill §8: every text
    # review is analyzed; rating-only stays out of text categories).
    from app.models.entities import ReviewAnalysis as _RA
    from app.services.analysis_service import analyze_review
    try:
        text_reviews = Review.query.filter(
            Review.tenant_id == tenant_id,
            Review.business_id == business_id,
            Review.has_text == True,
        ).all()
        analyzed = 0
        for rv in text_reviews:
            if _RA.query.filter_by(review_pk=rv.id).first() is None:
                try:
                    analyze_review(tenant_id, business_id, rv.id)
                    analyzed += 1
                except Exception:
                    logger.exception("Analysis failed for review %s", rv.id)
        report.analysis_jobs_created = analyzed
        db.session.add(report)
        db.session.commit()
    except Exception as exc:
        logger.warning("Post-sync analysis pass failed: %s", exc)

    audit = AuditLog(
        tenant_id=tenant_id,
        actor_type="system",
        action="sync.public_completed",
        entity_type="sync_report",
        entity_id=report.id,
        after_json={
            "source": source,
            "business_id": business_id,
            "locations_succeeded": report.locations_succeeded,
            "locations_failed": report.locations_failed,
            "reviews_created": report.reviews_created,
            "reviews_updated": report.reviews_updated,
        },
    )
    db.session.add(audit)
    db.session.commit()

    return {
        "report_id": report.id,
        "source": source,
        "locations_requested": report.locations_requested,
        "locations_succeeded": report.locations_succeeded,
        "locations_failed": report.locations_failed,
        "reviews_received": report.reviews_received,
        "reviews_created": report.reviews_created,
        "reviews_updated": report.reviews_updated,
        "reviews_unchanged": report.reviews_unchanged,
        "rating_only_reviews": report.rating_only_reviews,
        "duplicates_skipped": report.duplicates_skipped,
        "errors": report.errors,
        "started_at": report.started_at.isoformat() if report.started_at else None,
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
    }
