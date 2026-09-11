"""Response API blueprint — draft, approval, publication, moderation endpoints."""
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app import db
from app.models.entities import Review, ReviewReply, Approval

logger = logging.getLogger(__name__)

response_bp = Blueprint('response', __name__)


def _tenant_id():
    """Tenant id of the logged-in user's business.

    BUGFIX: routes below used to read `current_user.tenant_id` directly,
    but the User model has no `tenant_id` column/property (only
    `business_id`) — every call raised AttributeError -> 500. The correct
    path, used elsewhere in the codebase, is `current_user.business.tenant_id`.
    Returns None when the user has no business bound; callers compare this
    against a review's tenant_id, so None safely fails closed (denied)
    rather than raising.
    """
    return current_user.business.tenant_id if current_user.business else None


def _reply_to_json(reply: ReviewReply) -> dict:
    return {
        'id': reply.id,
        'review_pk': reply.review_pk,
        'draft_version': reply.draft_version,
        'draft_text': reply.draft_text,
        'route': reply.route,
        'approval_status': reply.approval_status,
        'approved_text': reply.approved_text,
        'publication_status': reply.publication_status,
        'published_by': reply.published_by,
        'published_at': reply.published_at.isoformat() if reply.published_at else None,
        'created_at': reply.created_at.isoformat() if reply.created_at else None,
        'updated_at': reply.updated_at.isoformat() if reply.updated_at else None,
        'moderation_state': reply.review_reply_state,
        'policy_violation': reply.policy_violation,
    }


@response_bp.route('/api/reviews/<review_id>/reply', methods=['GET'])
@login_required
def get_reply(review_id: str):
    """Get reply/draft status for a review."""
    reply = ReviewReply.query.filter_by(review_pk=review_id).order_by(
        ReviewReply.created_at.desc()
    ).first()
    if not reply:
        return jsonify({'success': False, 'errors': [{'code': 'NOT_FOUND', 'message': 'No reply found'}]}), 404

    review = db.session.get(Review, review_id)
    if review and review.tenant_id != _tenant_id():
        return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

    return jsonify({
        'success': True,
        'data': _reply_to_json(reply),
    })


@response_bp.route('/api/reviews/<review_id>/reply', methods=['POST'])
@login_required
def generate_draft(review_id: str):
    """Generate or retrieve draft reply for a review."""
    from app.services.response_service import create_reply_draft
    from app.models.entities import ReviewAnalysis, Outlet

    review = db.session.get(Review, review_id)
    if not review:
        return jsonify({'success': False, 'errors': [{'code': 'NOT_FOUND', 'message': 'Review not found'}]}), 404

    if review.tenant_id != _tenant_id():
        return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

    # Get analysis
    analysis = ReviewAnalysis.query.filter_by(review_pk=review_id).first()
    if not analysis:
        return jsonify({
            'success': False,
            'errors': [{'code': 'NO_ANALYSIS', 'message': 'Review must be analyzed first'}]
        }), 400

    # Get outlet
    outlet = db.session.get(Outlet, review.outlet_id)

    try:
        reply = create_reply_draft(
            int(review_id), analysis, outlet, user_id=str(current_user.id)
        )
        return jsonify({
            'success': True,
            'data': _reply_to_json(reply),
        })
    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'BAD_REQUEST', 'message': str(e)}]}), 400


@response_bp.route('/api/reviews/<review_id>/reply/<reply_id>/approve', methods=['PUT'])
@login_required
def approve_reply(review_id: str, reply_id: str):
    """Approve (and optionally edit) a reply draft."""
    from app.services.response_service import approve_reply as svc_approve

    reply = db.session.get(ReviewReply, reply_id)
    if not reply:
        return jsonify({'success': False, 'errors': [{'code': 'NOT_FOUND', 'message': 'Reply not found'}]}), 404

    review = db.session.get(Review, review_id)
    if review and review.tenant_id != _tenant_id():
        return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

    data = request.get_json(silent=True) or {}
    edited_text = data.get('edited_text')
    note = data.get('note')

    try:
        reply = svc_approve(int(reply_id), user_id=str(current_user.id),
                            edited_text=edited_text, note=note)
        return jsonify({'success': True, 'data': _reply_to_json(reply)})
    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'BAD_REQUEST', 'message': str(e)}]}), 400


