"""Dashboard routes — RUN_05 intelligence dashboard with analysis features."""
from flask import Blueprint, render_template, jsonify, g, request
from flask_login import login_required, current_user

from app.models.entities import Business, Outlet, Review, Issue, AuditLog, ReviewAnalysis
from app.services.analysis_service import (
    get_dashboard_summary,
    get_priority_reviews,
    get_outlet_comparison,
    get_management_summary,
    batch_analyze_pending,
)
from app.services.audit import log_audit

bp = Blueprint('dashboard', __name__)


# ─── PAGES ──────────────────────────────────────────────


@bp.route('/')
@login_required
def index():
    """Owner dashboard — UX redesign (all-time default; period selector).

    First-time users see ALL reviews since the first one; afterwards they
    pick a specific period (7/30/90 days, a month, or a custom range).
    """
    business = current_user.business
    if not business:
        return render_template('dashboard/index.html', business=None, stats=None,
                               summary=None, advisor=None, outlets=None, new_this_week=0,
                               period_label="Semua Waktu")

    from app.models.entities import Review, SyncReport
    from app import db as _db
    from app.services.public_analytics import (
        parse_filters, executive_summary, category_breakdown, branch_breakdown,
        period_analytics, review_explorer,
    )
    from app.services.ai_advisor import generate as advisor_generate
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func

    # Period from query params (days / month / start-end); default = ALL TIME
    f = parse_filters(request.args)
    if f.get("month"):
        period_label = f"Bulan {f['month']}"
    elif f.get("start") and f.get("end"):
        period_label = f"{f['start'].date().isoformat()} s/d {f['end'].date().isoformat()}"
    elif f.get("days"):
        period_label = f"{f['days']} hari terakhir"
    else:
        f["start"] = datetime(2000, 1, 1, tzinfo=timezone.utc)
        period_label = "Semua Waktu"

    summary = executive_summary(business.tenant_id, business.id, f)
    advisor = advisor_generate(business.tenant_id, business.id, f)
    categories = category_breakdown(business.tenant_id, business.id, f)
    branches = branch_breakdown(business.tenant_id, business.id, f)
    period = period_analytics(business.tenant_id, business.id, f)
    latest = review_explorer(business.tenant_id, business.id, f, page=1, per_page=5)

    # Star distribution (current period) from real data
    start_dt = f.get("start") or (datetime.now(timezone.utc) - timedelta(days=30))
    end_dt = f.get("end")
    star_q = _db.session.query(Review.star_rating, func.count()).filter(
        Review.tenant_id == business.tenant_id,
        Review.business_id == business.id,
        Review.create_time >= start_dt,
    )
    if end_dt:
        star_q = star_q.filter(Review.create_time <= end_dt)
    star_rows = star_q.group_by(Review.star_rating).all()
    star_dist = {r: c for r, c in star_rows if r is not None}

    outlets = Outlet.query.filter_by(
        tenant_id=business.tenant_id, business_id=business.id, monitor_enabled=True
    ).order_by(Outlet.name.asc()).all()

    last_report = (
        SyncReport.query.filter_by(tenant_id=business.tenant_id, business_id=business.id)
        .order_by(SyncReport.created_at.desc()).first()
    )
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    new_this_week = Review.query.filter(
        Review.tenant_id == business.tenant_id,
        Review.business_id == business.id,
        Review.create_time >= week_ago,
    ).count()

    # Sentiment quick counts (30d)
    counts = {
        'positive': summary.get('positive', 0),
        'neutral': summary.get('neutral', 0),
        'negative': summary.get('negative', 0),
        'total': summary.get('total_reviews', 0),
    }

    outlet_data = [
        {
            'id': o.id,
            'name': o.name,
            'rating': o.business_rating,
            'review_count': o.business_review_count,
            'city_regency': o.city_regency,
            'district': o.district,
            'last_sync': last_report.completed_at.isoformat() if last_report and last_report.completed_at else None,
        }
        for o in outlets
    ]

    stats = {
        'outlets': len(outlets),
        'reviews': counts['total'],
        'new_this_week': new_this_week,
        'positive': counts['positive'],
        'neutral': counts['neutral'],
        'negative': counts['negative'],
    }
    return render_template('dashboard/index.html', business=business, stats=stats,
                           summary=summary, advisor=advisor, outlets=outlet_data,
                           new_this_week=new_this_week, period_label=period_label,
                           categories=categories, branches=branches,
                           period=period, latest=latest, star_dist=star_dist)


@bp.route('/outlets')
@login_required
def outlets_page():
    """Owner outlet list — simple."""
    business = current_user.business
    if not business:
        return render_template('dashboard/outlets.html', business=None, outlets=None)
    from app.models.entities import SyncReport
    from datetime import datetime, timezone
    outlets = Outlet.query.filter_by(
        tenant_id=business.tenant_id, business_id=business.id, monitor_enabled=True
    ).order_by(Outlet.name.asc()).all()
    last_report = (
        SyncReport.query.filter_by(tenant_id=business.tenant_id, business_id=business.id)
        .order_by(SyncReport.created_at.desc()).first()
    )
    data = [
        {
            'id': o.id,
            'name': o.name,
            'rating': o.business_rating,
            'review_count': o.business_review_count,
            'city_regency': o.city_regency,
            'district': o.district,
            'last_sync': last_report.completed_at.isoformat() if last_report and last_report.completed_at else None,
        }
        for o in outlets
    ]
    return render_template('dashboard/outlets.html', business=business, outlets=data)


