"""Dashboard routes — minimal for RUN_01, expanded in later phases."""
from flask import Blueprint, render_template, jsonify, g
from flask_login import login_required, current_user
from app.models.entities import Business, Outlet, Review, Issue, AuditLog
from app.services.audit import log_audit

bp = Blueprint('dashboard', __name__)


@bp.route('/')
@login_required
def index():
    """Main dashboard — shows business overview."""
    business = current_user.business
    if not business:
        return render_template('dashboard/index.html', business=None, stats=None)

    # Basic stats (will be expanded in later phases)
    stats = {
        'outlets': Outlet.query.filter_by(business_id=business.id).count(),
        'reviews': Review.query.filter_by(business_id=business.id).count(),
        'issues_open': Issue.query.filter_by(business_id=business.id).filter(Issue.status.notin_(['resolved', 'closed'])).count(),
    }

    return render_template('dashboard/index.html', business=business, stats=stats)


# ─── API: Tenant Info ───────────────────────────────────
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


# ─── API: Audit Log (owner/admin only) ──────────────────
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


# Need request for query params
from flask import request
