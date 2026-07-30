"""Issue tracking API blueprint — creation, assignment, escalation, closure, patterns, reports."""
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app import db
from app.models.entities import Issue, IssuePattern, PatternReview, Review, ReviewAnalysis
from app.services import issue_service

logger = logging.getLogger(__name__)

issue_bp = Blueprint('issue', __name__)


def _require_tenant():
    """Get current user's tenant or abort."""
    tenant_id = getattr(current_user, 'tenant_id', None)
    if not tenant_id:
        return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'No tenant'}]}), 403
    return tenant_id


# ─── POST /api/issues — Create Issue ─────────────────────

@issue_bp.route('/api/issues', methods=['POST'])
@login_required
def create_issue():
    """Create issue from a review."""
    tenant_id = _require_tenant()
    data = request.get_json(silent=True) or {}
    review_id = data.get('review_id')
    analysis_id = data.get('analysis_id')

    if not review_id:
        return jsonify({'success': False, 'errors': [{'code': 'VALIDATION', 'message': 'review_id required'}]}), 400

    # Verify review belongs to tenant
    review = db.session.get(Review, review_id)
    if not review:
        return jsonify({'success': False, 'errors': [{'code': 'NOT_FOUND', 'message': 'Review not found'}]}), 404
    if review.tenant_id != tenant_id:
        return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

    try:
        issue = issue_service.create_issue(review_id, analysis_id, actor_user_id=current_user.id)
        db.session.commit()
        return jsonify({'success': True, 'data': issue_service.issue_to_json(issue)}), 201
    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'VALIDATION', 'message': str(e)}]}), 400


# ─── GET /api/issues — List Issues ───────────────────────

@issue_bp.route('/api/issues', methods=['GET'])
@login_required
def list_issues():
    """List issues with optional filters."""
    tenant_id = _require_tenant()
    status = request.args.get('status')
    urgency = request.args.get('urgency')
    outlet_id = request.args.get('outlet_id')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    issues = issue_service.list_issues(
        tenant_id=tenant_id, status=status, urgency=urgency,
        outlet_id=outlet_id, limit=min(limit, 200), offset=offset
    )
    return jsonify({
        'success': True,
        'data': [issue_service.issue_to_json(i) for i in issues],
        'meta': {'total': len(issues), 'limit': limit, 'offset': offset, 'timestamp': datetime.now(timezone.utc).isoformat()}
    })


# ─── GET /api/issues/<id> — Get Issue ────────────────────

@issue_bp.route('/api/issues/<issue_id>', methods=['GET'])
@login_required
def get_issue(issue_id: str):
    """Get issue details."""
    tenant_id = _require_tenant()
    try:
        issue = issue_service.get_issue(issue_id)
        if issue.tenant_id != tenant_id:
            return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403
        return jsonify({'success': True, 'data': issue_service.issue_to_json(issue)})
    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'NOT_FOUND', 'message': str(e)}]}), 404


# ─── PATCH /api/issues/<id> — Update Issue ───────────────

@issue_bp.route('/api/issues/<issue_id>', methods=['PATCH'])
@login_required
def update_issue(issue_id: str):
    """Update issue (status, assignment, notes)."""
    tenant_id = _require_tenant()
    data = request.get_json(silent=True) or {}

    try:
        issue = issue_service.get_issue(issue_id)
        if issue.tenant_id != tenant_id:
            return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

        # Status change
        if 'status' in data:
            issue_service.update_issue_status(
                issue_id, data['status'],
                actor_user_id=current_user.id,
                reason=data.get('reason')
            )

        # Assignment
        if 'assigned_user_id' in data:
            issue_service.assign_issue(
                issue_id, data['assigned_user_id'],
                actor_user_id=current_user.id
            )

        # Internal notes
        if 'note' in data:
            issue_service.add_internal_note(issue_id, data['note'], current_user.id)

        db.session.commit()
        issue = issue_service.get_issue(issue_id)
        return jsonify({'success': True, 'data': issue_service.issue_to_json(issue)})

    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'VALIDATION', 'message': str(e)}]}), 400


# ─── POST /api/issues/<id>/close — Close Issue ───────────

@issue_bp.route('/api/issues/<issue_id>/close', methods=['POST'])
@login_required
def close_issue(issue_id: str):
    """Close issue with required evidence."""
    tenant_id = _require_tenant()
    data = request.get_json(silent=True) or {}

    try:
        issue = issue_service.get_issue(issue_id)
        if issue.tenant_id != tenant_id:
            return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

        issue_service.close_issue(
            issue_id, actor_user_id=current_user.id,
            resolution_summary=data.get('resolution_summary'),
            evidence=data.get('evidence'),
            action_notes=data.get('action_notes'),
        )
        db.session.commit()
        issue = issue_service.get_issue(issue_id)
        return jsonify({'success': True, 'data': issue_service.issue_to_json(issue)})

    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'VALIDATION', 'message': str(e)}]}), 400


