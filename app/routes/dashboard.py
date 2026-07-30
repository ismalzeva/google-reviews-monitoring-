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
    """Main dashboard — redirect to intelligence view."""
    business = current_user.business
    if not business:
        return render_template('dashboard/index.html', business=None, stats=None)

    # Basic stats
    stats = {
        'outlets': Outlet.query.filter_by(business_id=business.id).count(),
        'reviews': Review.query.filter_by(business_id=business.id).count(),
        'issues_open': Issue.query.filter_by(business_id=business.id).filter(
            Issue.status.notin_(['resolved', 'closed'])).count(),
    }

    return render_template('dashboard/index.html', business=business, stats=stats)


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
