"""Public Monitoring API routes — RUN_09.

GRM Monitor mode: input brand name / Google Maps URL / Place ID → discover
public locations → verify → sync public reviews (no Google OAuth required).

Safety contract (GRM_PUBLIC_MONITORING_SKILL §15):
- No OAuth needed; direct reply stays disabled; auto-reply OFF.
- old_or_closed locations remain excluded.
- Source labeling explicit; mock never presented as official Google data.
"""
import csv
import io
import logging
import re

from flask import Blueprint, jsonify, request, Response
from flask_login import login_required, current_user

from app import db
from app.models.entities import LocationCandidate, Outlet, Business
from app.adapters.mock_public_review_adapter import MockPublicReviewAdapter
from app.services.discovery import (
    search_places,
    normalize_candidate,
    deduplicate_candidates,
    save_candidates,
    verify_candidate,
)
from app.services.sync_service import sync_public_reviews
from app.services import public_analytics

logger = logging.getLogger(__name__)

bp = Blueprint("public", __name__, url_prefix="/api/public")

_PUBLIC_ADAPTER = MockPublicReviewAdapter()


def _get_business() -> Business:
    """Current user's business (tenant-scoped)."""
    return current_user.business if current_user.is_authenticated else None


def _extract_place_id(url: str):
    """Extract a Google place ID from a Maps URL, or None."""
    if not url:
        return None
    m = re.search(r"place_id[:=]([A-Za-z0-9_:\-]+)", url)
    if m:
        return m.group(1)
    # Embedded hex place ID in /maps/place/…/data=!3m5!1s0x…:0x…
    m = re.search(r"!3m5!1s([0-9a-fA-Fx:]+)", url)
    if m:
        return m.group(1)
    return None


def _candidate_payload(c: LocationCandidate) -> dict:
    return {
        "id": c.id,
        "place_id": c.place_id,
        "display_name": c.display_name,
        "formatted_address": c.formatted_address,
        "province": c.province,
        "city_regency": c.city_regency,
        "district": c.district,
        "latitude": c.latitude,
        "longitude": c.longitude,
        "business_status": c.business_status,
        "google_maps_uri": c.google_maps_uri,
        "rating": c.rating,
        "review_count": c.review_count,
        "match_confidence": c.match_confidence,
        "owner_verification_status": c.owner_verification_status,
        "needs_geographic_resolution": c.needs_geographic_resolution,
    }


# ─── DISCOVER ───────────────────────────────────────────────
@bp.route("/discover", methods=["POST"])
@login_required
def discover():
    """Discover public locations from brand name, Maps URL, or Place ID.

    Body (JSON):
        {"query": "Bubur Fay"} | {"query": "Bubur Fay", "city": "Depok"}
        {"url": "https://www.google.com/maps/place/?q=place_id:…"}
        {"place_id": "ChIJ…"}
    """
    business = _get_business()
    if not business:
        return jsonify({"error": "No business bound to account"}), 400

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    city = (data.get("city") or "").strip() or None
    url = (data.get("url") or "").strip()
    place_id = (data.get("place_id") or "").strip()

    candidates = []

    # Direct place_id (from URL or field)
    direct_place_id = place_id or _extract_place_id(url)
    if direct_place_id:
        existing = LocationCandidate.query.filter_by(
            tenant_id=business.tenant_id, place_id=direct_place_id
        ).first()
        if existing:
            candidates.append(existing)
        else:
            try:
                loc = _PUBLIC_ADAPTER.fetch_location(direct_place_id)
            except Exception as exc:
                logger.warning("Unknown public place_id %s: %s", direct_place_id, exc)
                return (
                    jsonify(
                        {
                            "error": "Lokasi tidak ditemukan di sumber publik",
                            "place_id": direct_place_id,
                        }
                    ),
                    404,
                )
            raw = {
                "place_id": loc["place_id"],
                "display_name": loc["business_name"],
                "formatted_address": loc["full_address"],
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
                "business_status": "OPERATIONAL",
                "google_maps_uri": loc.get("maps_url"),
                "rating": loc.get("business_rating"),
                "review_count": loc.get("business_review_count"),
            }
            cand = normalize_candidate(
                raw, business.id, business.tenant_id, direct_place_id
            )
            candidates = save_candidates([cand])
            candidates = candidates or [cand]

    # Brand-name query
    if not candidates and query:
        if len(query) < 3:
            return jsonify({"error": "Query minimal 3 karakter"}), 400
        raw_results = search_places(query, city=city)
        if not raw_results:
            return jsonify({"error": "Tidak ada lokasi ditemukan", "query": query}), 404
        cands = [
            normalize_candidate(r, business.id, business.tenant_id, query)
            for r in raw_results
        ]
        existing_cands = LocationCandidate.query.filter_by(
            tenant_id=business.tenant_id
        ).all()
        deduped = deduplicate_candidates(cands, existing_cands)
        if deduped:
            save_candidates(deduped)
        # Surface existing candidates matching this query too (verified/old),
        # so discovery always shows the full relevant list.
        raw_place_ids = [r["place_id"] for r in raw_results if r.get("place_id")]
        matched_existing = []
        if raw_place_ids:
            matched_existing = LocationCandidate.query.filter(
                LocationCandidate.tenant_id == business.tenant_id,
                LocationCandidate.place_id.in_(raw_place_ids),
            ).all()
        seen_ids = {c.place_id for c in matched_existing}
        candidates = list(matched_existing) + [
            c for c in deduped if c.place_id not in seen_ids
        ]

    if not candidates:
        return jsonify({"error": "Input tidak dikenali. Gunakan query, url, atau place_id."}), 400

    return jsonify({"candidates": [_candidate_payload(c) for c in candidates]})