# ─── POST /api/issues/<id>/reopen — Reopen Issue ─────────

@issue_bp.route('/api/issues/<issue_id>/reopen', methods=['POST'])
@login_required
def reopen_issue(issue_id: str):
    """Reopen a closed/resolved issue."""
    tenant_id = _require_tenant()
    data = request.get_json(silent=True) or {}

    try:
        issue = issue_service.get_issue(issue_id)
        if issue.tenant_id != tenant_id:
            return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

        issue_service.reopen_issue(
            issue_id, actor_user_id=current_user.id,
            reason=data.get('reason')
        )
        db.session.commit()
        issue = issue_service.get_issue(issue_id)
        return jsonify({'success': True, 'data': issue_service.issue_to_json(issue)})

    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'VALIDATION', 'message': str(e)}]}), 400


# ─── POST /api/issues/<id>/escalate — Escalate ───────────

@issue_bp.route('/api/issues/<issue_id>/escalate', methods=['POST'])
@login_required
def escalate_issue(issue_id: str):
    """Escalate issue to owner."""
    tenant_id = _require_tenant()
    data = request.get_json(silent=True) or {}

    try:
        issue = issue_service.get_issue(issue_id)
        if issue.tenant_id != tenant_id:
            return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

        issue_service.escalate_issue(
            issue_id, actor_user_id=current_user.id,
            reason=data.get('reason')
        )
        db.session.commit()
        issue = issue_service.get_issue(issue_id)
        return jsonify({'success': True, 'data': issue_service.issue_to_json(issue)})

    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'VALIDATION', 'message': str(e)}]}), 400


# ─── POST /api/issues/pattern — Create/Update Pattern ────

@issue_bp.route('/api/issues/pattern', methods=['POST'])
@login_required
def create_pattern():
    """Create or update a pattern grouping."""
    tenant_id = _require_tenant()
    data = request.get_json(silent=True) or {}
    pattern_key = data.get('pattern_key')
    if not pattern_key:
        return jsonify({'success': False, 'errors': [{'code': 'VALIDATION', 'message': 'pattern_key required'}]}), 400

    business_id = data.get('business_id')
    if not business_id:
        return jsonify({'success': False, 'errors': [{'code': 'VALIDATION', 'message': 'business_id required'}]}), 400

    try:
        pattern = issue_service.create_or_update_pattern(
            pattern_key=pattern_key,
            tenant_id=tenant_id,
            business_id=business_id,
            title=data.get('title'),
            parent_issue_id=data.get('parent_issue_id'),
            outlet_specific=data.get('outlet_specific', False),
        )

        # Link supporting reviews
        for review_id in (data.get('supporting_review_ids') or []):
            issue_service.link_review_to_pattern(pattern.id, review_id, data.get('parent_issue_id'))

        db.session.commit()

        result = issue_service.get_pattern_with_reviews(pattern.id)
        return jsonify({
            'success': True,
            'data': {
                'id': result['pattern'].id,
                'pattern_key': result['pattern'].pattern_key,
                'title': result['pattern'].title,
                'parent_issue_id': result['pattern'].parent_issue_id,
                'review_count': result['review_count'],
                'supporting_reviews': result['supporting_reviews'],
            }
        }), 201
    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'VALIDATION', 'message': str(e)}]}), 400


# ─── GET /api/issues/pattern/<id> — Get Pattern ──────────

@issue_bp.route('/api/issues/pattern/<pattern_id>', methods=['GET'])
@login_required
def get_pattern(pattern_id: str):
    """Get pattern with supporting reviews."""
    tenant_id = _require_tenant()
    try:
        result = issue_service.get_pattern_with_reviews(pattern_id)
        if result['pattern'].tenant_id != tenant_id:
            return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403
        return jsonify({'success': True, 'data': {
            'id': result['pattern'].id,
            'pattern_key': result['pattern'].pattern_key,
            'title': result['pattern'].title,
            'parent_issue_id': result['pattern'].parent_issue_id,
            'trend': result['pattern'].trend,
            'outlet_specific': result['pattern'].outlet_specific,
            'review_count': result['review_count'],
            'supporting_reviews': result['supporting_reviews'],
        }})
    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'NOT_FOUND', 'message': str(e)}]}), 404


# ─── GET /api/issues/report — Reports ────────────────────

@issue_bp.route('/api/issues/report', methods=['GET'])
@login_required
def get_report():
    """Get weekly or monthly report."""
    tenant_id = _require_tenant()
    report_type = request.args.get('type', 'weekly')
    business_id = request.args.get('business_id')

    try:
        if report_type == 'monthly':
            report = issue_service.get_monthly_report(tenant_id, business_id)
        else:
            report = issue_service.get_weekly_report(tenant_id, business_id)
        return jsonify({'success': True, 'data': report})
    except Exception as e:
        return jsonify({'success': False, 'errors': [{'code': 'ERROR', 'message': str(e)}]}), 500
