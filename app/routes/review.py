"""Routes for Review Ingestion — sync, import, history, status."""

import csv
import hashlib
import io
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint, render_template, request, jsonify, session,
    redirect, url_for, flash, current_app
)

from app import db
from app.models.entities import (
    Business, Outlet, GoogleConnection, Review, ReviewVersion,
    ImportBatch, SyncReport, PubsubEvent, AuditLog
)
from app.services.review_service import normalize_review, upsert_review
from app.services.review_source_adapter import get_adapter, MockReviewAdapter
from app.services.sync_service import sync_reviews, get_sync_report, list_sync_reports
from app.services.import_service import (
    parse_import_file, detect_column_mapping, execute_import, preview_import
)
from app.services.event_service import process_mock_event, pubsub_health_check
from app.services.reconciliation_service import reconcile_reviews

review_bp = Blueprint("review", __name__, url_prefix="/review")
logger = logging.getLogger(__name__)


# ─── HELPERS ──────────────────────────────────────────

def _get_tenant():
    return session.get("tenant_id") or request.headers.get("X-Tenant-ID")


def _get_business():
    return session.get("business_id")


def _require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def _get_connection():
    """Get the GoogleConnection for this tenant/business (mock)."""
    tenant_id = _get_tenant()
    business_id = _get_business()
    if not tenant_id or not business_id:
        return None
    conn = GoogleConnection.query.filter_by(
        tenant_id=tenant_id, business_id=business_id
    ).first()
    return conn


# ─── REVIEW SOURCES STATUS ──────────────────────────

@review_bp.route("/sources")
@_require_auth
def sources():
    """Status page for all review sources."""
    conn = _get_connection()
    adapter = get_adapter("mock")
    health = adapter.health_check()

    pubsub_health = pubsub_health_check()

    # Outlet count
    outlets = Outlet.query.filter_by(
        tenant_id=_get_tenant(),
        business_id=_get_business(),
    ).all()
    active_outlets = sum(1 for o in outlets if o.monitor_enabled and o.status != "old_or_closed")

    return render_template(
        "review/sources.html",
        connection=conn,
        adapter_health=health,
        pubsub_health=pubsub_health,
        active_outlets=active_outlets,
        total_outlets=len(outlets),
    )


# ─── SYNC ────────────────────────────────────────────

@review_bp.route("/sync", methods=["GET", "POST"])
@_require_auth
def sync():
    """Manual trigger historical sync."""
    tenant_id = _get_tenant()
    business_id = _get_business()

    outlets = Outlet.query.filter(
        Outlet.tenant_id == tenant_id,
        Outlet.business_id == business_id,
        Outlet.monitor_enabled == True,
        Outlet.status != "old_or_closed",
    ).all()

    if request.method == "POST":
        outlet_ids = request.form.getlist("outlet_ids")
        source = request.form.get("source", "mock")

        # Convert outlet_ids to UUIDs if provided
        outlet_uuids = None
        if outlet_ids:
            outlet_uuids = [oid for oid in outlet_ids if oid.strip()]

        result = sync_reviews(
            tenant_id=tenant_id,
            business_id=business_id,
            source=source,
            outlet_ids=outlet_uuids,
        )
        flash(f"Sync completed. Created: {result['reviews_created']}, Updated: {result['reviews_updated']}", "success")
        return redirect(url_for("review.sync_history"))

    return render_template("review/sync.html", outlets=outlets)


@review_bp.route("/sync/run", methods=["POST"])
@_require_auth
def sync_run():
    """API endpoint for sync."""
    tenant_id = _get_tenant()
    business_id = _get_business()
    data = request.get_json() or {}
    outlet_ids = data.get("outlet_ids")
    source = data.get("source", "mock")

    result = sync_reviews(
        tenant_id=tenant_id,
        business_id=business_id,
        source=source,
        outlet_ids=outlet_ids,
    )
    return jsonify(result)


# ─── SYNC HISTORY ────────────────────────────────────

@review_bp.route("/sync/history")
@_require_auth
def sync_history():
    """List recent sync reports."""
    tenant_id = _get_tenant()
    business_id = _get_business()
    reports = list_sync_reports(tenant_id, business_id)
    return render_template("review/sync_history.html", reports=reports)


@review_bp.route("/sync/report/<report_id>")
@_require_auth
def sync_report_detail(report_id):
    """View sync report detail."""
    tenant_id = _get_tenant()
    report = get_sync_report(report_id, tenant_id)
    if not report:
        flash("Sync report not found", "error")
        return redirect(url_for("review.sync_history"))
    return render_template("review/sync_report.html", report=report)


# ─── IMPORT ──────────────────────────────────────────