# ─── VERIFY ─────────────────────────────────────────────────
@bp.route("/verify", methods=["POST"])
@login_required
def verify():
    """Verify a discovered candidate → creates an Outlet when confirmed.

    Body (JSON): {"candidate_id": "...", "decision": "owner_confirmed"|…}
    """
    data = request.get_json(silent=True) or {}
    candidate_id = (data.get("candidate_id") or "").strip()
    decision = (data.get("decision") or "").strip()

    if not candidate_id or not decision:
        return jsonify({"error": "candidate_id dan decision wajib"}), 400

    candidate = LocationCandidate.query.filter_by(
        id=candidate_id, tenant_id=current_user.business.tenant_id
    ).first()
    if not candidate:
        return jsonify({"error": "Candidate tidak ditemukan"}), 404

    result = verify_candidate(
        candidate_id=candidate_id,
        decision=decision,
        user_id=str(current_user.id),
        note=data.get("note", ""),
        tenant_id=current_user.business.tenant_id,
    )
    if result is None:
        return jsonify({"error": "Decision tidak valid"}), 400

    outlet = None
    if decision == "owner_confirmed":
        outlet = Outlet.query.filter_by(
            business_id=candidate.business_id,
            public_place_id=candidate.place_id,
        ).first()

    return jsonify(
        {
            "candidate": _candidate_payload(result),
            "outlet": (
                {
                    "id": outlet.id,
                    "name": outlet.name,
                    "address": outlet.address,
                    "maps_url": outlet.maps_url,
                    "business_rating": outlet.business_rating,
                    "business_review_count": outlet.business_review_count,
                    "province": outlet.province,
                    "city_regency": outlet.city_regency,
                    "district": outlet.district,
                    "monitor_enabled": outlet.monitor_enabled,
                    "source": outlet.source,
                }
                if outlet
                else None
            ),
        }
    )


# ─── SYNC ───────────────────────────────────────────────────
@bp.route("/sync", methods=["POST"])
@login_required
def sync():
    """Run public review sync for outlets (no OAuth).

    Body (JSON): {"outlet_ids": ["…", "…"]}  (optional; default = all monitored)
    """
    business = _get_business()
    if not business:
        return jsonify({"error": "No business bound to account"}), 400

    data = request.get_json(silent=True) or {}
    outlet_ids = data.get("outlet_ids") or None
    source = data.get("source")  # optional override

    report = sync_public_reviews(
        tenant_id=business.tenant_id,
        business_id=business.id,
        outlet_ids=outlet_ids,
        source=source,
    )
    return jsonify(report)


# ─── LOCATIONS ──────────────────────────────────────────────
@bp.route("/locations", methods=["GET"])
@login_required
def locations():
    """List public-monitored outlets for the tenant with geographic fields.

    Includes provider/sync status per outlet (no raw secrets or sensitive
    vendor errors).
    """
    business = _get_business()
    if not business:
        return jsonify({"error": "No business bound to account"}), 400

    from app.models.entities import SyncReport
    from app.services.public_provider import get_public_review_provider

    try:
        provider = get_public_review_provider()
    except ValueError:
        provider = "unknown"

    last_reports = {}
    reports = (
        SyncReport.query.filter_by(tenant_id=business.tenant_id)
        .order_by(SyncReport.created_at.desc())
        .limit(50)
        .all()
    )
    for r in reports:
        if r.business_id not in last_reports:
            last_reports[r.business_id] = r

    outlets = (
        Outlet.query.filter_by(tenant_id=business.tenant_id)
        .order_by(Outlet.name.asc())
        .all()
    )
    payload = []
    for o in outlets:
        report = last_reports.get(o.business_id)
        payload.append(
            {
                "id": o.id,
                "name": o.name,
                "address": o.address,
                "province": o.province,
                "city_regency": o.city_regency,
                "district": o.district,
                "latitude": o.latitude,
                "longitude": o.longitude,
                "maps_url": o.maps_url,
                "business_rating": o.business_rating,
                "business_review_count": o.business_review_count,
                "source": o.source,
                "provider": report.source if report else provider,
                "last_sync": report.completed_at.isoformat() if report and report.completed_at else None,
                "sync_status": (
                    "ok" if report and report.locations_failed == 0 else
                    ("partial_failure" if report and report.locations_failed else
                     ("never" if not report else "error"))
                ),
                "reviews_inserted": report.reviews_created if report else 0,
                "reviews_updated": report.reviews_updated if report else 0,
                "reviews_skipped": (report.reviews_unchanged + report.duplicates_skipped) if report else 0,
                "error_count": len(report.errors) if report and report.errors else 0,
                "status": o.status,
                "monitor_enabled": o.monitor_enabled,
                "needs_geographic_resolution": o.needs_geographic_resolution,
            }
        )
    return jsonify({"outlets": payload, "configured_provider": provider})


