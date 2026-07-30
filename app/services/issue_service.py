"""Issue tracking & operations service — creation, assignment, escalation, pattern, closure, reports.

Scope per RUN_07:
- Issue creation from review/analysis
- Assignment + responsible role
- Status flow (new → under_review → assigned → in_progress → resolved → closed / reopened)
- Escalation (critical → owner)
- Repeat-pattern parent issue
- Closure evidence (action note, resolver, timestamp)
- SLA/target config
- Weekly/monthly report
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from app import db
from app.models.entities import (
    Review, ReviewAnalysis, ReviewReply,
    Outlet, Issue, IssuePattern, PatternReview,
    User, Business, AuditLog
)

logger = logging.getLogger(__name__)

# ─── SLA DEFAULTS ─────────────────────────────────────────

SLA_TARGETS = {
    'low':      {'acknowledgement_hours': 24, 'assignment_hours': None},
    'medium':   {'acknowledgement_hours': 12, 'assignment_hours': 12},
    'high':     {'acknowledgement_hours': 2,  'assignment_hours': 2},
    'critical': {'acknowledgement_hours': 0,  'assignment_hours': 0},  # immediate
}

# ─── CATEGORY → ROLE MAPPING ─────────────────────────────

CATEGORY_ROLES = {
    'food_quality':        {'primary': 'kepala_dapur',     'support': ['supervisor_operasional', 'kepala_outlet']},
    'service':             {'primary': 'kepala_outlet',    'support': ['supervisor_operasional', 'human_resources']},
    'wait_time':           {'primary': 'supervisor_operasional', 'support': ['kepala_outlet']},
    'wrong_order':         {'primary': 'supervisor_operasional', 'support': ['kepala_outlet']},
    'cleanliness':         {'primary': 'kepala_outlet',    'support': ['supervisor_operasional', 'quality_control']},
    'food_safety':         {'primary': 'owner',            'support': ['quality_control', 'supervisor_operasional', 'kepala_dapur', 'legal_or_compliance']},
    'reputation':          {'primary': 'owner',            'support': ['customer_service', 'marketing', 'legal_or_compliance']},
    'pricing':             {'primary': 'owner',            'support': ['supervisor_operasional']},
    'general_complaint':   {'primary': 'supervisor_operasional', 'support': ['kepala_outlet']},
}

# ─── VALID STATUS TRANSITIONS ────────────────────────────

_VALID_TRANSITIONS = {
    'new':           ['under_review'],
    'under_review':  ['assigned', 'in_progress', 'resolved'],
    'assigned':      ['in_progress', 'resolved'],
    'in_progress':   ['resolved'],
    'resolved':      ['closed', 'reopened'],
    'closed':        ['reopened'],
    'reopened':      ['under_review', 'assigned', 'in_progress'],
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _determine_category(analysis: ReviewAnalysis) -> str:
    """Determine issue category from analysis fields."""
    topics = analysis.topics_json or []
    for t in topics if isinstance(topics, list) else []:
        kw = (t.get('keyword') or t.get('topic') or '').lower()
        if any(s in kw for s in ['diare', 'basi', 'mual', 'sakit', 'kesehatan', 'food safety']):
            return 'food_safety'
        if any(s in kw for s in ['viral', 'media', 'reputasi', 'hukum', 'legal']):
            return 'reputation'
        if any(s in kw for s in ['kebersihan', 'kotor', 'serangga', 'bersih']):
            return 'cleanliness'
        if any(s in kw for s in ['antre', 'lama', 'tunggu', 'wait']):
            return 'wait_time'
        if any(s in kw for s in ['pesan', 'salah', 'order', 'menu']):
            return 'wrong_order'
        if any(s in kw for s in ['pelayanan', 'staff', 'ramah', 'sopan', 'kasar']):
            return 'service'
        if any(s in kw for s in ['harga', 'mahal', 'murah', 'uang']):
            return 'pricing'
        if any(s in kw for s in ['rasa', 'enak', 'hambar', 'asin', 'manis']):
            return 'food_quality'
    if analysis.urgency in ('high', 'critical'):
        return 'general_complaint'
    return 'general_complaint'


def _get_sla_targets(urgency: str) -> dict:
    """Get SLA target hours for a given urgency level."""
    return SLA_TARGETS.get(urgency, {'acknowledgement_hours': 24, 'assignment_hours': None})


# ─── CREATE ISSUE ─────────────────────────────────────────

def create_issue(review_id: str, analysis_id: str = None,
                 actor_user_id: str = None) -> Issue:
    """Create an issue from a review + analysis. Returns the Issue."""
    review = db.session.get(Review, review_id)
    if not review:
        raise ValueError(f'Review not found: {review_id}')

    analysis = None
    if analysis_id:
        analysis = db.session.get(ReviewAnalysis, analysis_id)
    else:
        analysis = ReviewAnalysis.query.filter_by(review_pk=review_id)\
            .order_by(ReviewAnalysis.created_at.desc()).first()

    # Determine category & roles
    category = 'general_complaint'
    primary_role = 'supervisor_operasional'
    sup_roles = ['kepala_outlet']
    if analysis:
        category = _determine_category(analysis)
        role_map = CATEGORY_ROLES.get(category, CATEGORY_ROLES['general_complaint'])
        primary_role = role_map['primary']
        sup_roles = role_map['support']

    urgency = analysis.urgency if analysis else 'medium'
    sla = _get_sla_targets(urgency)
    due_hours = sla.get('assignment_hours') or sla.get('acknowledgement_hours') or 24
    due_at = _now() + timedelta(hours=due_hours) if sla.get('assignment_hours') is not None else None

    # Build source facts
    source_facts = {
        'review_star_rating': review.star_rating,
        'review_comment_preview': (review.comment or '')[:200],
        'review_source': review.source,
        'analysis_sentiment': analysis.sentiment if analysis else None,
        'analysis_urgency': urgency,
        'analysis_reputation_risk': analysis.reputation_risk if analysis else None,
    }

    issue = Issue(
        tenant_id=review.tenant_id,
        business_id=review.business_id,
        outlet_id=review.outlet_id,
        review_id=review.id,
        title=f'{category.replace("_", " ").title()} — Review {review.star_rating}★',
        issue_summary=analysis.issue_summary if analysis and analysis.issue_summary else (review.comment or '')[:500],
        category=category,
        urgency=urgency,
        reputation_risk=analysis.reputation_risk if analysis else 'minimal',
        source_facts=source_facts,
        ai_assessment={
            'analysis_id': analysis.id if analysis else None,
            'sentiment': analysis.sentiment if analysis else None,
            'topics': analysis.topics_json if analysis else [],
            'repeat_pattern_candidate': analysis.repeat_pattern_candidate if analysis else False,
            'responsible_role': analysis.responsible_role if analysis else primary_role,
        } if analysis else None,
        primary_owner_role=primary_role,
        supporting_roles=sup_roles,
        status='new',
        due_at=due_at,
        action_checklist=[],
        internal_notes=[],
        evidence_attachments=[],
    )
    db.session.add(issue)
    db.session.flush()

    _log_action('issue_created', entity_id=issue.id,
                after={'status': 'new', 'category': category, 'urgency': urgency},
                actor_id=actor_user_id, tenant_id=review.tenant_id)

    return issue


def get_issue(issue_id: str) -> Issue:
    """Get issue by ID."""
    issue = db.session.get(Issue, issue_id)
    if not issue:
        raise ValueError(f'Issue not found: {issue_id}')
    return issue


def list_issues(tenant_id: str = None, status: str = None,
                urgency: str = None, outlet_id: str = None,
                limit: int = 50, offset: int = 0) -> list:
    """List issues with optional filters."""
    q = Issue.query
    if tenant_id:
        q = q.filter_by(tenant_id=tenant_id)
    if status:
        q = q.filter_by(status=status)
    if urgency:
        q = q.filter_by(urgency=urgency)
    if outlet_id:
        q = q.filter_by(outlet_id=outlet_id)
    q = q.order_by(Issue.created_at.desc()).offset(offset).limit(limit)
    return q.all()


def update_issue_status(issue_id: str, new_status: str,
                        actor_user_id: str = None,
                        reason: str = None) -> Issue:
    """Update issue status with valid transition check."""
    issue = get_issue(issue_id)
    old_status = issue.status

    if old_status not in _VALID_TRANSITIONS:
        raise ValueError(f'Invalid current status: {old_status}')
    if new_status not in _VALID_TRANSITIONS[old_status]:
        raise ValueError(
            f'Invalid transition: {old_status} → {new_status}. '
            f'Allowed: {_VALID_TRANSITIONS[old_status]}'
        )

    before = {'status': old_status}
    issue.status = new_status
    issue.updated_at = _now()

    if new_status == 'resolved':
        issue.resolved_at = _now()

    _log_action('issue_status_changed', entity_id=issue.id,
                before=before, after={'status': new_status},
                actor_id=actor_user_id, tenant_id=issue.tenant_id,
                reason=reason)

    return issue


# ─── ASSIGN ───────────────────────────────────────────────

def assign_issue(issue_id: str, user_id: str,
                 actor_user_id: str = None) -> Issue:
    """Assign issue to a user."""
    issue = get_issue(issue_id)
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError(f'User not found: {user_id}')

    before = {'assigned_user_id': issue.assigned_user_id}
    issue.assigned_user_id = user_id
    issue.updated_at = _now()

    # Auto-advance to assigned if still in new/under_review
    if issue.status in ('new', 'under_review'):
        issue.status = 'assigned'

    _log_action('issue_assigned', entity_id=issue.id,
                before=before, after={'assigned_user_id': user_id},
                actor_id=actor_user_id, tenant_id=issue.tenant_id)

    return issue


# ─── CLOSE ISSUE ──────────────────────────────────────────

def close_issue(issue_id: str, actor_user_id: str,
                resolution_summary: str = None,
                evidence: list = None,
                action_notes: list = None) -> Issue:
    """Close issue with required evidence.

    Requirements:
    - action note / resolution summary
    - resolver identity (actor_user_id)
    - timestamp
    - evidence attachments (optional but tracked)
    """
    issue = get_issue(issue_id)

    # Must be in resolved status first (or closed for reopen flow)
    if issue.status not in ('resolved',):
        raise ValueError(f'Cannot close issue in status {issue.status}. Must be resolved first.')

    if not resolution_summary and not action_notes:
        raise ValueError('Closure requires resolution_summary or action_notes.')

    before = {'status': issue.status, 'resolution_summary': issue.resolution_summary}
    issue.status = 'closed'
    issue.closed_by = actor_user_id
    issue.closed_at = _now()
    issue.resolved_at = issue.resolved_at or _now()
    if resolution_summary:
        issue.resolution_summary = resolution_summary
    if evidence:
        existing = issue.evidence_attachments or []
        issue.evidence_attachments = existing + evidence
    if action_notes:
        existing = issue.action_checklist or []
        issue.action_checklist = existing + [{'note': n, 'timestamp': _now().isoformat(), 'actor': actor_user_id} for n in action_notes]

    issue.updated_at = _now()

    _log_action('issue_closed', entity_id=issue.id,
                before=before,
                after={'status': 'closed', 'closed_by': actor_user_id},
                actor_id=actor_user_id, tenant_id=issue.tenant_id)

    return issue


# ─── REOPEN ISSUE ─────────────────────────────────────────

def reopen_issue(issue_id: str, actor_user_id: str,
                 reason: str = None) -> Issue:
    """Reopen a closed/resolved issue."""
    issue = get_issue(issue_id)
    if issue.status not in ('closed', 'resolved'):
        raise ValueError(f'Cannot reopen issue in status {issue.status}.')

    before = {'status': issue.status}
    issue.status = 'reopened'
    issue.updated_at = _now()
    # Clear closure fields for re-entry
    issue.closed_by = None
    issue.closed_at = None

    _log_action('issue_reopened', entity_id=issue.id,
                before=before, after={'status': 'reopened'},
                actor_id=actor_user_id, tenant_id=issue.tenant_id,
                reason=reason)

    return issue


# ─── ESCALATION ───────────────────────────────────────────

def escalate_issue(issue_id: str, actor_user_id: str = None,
                   reason: str = None) -> Issue:
    """Escalate issue to owner/primary role."""
    issue = get_issue(issue_id)
    before = {'status': issue.status, 'assigned_user_id': issue.assigned_user_id}

    # Find owner user — join through Business for tenant
    owner = User.query.join(Business).filter(
        Business.tenant_id == issue.tenant_id,
        User.role == 'owner',
        User.is_active == True
    ).first()

    if owner:
        issue.assigned_user_id = owner.id
    issue.primary_owner_role = 'owner'
    if issue.status in ('new', 'under_review', 'assigned'):
        issue.status = 'in_progress'
    issue.updated_at = _now()

    _log_action('issue_escalated', entity_id=issue.id,
                before=before,
                after={'status': issue.status, 'assigned_user_id': issue.assigned_user_id},
                actor_id=actor_user_id, tenant_id=issue.tenant_id,
                reason=reason or 'Escalation triggered')

    return issue


# ─── PATTERN DETECTION ────────────────────────────────────

def create_or_update_pattern(pattern_key: str, tenant_id: str, business_id: str,
                             title: str = None, parent_issue_id: str = None,
                             outlet_specific: bool = False) -> IssuePattern:
    """Find or create a pattern by key. Updates if exists."""
    pattern = IssuePattern.query.filter_by(
        tenant_id=tenant_id, pattern_key=pattern_key
    ).first()
    if pattern:
        pattern.title = title or pattern.title
        pattern.parent_issue_id = parent_issue_id or pattern.parent_issue_id
        pattern.outlet_specific = outlet_specific
        pattern.updated_at = _now()
        return pattern

    pattern = IssuePattern(
        tenant_id=tenant_id,
        business_id=business_id,
        parent_issue_id=parent_issue_id,
        pattern_key=pattern_key,
        title=title or pattern_key.replace('_', ' ').title(),
        outlet_specific=outlet_specific,
    )
    db.session.add(pattern)
    db.session.flush()
    return pattern


def link_review_to_pattern(pattern_id: str, review_id: str,
                           issue_id: str = None) -> PatternReview:
    """Link a supporting review to a pattern (idempotent)."""
    existing = PatternReview.query.filter_by(
        pattern_id=pattern_id, review_id=review_id
    ).first()
    if existing:
        return existing

    link = PatternReview(
        pattern_id=pattern_id,
        review_id=review_id,
        issue_id=issue_id,
    )
    db.session.add(link)
    db.session.flush()
    return link


def get_pattern_with_reviews(pattern_id: str) -> dict:
    """Get pattern details with linked reviews."""
    pattern = db.session.get(IssuePattern, pattern_id)
    if not pattern:
        raise ValueError(f'Pattern not found: {pattern_id}')

    reviews = PatternReview.query.filter_by(pattern_id=pattern_id).all()
    return {
        'pattern': pattern,
        'supporting_reviews': [{
            'id': pr.id,
            'review_id': pr.review_id,
            'issue_id': pr.issue_id,
            'created_at': pr.created_at.isoformat() if pr.created_at else None,
        } for pr in reviews],
        'review_count': len(reviews),
    }


# ─── ISSUE REPORT ─────────────────────────────────────────

def _issue_to_dict(issue: Issue) -> dict:
    return {
        'id': issue.id,
        'tenant_id': issue.tenant_id,
        'outlet_id': issue.outlet_id,
        'review_id': issue.review_id,
        'title': issue.title,
        'category': issue.category,
        'urgency': issue.urgency,
        'status': issue.status,
        'primary_owner_role': issue.primary_owner_role,
        'assigned_user_id': issue.assigned_user_id,
        'due_at': issue.due_at.isoformat() if issue.due_at else None,
        'created_at': issue.created_at.isoformat() if issue.created_at else None,
        'resolved_at': issue.resolved_at.isoformat() if issue.resolved_at else None,
        'closed_at': issue.closed_at.isoformat() if issue.closed_at else None,
        'closed_by': issue.closed_by,
        'resolution_summary': issue.resolution_summary,
        'action_checklist': issue.action_checklist or [],
    }


def get_weekly_report(tenant_id: str, business_id: str = None) -> dict:
    """Generate weekly management summary."""
    now = _now().replace(tzinfo=None)  # naive for SQLite compatibility
    week_ago = now - timedelta(days=7)

    q = Issue.query.filter_by(tenant_id=tenant_id)
    if business_id:
        q = q.filter_by(business_id=business_id)

    all_issues = q.all()
    new_this_week = [i for i in all_issues if i.created_at and i.created_at >= week_ago]
    resolved_this_week = [i for i in all_issues if i.resolved_at and i.resolved_at >= week_ago]
    closed_this_week = [i for i in all_issues if i.closed_at and i.closed_at >= week_ago]
    reopened_this_week = [i for i in all_issues if i.status == 'reopened' and i.updated_at and i.updated_at >= week_ago]
    overdue = [i for i in all_issues if i.due_at and i.due_at < now and i.status not in ('closed', 'resolved')]

    open_issues = [i for i in all_issues if i.status not in ('closed', 'resolved')]
    critical_open = [i for i in open_issues if i.urgency == 'critical']

    # Pattern detection
    patterns = IssuePattern.query.filter_by(tenant_id=tenant_id).all()
    pattern_summary = []
    for p in patterns:
        review_count = PatternReview.query.filter_by(pattern_id=p.id).count()
        pattern_summary.append({
            'pattern_key': p.pattern_key,
            'title': p.title,
            'review_count': review_count,
            'trend': p.trend,
        })

    return {
        'period': {'start': week_ago.isoformat(), 'end': now.isoformat()},
        'total_issues': len(all_issues),
        'new_this_week': len(new_this_week),
        'resolved_this_week': len(resolved_this_week),
        'closed_this_week': len(closed_this_week),
        'reopened_this_week': len(reopened_this_week),
        'overdue': len(overdue),
        'open_issues': len(open_issues),
        'critical_open': len(critical_open),
        'patterns': pattern_summary,
        'generated_at': now.isoformat(),
    }


def get_monthly_report(tenant_id: str, business_id: str = None, month_offset: int = 0) -> dict:
    """Generate monthly management summary."""
    now = _now().replace(tzinfo=None)  # naive for SQLite
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_offset > 0:
        month_start = (month_start.replace(month=1) + timedelta(days=366))\
            .replace(day=1) if month_start.month + month_offset > 12 else \
            month_start
    else:
        month_start = month_start - timedelta(days=month_start.day - 1)

    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_end = next_month - timedelta(seconds=1)

    q = Issue.query.filter_by(tenant_id=tenant_id)
    if business_id:
        q = q.filter_by(business_id=business_id)

    all_issues = q.all()
    month_issues = [i for i in all_issues if i.created_at and month_start <= i.created_at <= month_end]
    resolved = [i for i in all_issues if i.resolved_at and month_start <= i.resolved_at <= month_end]
    closed = [i for i in all_issues if i.closed_at and month_start <= i.closed_at <= month_end]

    # Category breakdown
    categories = {}
    for i in month_issues:
        cat = i.category or 'other'
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    return {
        'period': {'start': month_start.isoformat(), 'end': month_end.isoformat()},
        'total_issues': len(all_issues),
        'issues_this_month': len(month_issues),
        'resolved_this_month': len(resolved),
        'closed_this_month': len(closed),
        'categories': categories,
        'generated_at': now.isoformat(),
    }


# ─── INTERNAL NOTES ──────────────────────────────────────

def add_internal_note(issue_id: str, note: str, actor_user_id: str) -> Issue:
    """Add an internal note to an issue."""
    issue = get_issue(issue_id)
    existing = issue.internal_notes or []
    existing.append({
        'note': note,
        'timestamp': _now().isoformat(),
        'actor': actor_user_id,
    })
    issue.internal_notes = existing
    issue.updated_at = _now()
    return issue


# ─── ISSUE TO DICT ───────────────────────────────────────

def issue_to_json(issue: Issue) -> dict:
    """Serialize issue to JSON-safe dict."""
    return {
        'id': issue.id,
        'tenant_id': issue.tenant_id,
        'business_id': issue.business_id,
        'outlet_id': issue.outlet_id,
        'review_id': issue.review_id,
        'pattern_id': issue.pattern_id,
        'title': issue.title,
        'issue_summary': issue.issue_summary,
        'category': issue.category,
        'urgency': issue.urgency,
        'reputation_risk': issue.reputation_risk,
        'source_facts': issue.source_facts,
        'ai_assessment': issue.ai_assessment,
        'primary_owner_role': issue.primary_owner_role,
        'assigned_user_id': issue.assigned_user_id,
        'supporting_roles': issue.supporting_roles,
        'status': issue.status,
        'due_at': issue.due_at.isoformat() if issue.due_at else None,
        'action_checklist': issue.action_checklist,
        'internal_notes': issue.internal_notes,
        'evidence_attachments': issue.evidence_attachments,
        'resolution_summary': issue.resolution_summary,
        'closed_by': issue.closed_by,
        'closed_at': issue.closed_at.isoformat() if issue.closed_at else None,
        'created_at': issue.created_at.isoformat() if issue.created_at else None,
        'updated_at': issue.updated_at.isoformat() if issue.updated_at else None,
        'resolved_at': issue.resolved_at.isoformat() if issue.resolved_at else None,
    }


# ─── AUDIT LOG HELPER ────────────────────────────────────

def _log_action(action: str, entity_id: str = None,
                before: dict = None, after: dict = None,
                actor_id: str = None, tenant_id: str = None,
                reason: str = None):
    """Record action in audit log."""
    try:
        log = AuditLog(
            tenant_id=tenant_id,
            actor_type='user' if actor_id else 'system',
            actor_id=actor_id or 'system',
            action=action,
            entity_type='issue',
            entity_id=entity_id,
            before_json=before,
            after_json=after,
            reason=reason,
        )
        db.session.add(log)
    except Exception as e:
        logger.warning(f'Failed to create audit log: {e}')