@review_bp.route("/import", methods=["GET", "POST"])
@_require_auth
def import_reviews():
    """CSV/XLSX Outscraper import page."""
    tenant_id = _get_tenant()
    business_id = _get_business()

    outlets = Outlet.query.filter_by(
        tenant_id=tenant_id,
        business_id=business_id,
    ).all()

    if request.method == "POST":
        # Handle file upload
        if "file" not in request.files:
            flash("No file uploaded", "error")
            return render_template("review/import.html", outlets=outlets)

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected", "error")
            return render_template("review/import.html", outlets=outlets)

        # Save uploaded file temporarily
        ext = os.path.splitext(file.filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        file_type = "csv" if ext == ".csv" else "xlsx" if ext in (".xlsx", ".xls") else None

        if not file_type:
            os.unlink(tmp_path)
            flash("Unsupported file type. Only CSV and XLSX are supported.", "error")
            return render_template("review/import.html", outlets=outlets)

        # Get column mapping from form
        mapping_raw = request.form.get("column_mapping", "{}")
        try:
            column_mapping = json.loads(mapping_raw)
        except (json.JSONDecodeError, TypeError):
            column_mapping = {}

        # Get outlet mapping from form
        outlet_map_raw = request.form.get("outlet_mapping", "{}")
        try:
            outlet_map = json.loads(outlet_map_raw)
        except (json.JSONDecodeError, TypeError):
            outlet_map = {}

        action = request.form.get("action", "import")

        if action == "preview":
            result = preview_import(tmp_path, file_type)
            os.unlink(tmp_path)
            return render_template("review/import_preview.html",
                                   preview=result,
                                   outlets=outlets,
                                   filename=file.filename)

        elif action == "import":
            # Parse file first, then import
            parsed_rows, parse_errors = parse_import_file(tmp_path, file_type)
            if parse_errors:
                os.unlink(tmp_path)
                flash(f"File parse errors: {'; '.join(parse_errors)}", "error")
                return render_template("review/import.html", outlets=outlets)

            result = execute_import(
                tenant_id=tenant_id,
                business_id=business_id,
                mapping=column_mapping,
                rows=parsed_rows,
                outlet_map=outlet_map,
                file_name=file.filename,
                user_id=session.get("user_id", "system"),
            )
            os.unlink(tmp_path)
            flash(f"Import completed: {result.get('rows_valid', 0)} valid, "
                  f"{result.get('rows_invalid', 0)} invalid, "
                  f"{result.get('duplicates', 0)} duplicates", "success")
            return redirect(url_for("review.sync_history"))

    return render_template("review/import.html", outlets=outlets)


# ─── RECONCILIATION ──────────────────────────────────

@review_bp.route("/reconcile", methods=["POST"])
@_require_auth
def reconcile():
    """Trigger reconciliation."""
    tenant_id = _get_tenant()
    business_id = _get_business()
    result = reconcile_reviews(tenant_id=tenant_id, business_id=business_id)
    flash(f"Reconciliation completed. Updated: {result['reviews_updated']}, "
          f"Marked unavailable: {result['reviews_marked_unavailable']}", "success")
    return redirect(url_for("review.sources"))


# ─── REVIEW LIST ─────────────────────────────────────

@review_bp.route("/list")
@_require_auth
def review_list():
    """List reviews for this tenant."""
    tenant_id = _get_tenant()
    business_id = _get_business()

    outlet_id = request.args.get("outlet_id")
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = Review.query.filter_by(
        tenant_id=tenant_id,
        business_id=business_id,
    )

    if outlet_id:
        query = query.filter_by(outlet_id=outlet_id)

    query = query.order_by(Review.update_time.desc())
    reviews = query.paginate(page=page, per_page=per_page, error_out=False)

    outlets = Outlet.query.filter_by(tenant_id=tenant_id, business_id=business_id).all()

    return render_template("review/list.html", reviews=reviews, outlets=outlets,
                           selected_outlet=outlet_id)


# ─── EVENT PROCESSING (Mock) ─────────────────────────

@review_bp.route("/events/simulate", methods=["POST"])
@_require_auth
def simulate_event():
    """Simulate a NEW_REVIEW or UPDATED_REVIEW event for testing."""
    tenant_id = _get_tenant()
    business_id = _get_business()
    data = request.get_json()

    if not data:
        return jsonify({"error": "Missing payload"}), 400

    event_type = data.get("event_type", "NEW_REVIEW")
    outlet_id = data.get("outlet_id")

    if not outlet_id:
        return jsonify({"error": "outlet_id required"}), 400

    review_data = data.get("review_data", {})

    result = process_mock_event(
        event_type=event_type,
        tenant_id=tenant_id,
        business_id=business_id,
        outlet_id=outlet_id,
        review_data=review_data,
    )
    return jsonify(result)


# ─── PUB/SUB SETTINGS ────────────────────────────────

@review_bp.route("/pubsub")
@_require_auth
def pubsub_settings():
    """Pub/Sub configuration page (mock)."""
    health = pubsub_health_check()
    return render_template("review/pubsub.html", health=health)