@response_bp.route('/api/reviews/<review_id>/reply/<reply_id>/reject', methods=['PUT'])
@login_required
def reject_reply(review_id: str, reply_id: str):
    """Reject a reply draft."""
    from app.services.response_service import reject_reply as svc_reject

    reply = db.session.get(ReviewReply, reply_id)
    if not reply:
        return jsonify({'success': False, 'errors': [{'code': 'NOT_FOUND', 'message': 'Reply not found'}]}), 404

    review = db.session.get(Review, review_id)
    if review and review.tenant_id != _tenant_id():
        return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

    data = request.get_json(silent=True) or {}
    note = data.get('note')

    try:
        reply = svc_reject(int(reply_id), user_id=str(current_user.id), note=note)
        return jsonify({'success': True, 'data': _reply_to_json(reply)})
    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'BAD_REQUEST', 'message': str(e)}]}), 400


@response_bp.route('/api/reviews/<review_id>/reply/<reply_id>/publish', methods=['POST'])
@login_required
def publish_reply(review_id: str, reply_id: str):
    """Publish a reply (mock — no Google API call)."""
    from app.services.response_service import publish_reply as svc_publish

    reply = db.session.get(ReviewReply, reply_id)
    if not reply:
        return jsonify({'success': False, 'errors': [{'code': 'NOT_FOUND', 'message': 'Reply not found'}]}), 404

    review = db.session.get(Review, review_id)
    if review and review.tenant_id != _tenant_id():
        return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

    try:
        reply = svc_publish(int(reply_id), user_id=str(current_user.id))
        return jsonify({'success': True, 'data': _reply_to_json(reply)})
    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'BAD_REQUEST', 'message': str(e)}]}), 400


@response_bp.route('/api/reviews/<review_id>/reply/<reply_id>/moderation', methods=['PUT'])
@login_required
def update_moderation(review_id: str, reply_id: str):
    """Update moderation state from review page/developer."""
    from app.services.response_service import update_moderation as svc_mod

    reply = db.session.get(ReviewReply, reply_id)
    if not reply:
        return jsonify({'success': False, 'errors': [{'code': 'NOT_FOUND', 'message': 'Reply not found'}]}), 404

    data = request.get_json(silent=True) or {}
    state = data.get('state', '').lower()
    if state not in ('published', 'rejected', 'pending_review'):
        return jsonify({
            'success': False,
            'errors': [{'code': 'BAD_REQUEST', 'message': f'Invalid state: {state}'}]
        }), 400

    violation = data.get('policy_violation', False)
    reply = svc_mod(int(reply_id), moderation_state=state, policy_violation=violation)
    return jsonify({'success': True, 'data': _reply_to_json(reply)})


@response_bp.route('/api/reviews/<review_id>/reply/<reply_id>/edit', methods=['PUT'])
@login_required
def edit_reply(review_id: str, reply_id: str):
    """Edit an existing reply (resets approval)."""
    from app.services.response_service import update_existing_reply

    reply = db.session.get(ReviewReply, reply_id)
    if not reply:
        return jsonify({'success': False, 'errors': [{'code': 'NOT_FOUND', 'message': 'Reply not found'}]}), 404

    review = db.session.get(Review, review_id)
    if review and review.tenant_id != _tenant_id():
        return jsonify({'success': False, 'errors': [{'code': 'FORBIDDEN', 'message': 'Cross-tenant access denied'}]}), 403

    data = request.get_json(silent=True) or {}
    new_text = data.get('new_text', '')
    if not new_text:
        return jsonify({'success': False, 'errors': [{'code': 'BAD_REQUEST', 'message': 'new_text required'}]}), 400

    try:
        reply = update_existing_reply(int(reply_id), new_text, user_id=str(current_user.id))
        return jsonify({'success': True, 'data': _reply_to_json(reply)})
    except ValueError as e:
        return jsonify({'success': False, 'errors': [{'code': 'BAD_REQUEST', 'message': str(e)}]}), 400


@response_bp.route('/api/response/metrics', methods=['GET'])
@login_required
def response_metrics():
    """Get response metrics for the current tenant."""
    from app.services.response_service import get_response_metrics

    days = request.args.get('days', 30, type=int)
    business_id = request.args.get('business_id')

    data = get_response_metrics(
        tenant_id=_tenant_id(),
        business_id=business_id,
        days=days,
    )
    return jsonify({'success': True, 'data': data})