# ─── ANALYTICS ─────────────────────────────────────────────
def _filters():
    return public_analytics.parse_filters(request.args)


def _require_business():
    business = current_user.business
    if not business:
        return None, (jsonify({"error": "No business bound to account"}), 400)
    return business, None


@bp.route("/analytics/summary")
@login_required
def analytics_summary():
    business, err = _require_business()
    if err:
        return err
    data = public_analytics.executive_summary(business.tenant_id, business.id, _filters())
    return jsonify(data)


@bp.route("/analytics/categories")
@login_required
def analytics_categories():
    business, err = _require_business()
    if err:
        return err
    data = public_analytics.category_breakdown(business.tenant_id, business.id, _filters())
    return jsonify(data)


@bp.route("/analytics/branches")
@login_required
def analytics_branches():
    business, err = _require_business()
    if err:
        return err
    data = public_analytics.branch_breakdown(business.tenant_id, business.id, _filters())
    return jsonify(data)


@bp.route("/analytics/geography")
@login_required
def analytics_geography():
    business, err = _require_business()
    if err:
        return err
    data = public_analytics.geographic_breakdown(business.tenant_id, business.id, _filters())
    return jsonify(data)


@bp.route("/analytics/period")
@login_required
def analytics_period():
    business, err = _require_business()
    if err:
        return err
    data = public_analytics.period_analytics(business.tenant_id, business.id, _filters())
    return jsonify(data)


@bp.route("/analytics/explorer")
@login_required
def analytics_explorer():
    business, err = _require_business()
    if err:
        return err
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    data = public_analytics.review_explorer(
        business.tenant_id, business.id, _filters(), page=page, per_page=per_page
    )
    return jsonify(data)


@bp.route("/analytics/priority")
@login_required
def analytics_priority():
    business, err = _require_business()
    if err:
        return err
    data = public_analytics.priority_insights(business.tenant_id, business.id, _filters())
    return jsonify(data)


# ─── EXPORT (§12) ──────────────────────────────────────────
def _export_filename(ext: str) -> str:
    from datetime import datetime
    return f"grm_public_reviews_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"


def _export_metadata(f: dict) -> dict:
    """Filter metadata recorded on every export (skill §12)."""
    from datetime import datetime
    start = f.get("start")
    end = f.get("end")
    return {
        "rentang_waktu": (
            f"{start.date().isoformat()} — {end.date().isoformat()}" if start and end else "auto (30 hari)"
        ),
        "kota_kabupaten": f.get("city") or "semua",
        "kecamatan": f.get("district") or "semua",
        "cabang": ",".join(f["outlet_ids"]) if f.get("outlet_ids") else "semua",
        "kategori": f.get("category") or "semua",
        "rating": ",".join(str(r) for r in f["ratings"]) if f.get("ratings") else "semua",
        "sentimen": f.get("sentiment") or "semua",
        "urgensi": f.get("urgency") or "semua",
        "sumber": f.get("source") or "semua",
        "generated_at": datetime.now().isoformat(),
    }


@bp.route("/analytics/export.csv")
@login_required
def export_csv():
    business, err = _require_business()
    if err:
        return err
    f = _filters()
    rows = public_analytics.export_rows(business.tenant_id, business.id, f)
    buf = io.StringIO()
    for k, v in _export_metadata(f).items():
        buf.write(f"# {k}: {v}\n")
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) if rows else ["tanggal"])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    csv_text = buf.getvalue()
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={_export_filename('csv')}"},
    )


@bp.route("/analytics/export.xlsx")
@login_required
def export_xlsx():
    business, err = _require_business()
    if err:
        return err
    try:
        from openpyxl import Workbook
    except ImportError:
        return jsonify({"error": "XLSX export belum tersedia (openpyxl belum terinstall). Gunakan CSV."}), 501
    f = _filters()
    rows = public_analytics.export_rows(business.tenant_id, business.id, f)
    wb = Workbook()
    # Sheet 1 — Export Info (filter metadata)
    ws_info = wb.active
    ws_info.title = "Export Info"
    for k, v in _export_metadata(f).items():
        ws_info.append([k, v])
    # Sheet 2 — data
    ws = wb.create_sheet("Public Reviews")
    headers = list(rows[0].keys()) if rows else ["tanggal"]
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, "") for h in headers])
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return Response(
        bio.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={_export_filename('xlsx')}"},
    )