@bp.route('/reviews')
@login_required
def reviews_page():
    """Owner reviews page — positive/neutral/negative tabs + filters."""
    business = current_user.business
    return render_template('dashboard/reviews.html', business=business)


@bp.route('/settings')
@login_required
def settings_page():
    """Owner settings — profile, integration, logout."""
    business = current_user.business
    return render_template('dashboard/settings.html', business=business,
                           user=current_user)


@bp.route('/intelligence')
@login_required
def intelligence():
    """Intelligence dashboard — analysis and insights."""
    business = current_user.business
    if not business:
        return render_template('dashboard/intelligence.html', business=None)

    outlets = Outlet.query.filter_by(
        tenant_id=business.tenant_id,
        business_id=business.id,
        monitor_enabled=True,
    ).all()

    return render_template(
        'dashboard/intelligence.html',
        business=business,
        outlets=outlets,
    )


@bp.route('/advisor')
@login_required
def advisor_page():
    """AI Advisor UI panel — 'Prioritas Perbaikan Hari Ini'."""
    business = current_user.business
    return render_template('dashboard/advisor.html', business=business)


# ─── API: SUMMARY ──────────────────────────────────────


@bp.route('/api/analysis/summary')
@login_required
def api_summary():
    """API: dashboard summary with period and outlet filters."""
    business = current_user.business
    if not business:
        return jsonify(success=False, data=None, meta={}, errors=[{"code": "NO_BUSINESS", "message": "Belum ada bisnis", "field": None, "retryable": False}]), 400

    days = int(request.args.get('days', 30))
    outlet_id = request.args.get('outlet_id')

    if days not in (7, 14, 30, 90):
        days = 30

    data = get_dashboard_summary(
        tenant_id=business.tenant_id,
        business_id=business.id,
        outlet_id=outlet_id,
        days=days,
    )

    return jsonify(success=True, data=data, meta={}, errors=[])


@bp.route('/api/analysis/priority')
@login_required
def api_priority():
    """API: priority review queue."""
    business = current_user.business
    if not business:
        return jsonify(success=False, data=None, meta={}, errors=[{"code": "NO_BUSINESS", "message": "Belum ada bisnis", "field": None, "retryable": False}]), 400

    outlet_id = request.args.get('outlet_id')
    limit = min(int(request.args.get('limit', 20)), 100)

    data = get_priority_reviews(
        tenant_id=business.tenant_id,
        business_id=business.id,
        outlet_id=outlet_id,
        limit=limit,
    )

    return jsonify(success=True, data=data, meta={}, errors=[])


@bp.route('/api/analysis/outlet-comparison')
@login_required
def api_outlet_comparison():
    """API: outlet comparison."""
    business = current_user.business
    if not business:
        return jsonify(success=False, data=None, meta={}, errors=[{"code": "NO_BUSINESS", "message": "Belum ada bisnis", "field": None, "retryable": False}]), 400

    days = int(request.args.get('days', 30))

    data = get_outlet_comparison(
        tenant_id=business.tenant_id,
        business_id=business.id,
        days=days,
    )

    return jsonify(success=True, data=data, meta={}, errors=[])


@bp.route('/api/analysis/management-summary')
@login_required
def api_management_summary():
    """API: management summary."""
    business = current_user.business
    if not business:
        return jsonify(success=False, data=None, meta={}, errors=[{"code": "NO_BUSINESS", "message": "Belum ada bisnis", "field": None, "retryable": False}]), 400

    days = int(request.args.get('days', 30))

    data = get_management_summary(
        tenant_id=business.tenant_id,
        business_id=business.id,
        days=days,
    )

    return jsonify(success=True, data=data, meta={}, errors=[])


@bp.route('/api/analysis/trigger', methods=['POST'])
@login_required
def api_trigger_analysis():
    """API: trigger analysis on pending reviews."""
    business = current_user.business
    if not business:
        return jsonify(success=False, data=None, meta={}, errors=[{"code": "NO_BUSINESS", "message": "Belum ada bisnis", "field": None, "retryable": False}]), 400

    result = batch_analyze_pending(
        tenant_id=business.tenant_id,
        business_id=business.id,
    )

    return jsonify(success=True, data=result, meta={}, errors=[])


@bp.route('/api/tenant')
@login_required
def tenant_info():
    """API: current tenant context."""
    business = current_user.business
    if not business:
        return jsonify(success=True, data={'tenant': None}, meta={}, errors=[])

    return jsonify(success=True, data={
        'tenant_id': business.tenant_id,
        'business_id': business.id,
        'business_name': business.name,
        'brand_name': business.brand_name,
        'user_role': current_user.role,
    }, meta={}, errors=[])


@bp.route('/api/audit-logs')
@login_required
def audit_logs():
    """API: recent audit logs for current tenant."""
    if not current_user.has_role('owner', 'admin'):
        return jsonify(success=False, data=None, meta={}, errors=[{"code": "FORBIDDEN", "message": "Hanya owner/admin", "field": None, "retryable": False}]), 403

    business = current_user.business
    if not business:
        return jsonify(success=True, data=[], meta={}, errors=[])

    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 200)

    logs = AuditLog.query.filter_by(tenant_id=business.tenant_id)\
        .order_by(AuditLog.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(success=True, data=[{
        'id': l.id, 'action': l.action, 'actor_type': l.actor_type,
        'entity_type': l.entity_type, 'entity_id': l.entity_id,
        'created_at': l.created_at.isoformat() if l.created_at else None,
    } for l in logs.items], meta={'pagination': {'page': page, 'per_page': per_page, 'total': logs.total}}, errors=[])
