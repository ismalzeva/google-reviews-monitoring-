"""Review response service — routing, draft, approval, publication, moderation.

Routes:
  auto       — Safe (5-star, positive, no complaints, high confidence)
  approval   — Human approval needed (mixed, negative, 1-3 star, low confidence)
  escalation — Critical (illness, legal, severe risk)

auto-reply is OFF by default. Must be explicitly enabled per business/tenant.
All publications are mock-only until Gate F is complete.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app import db
from app.models.entities import (
    Review, ReviewAnalysis, ReviewReply, Approval,
    Outlet, Issue, AuditLog
)

logger = logging.getLogger(__name__)

# ─── CONFIG ─────────────────────────────────────────────────

AUTO_REPLY_ENABLED_DEFAULT = False  # OFF by default (Gate F rule)

# ─── BRAND TONE TEMPLATES — BUBUR FAY ──────────────────────

_TEMPLATES = {
    'positive': (
        "Terima kasih sudah menikmati Bubur Fay. "
        "Senang sekali mengetahui bubur dan pelayanan kami berkesan baik. "
        "Sampai bertemu kembali."
    ),
    'mixed': (
        "Terima kasih atas masukannya. "
        "Kami senang buburnya disukai dan mohon maaf karena "
        "{complaint} belum sesuai harapan. "
        "Masukan ini akan kami sampaikan kepada tim outlet untuk diperiksa dan diperbaiki."
    ),
    'negative': (
        "Terima kasih sudah menyampaikan pengalaman Anda. "
        "Kami mohon maaf karena {complaint} belum sesuai harapan. "
        "Hal ini perlu kami periksa bersama tim outlet agar tidak terulang. "
        "Terima kasih atas masukannya."
    ),
    'critical_holding': (
        "Terima kasih telah menyampaikan hal ini. "
        "Kami prihatin dengan pengalaman yang Anda ceritakan dan "
        "sedang meminta tim terkait melakukan pemeriksaan segera. "
        "Agar detailnya dapat kami telusuri dengan tepat, "
        "mohon hubungi kanal resmi Bubur Fay yang tercantum pada profil bisnis."
    ),
}

# ─── DRAFT GENERATION ───────────────────────────────────────


def generate_draft_text(review: Review, analysis: ReviewAnalysis) -> str:
    """Generate draft reply text based on analysis and brand tone."""
    sentiment = analysis.sentiment or 'neutral'
    urgency = analysis.urgency or 'low'
    risk = analysis.reputation_risk or 'minimal'

    # Critical holding response
    if urgency == 'critical' or risk == 'severe':
        return _TEMPLATES['critical_holding']

    # Negative
    if sentiment == 'negative':
        topics = analysis.topics_json or []
        complaint = ''
        if isinstance(topics, list) and len(topics) > 0:
            complaint = topics[0].get('keyword', '') if isinstance(topics[0], dict) else str(topics[0])
        return _TEMPLATES['negative'].format(complaint=complaint)

    # Mixed
    if sentiment == 'mixed':
        topics = analysis.topics_json or []
        complaint = ''
        if isinstance(topics, list) and len(topics) > 0:
            # Find a negative topic
            for t in topics:
                if isinstance(t, dict) and t.get('polarity') == 'negative':
                    complaint = t.get('keyword', '')
                    break
        return _TEMPLATES['mixed'].format(complaint=complaint)

    # Positive / neutral
    return _TEMPLATES['positive']


# ─── ROUTING LOGIC ────────────────────────────────────────────


def _is_auto_reply_eligible(review: Review, analysis: ReviewAnalysis,
                            outlet: Outlet) -> tuple[bool, str]:
    """Check if a review qualifies for auto-reply (approval not needed).

    Gate F rules:
    - auto-reply OFF by default (outlet._auto_reply_enabled)
    - rating 1–2: never auto, always human
    - sentiment negative/mixed: always human
    - urgency high/critical: always human
    - reputation_risk elevated/severe: always human
    - confidence < 0.7: always human
    - has_issue: always human
    """
    # Auto-reply OFF by default (Gate F rule F11)
    if not getattr(outlet, '_auto_reply_enabled', False):
        return False, 'auto_reply_disabled'

    # Rating 1-3: never auto (rating 3 needs human judgement)
    if review.star_rating <= 3:
        return False, 'low_rating'

    # Negative/mixed sentiment: always human
    sentiment = (analysis.sentiment or 'neutral').lower()
    if sentiment in ('negative', 'mixed'):
        return False, 'negative_or_mixed_sentiment'

    # Urgency high+: always human
    urgency = (analysis.urgency or 'low').lower()
    if urgency in ('high', 'critical'):
        return False, 'elevated_urgency'

    # Reputation risk
    risk = (analysis.reputation_risk or 'minimal').lower()
    if risk in ('elevated', 'severe'):
        return False, 'elevated_risk'

    # Low confidence
    confidence = analysis.confidence_json or {}
    if isinstance(confidence, dict):
        sent_conf = confidence.get('sentiment', 1.0)
        if isinstance(sent_conf, (int, float)) and sent_conf < 0.7:
            return False, 'low_confidence'

    # Has issue
    if analysis.issue_summary:
        return False, 'has_issue'

    # Has negative topics
    topics = analysis.topics_json or []
    if isinstance(topics, list):
        for t in topics:
            if isinstance(t, dict) and t.get('polarity') == 'negative':
                return False, 'negative_topic'

    return True, 'ok'


def _needs_approval(review: Review, analysis: ReviewAnalysis,
                    outlet: Outlet) -> bool:
    """Check if review needs human approval."""
    eligible, reason = _is_auto_reply_eligible(review, analysis, outlet)
    if eligible:
        return False  # Can auto-reply
    return True


def _is_critical(review: Review, analysis: ReviewAnalysis) -> bool:
    """Check if review is critical (must escalate, bypass approval)."""
    urgency = (analysis.urgency or 'low').lower()
    risk = (analysis.reputation_risk or 'minimal').lower()
    return urgency == 'critical' or risk == 'severe'


def determine_route(review: Review, analysis: ReviewAnalysis,
                    outlet: Outlet) -> str:
    """Determine response route for a review.

    Returns: 'auto', 'approval', or 'escalation'
    """
    if _is_critical(review, analysis):
        return 'escalation'

    if _is_auto_reply_eligible(review, analysis, outlet)[0]:
        return 'auto'

    return 'approval'


# ─── CHECK EXISTING REPLY ────────────────────────────────────


def _check_existing_reply(review_id: str) -> tuple[bool, ReviewReply | None]:
    """Check if a reply already exists for this review."""
    existing = ReviewReply.query.filter_by(review_pk=review_id).first()
    if existing:
        return True, existing
    return False, None


# ─── AUDIT HELPER ────────────────────────────────────────────


def _create_audit_log(tenant_id: str | None, action: str,
                      entity_type: str, entity_id: str,
                      user_id: str | None = None,
                      reason: str | None = None) -> AuditLog:
    """Create a standardized audit log entry.

    AuditLog model fields: id, tenant_id, actor_type, actor_id,
    action, entity_type, entity_id, before_json, after_json,
    reason, trace_id, created_at
    """
    audit = AuditLog(
        tenant_id=tenant_id,
        actor_type='user' if user_id else 'system',
        actor_id=user_id if user_id else 'system',
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(audit)
    return audit


# ─── DRAFT CREATION ──────────────────────────────────────────


def create_reply_draft(review_id: str, analysis: ReviewAnalysis,
                       outlet: Outlet, user_id: str) -> ReviewReply:
    """Create a reply draft. Determines route, generates text, saves."""
    review = db.session.get(Review, review_id)
    if not review:
        raise ValueError(f"Review {review_id} not found")

    # Check existing
    has_published, existing = _check_existing_reply(review_id)
    if has_published:
        # Idempotent — return existing published reply
        return existing

    # Determine route with DB check for existing
    route = determine_route(review, analysis, outlet)

    # If eligible for auto but has existing draft, switch to approval
    if existing and route == 'auto':
        route = 'approval'

    # Generate draft text
    draft_text = generate_draft_text(review, analysis)

    # Create reply
    reply = ReviewReply(
        review_pk=review_id,
        draft_version=1,
        draft_text=draft_text,
        route=route,
        approval_status='pending',
        approved_text=None,
        publication_status='draft',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.session.add(reply)

    # Create audit log
    _create_audit_log(
        tenant_id=review.tenant_id,
        action='reply_draft_created',
        entity_type='review_reply',
        entity_id=str(review_id),
        user_id=user_id,
        reason=json.dumps({'route': route, 'outlet_id': outlet.id}),
    )
    db.session.commit()

    return reply


# ─── APPROVAL / REJECT / PUBLISH ──────────────────────────────


def approve_reply(reply_id: str, user_id: str,
                  edited_text: str | None = None,
                  note: str | None = None) -> ReviewReply:
    """Approve a reply draft (with optional edits)."""
    reply = db.session.get(ReviewReply, reply_id)
    if not reply:
        raise ValueError(f"Reply {reply_id} not found")

    reply.approval_status = 'approved'
    if edited_text:
        reply.approved_text = edited_text
        reply.draft_text = edited_text
    else:
        reply.approved_text = reply.draft_text
    reply.updated_at = datetime.now(timezone.utc)

    # Get tenant_id from the review
    review = db.session.get(Review, reply.review_pk)
    tenant_id = review.tenant_id if review else None

    # Record approval
    approval = Approval(
        tenant_id=tenant_id,
        review_reply_id=reply_id,
        decision='approved',
        actor_user_id=user_id,
        edited_text=edited_text,
        note=note,
        decided_at=datetime.now(timezone.utc),
    )
    db.session.add(approval)

    _create_audit_log(
        tenant_id=tenant_id,
        action='reply_approved',
        entity_type='review_reply',
        entity_id=str(reply_id),
        user_id=user_id,
        reason=json.dumps({'edited': edited_text is not None, 'note': note}),
    )
    db.session.commit()
    return reply


def reject_reply(reply_id: str, user_id: str,
                 note: str | None = None) -> ReviewReply:
    """Reject a reply draft."""
    reply = db.session.get(ReviewReply, reply_id)
    if not reply:
        raise ValueError(f"Reply {reply_id} not found")

    reply.approval_status = 'rejected'
    reply.updated_at = datetime.now(timezone.utc)

    review = db.session.get(Review, reply.review_pk)
    tenant_id = review.tenant_id if review else None

    approval = Approval(
        tenant_id=tenant_id,
        review_reply_id=reply_id,
        decision='rejected',
        actor_user_id=user_id,
        note=note,
        decided_at=datetime.now(timezone.utc),
    )
    db.session.add(approval)

    _create_audit_log(
        tenant_id=tenant_id,
        action='reply_rejected',
        entity_type='review_reply',
        entity_id=str(reply_id),
        user_id=user_id,
        reason=json.dumps({'note': note}),
    )
    db.session.commit()
    return reply


def publish_reply(reply_id: str, user_id: str) -> ReviewReply:
    """Publish a reply (mock — no Google API call)."""
    reply = db.session.get(ReviewReply, reply_id)
    if not reply:
        raise ValueError(f"Reply {reply_id} not found")

    # Idempotent — if already published, return as-is
    if reply.publication_status == 'published':
        return reply

    # Must be approved
    if reply.approval_status != 'approved':
        raise ValueError(
            f"Cannot publish reply {reply_id}: status={reply.approval_status}"
        )

    # Mock publication
    reply.publication_status = 'published'
    reply.approved_text = reply.approved_text or reply.draft_text
    reply.published_by = user_id
    reply.published_at = datetime.now(timezone.utc)
    reply.google_reply_update_time = datetime.now(timezone.utc)
    reply.review_reply_state = 'published'
    reply.updated_at = datetime.now(timezone.utc)

    review = db.session.get(Review, reply.review_pk)
    tenant_id = review.tenant_id if review else None

    _create_audit_log(
        tenant_id=tenant_id,
        action='reply_published',
        entity_type='review_reply',
        entity_id=str(reply_id),
        user_id=user_id,
        reason=json.dumps({'mock': True, 'text_preview': (reply.approved_text or '')[:100]}),
    )
    db.session.commit()
    return reply


def update_existing_reply(reply_id: str, new_text: str,
                          user_id: str) -> ReviewReply:
    """Update a published or draft reply with new text.

    Increments draft_version. Resets approval_status to pending.
    """
    reply = db.session.get(ReviewReply, reply_id)
    if not reply:
        raise ValueError(f"Reply {reply_id} not found")

    reply.draft_version = (reply.draft_version or 1) + 1
    reply.draft_text = new_text
    reply.approved_text = None
    reply.approval_status = 'pending'
    reply.publication_status = 'draft'
    reply.updated_at = datetime.now(timezone.utc)

    review = db.session.get(Review, reply.review_pk)
    tenant_id = review.tenant_id if review else None

    _create_audit_log(
        tenant_id=tenant_id,
        action='reply_updated',
        entity_type='review_reply',
        entity_id=str(reply_id),
        user_id=user_id,
        reason=json.dumps({'version': reply.draft_version, 'text_preview': new_text[:100]}),
    )
    db.session.commit()
    return reply


def update_moderation(reply_id: str, moderation_state: str,
                      policy_violation: bool = False) -> ReviewReply:
    """Update moderation status from Google.

    States: 'published', 'rejected', 'pending_review'.
    """
    reply = db.session.get(ReviewReply, reply_id)
    if not reply:
        raise ValueError(f"Reply {reply_id} not found")

    reply.review_reply_state = moderation_state
    reply.policy_violation = str(policy_violation) if policy_violation else None
    reply.updated_at = datetime.now(timezone.utc)

    # If rejected by moderation, reset to draft for correction
    if moderation_state == 'rejected':
        reply.publication_status = 'draft'
        reply.approval_status = 'pending'

    review = db.session.get(Review, reply.review_pk)
    tenant_id = review.tenant_id if review else None

    _create_audit_log(
        tenant_id=tenant_id,
        action='reply_moderation',
        entity_type='review_reply',
        entity_id=str(reply_id),
        reason=json.dumps({'state': moderation_state, 'policy_violation': policy_violation}),
    )
    db.session.commit()
    return reply


# ─── ESCALATION ──────────────────────────────────────────────


def create_escalation(review_id: str, analysis: ReviewAnalysis,
                      user_id: str) -> tuple[Issue, ReviewReply]:
    """Create a critical escalation: Issue + holding draft reply."""
    review = db.session.get(Review, review_id)
    if not review:
        raise ValueError(f"Review {review_id} not found")

    # Create issue
    issue = Issue(
        tenant_id=review.tenant_id,
        business_id=review.business_id,
        review_id=review_id,
        category='critical',
        title=analysis.issue_summary or f"Critical review #{review_id}",
        issue_summary=f"Auto-escalated from review {review_id}. Sentiment: {analysis.sentiment}. Urgency: {analysis.urgency}.",
        urgency='high',
        status='new',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.session.add(issue)
    db.session.flush()

    # Create holding reply
    draft_text = generate_draft_text(review, analysis)
    reply = ReviewReply(
        review_pk=review_id,
        draft_version=1,
        draft_text=draft_text,
        route='escalation',
        approval_status='escalated',
        approved_text=None,
        publication_status='draft',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.session.add(reply)

    _create_audit_log(
        tenant_id=review.tenant_id,
        action='escalation_created',
        entity_type='review_reply',
        entity_id=str(review_id),
        user_id=user_id,
        reason=json.dumps({'issue_id': issue.id, 'category': 'critical'}),
    )
    db.session.commit()

    return issue, reply


# ─── METRICS ─────────────────────────────────────────────────


def get_response_metrics(tenant_id: str, business_id: str | None = None,
                         days: int = 30) -> dict:
    """Get response metrics."""
    from sqlalchemy import func as sa_func

    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = ReviewReply.query.join(
        Review, ReviewReply.review_pk == Review.id
    ).filter(
        Review.tenant_id == tenant_id,
        Review.created_at >= cutoff
    )

    if business_id:
        query = query.filter(Review.business_id == business_id)

    replies = query.all()

    total = len(replies)
    published = sum(1 for r in replies if r.publication_status == 'published')
    pending = sum(1 for r in replies
                  if r.approval_status == 'pending'
                  and r.publication_status != 'published')
    approved = sum(1 for r in replies if r.approval_status == 'approved')
    rejected = sum(
        1 for a in Approval.query.filter(
            Approval.decision == 'rejected',
            Approval.review_reply_id.in_([r.id for r in replies])
        ).all()
    ) if replies else 0
    escalated = sum(1 for r in replies if r.route == 'escalation')
    auto = sum(1 for r in replies if r.route == 'auto')

    routes = {'auto': auto, 'approval': len(replies) - auto - escalated, 'escalation': escalated}
    approval_statuses = {
        'pending': pending,
        'approved': approved,
        'rejected': rejected,
        'escalated': escalated,
    }

    # Calculate average response time
    response_times = []
    for r in replies:
        if r.published_at:
            review = db.session.get(Review, r.review_pk)
            if review and review.created_at:
                try:
                    rt = (r.published_at - review.created_at).total_seconds() / 3600
                    if 0 < rt < 720:
                        response_times.append(rt)
                except (TypeError, ValueError):
                    pass

    avg_response_hours = round(sum(response_times) / len(response_times), 1) if response_times else 0

    return {
        'total_replies': total,
        'published': published,
        'pending_approval': pending,
        'approved': approved,
        'rejected': rejected,
        'escalated': escalated,
        'routes': routes,
        'approval_statuses': approval_statuses,
        'avg_response_hours': avg_response_hours,
        'period_days': days,
        'review_count': len(set(r.review_pk for r in replies)),
        'response_rate': round(published / len(set(r.review_pk for r in replies)) * 100, 1)
        if set(r.review_pk for r in replies) else 0,
    }
