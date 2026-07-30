"""Event service — NEW_REVIEW / UPDATED_REVIEW Pub/Sub pipeline.

Handles incoming event payloads from Google Pub/Sub (or mock),
resolves tenant and outlet, checks duplication, persists the event,
and delegates review upsert to a caller-provided callback.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Callable

from app import db
from app.models.entities import (
    PubsubEvent,
    Business,
    Outlet,
)

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────

VALID_EVENT_TYPES = frozenset({'NEW_REVIEW', 'UPDATED_REVIEW'})

REQUIRED_FIELDS = frozenset({'event_type', 'message_id', 'publish_time'})

# ─── Event processing ────────────────────────────────────


def process_event(
    event_payload: dict,
    upsert_callback: Callable | None = None,
) -> dict:
    """Process an incoming Pub/Sub event payload.

    Parameters
    ----------
    event_payload : dict
        Must contain: event_type, review_name, location_name, message_id,
        publish_time, google_account_id, tenant_id.
    upsert_callback : callable or None
        If provided, called as:
            upsert_callback(tenant_id, business_id, outlet_id, review_data)
        where review_data is the fetched / adapter-provided review dict.
        Expected to return a dict with at least ``{'review_id': ...}``.

    Returns
    -------
    dict
        ``{'status': 'duplicate'}`` — event already recorded.
        ``{'status': 'created', 'event_id': ..., 'review_id': ...}`` —
        event processed (review_id may be None if no callback).
        ``{'status': 'invalid', 'errors': [...]}`` — validation failed.
    """
    # ── 1. Validate event_type presence ──────────────────
    is_valid, errors = validate_event(event_payload)
    if not is_valid:
        logger.warning('Invalid event payload: %s', errors)
        return {'status': 'invalid', 'errors': errors}

    event_type = event_payload['event_type']

    # ── 2. Duplication check (google_account_id, message_id) ──
    google_account_id = event_payload.get('google_account_id')
    message_id = event_payload['message_id']

    existing = PubsubEvent.query.filter_by(
        google_account_id=google_account_id,
        message_id=message_id,
    ).first()

    if existing is not None:
        logger.info(
            'Duplicate Pub/Sub event (google_account_id=%s, message_id=%s)',
            google_account_id, message_id,
        )
        return {'status': 'duplicate'}

    # ── 3. Parse and persist the event ───────────────────
    publish_time_str = event_payload.get('publish_time')
    publish_time = _parse_datetime(publish_time_str)

    payload_hash = _payload_hash(event_payload)

    event = PubsubEvent(
        tenant_id=event_payload.get('tenant_id'),
        google_account_id=google_account_id,
        event_type=event_type,
        review_name=event_payload.get('review_name'),
        location_name=event_payload.get('location_name'),
        message_id=message_id,
        publish_time=publish_time,
        payload_hash=payload_hash,
        processing_status='received',
    )
    db.session.add(event)
    db.session.flush()  # get event.id without committing yet

    # ── 4. Resolve tenant & location ─────────────────────
    tenant_id = event_payload.get('tenant_id')
    business_id = None
    outlet_id = None
    location_name = event_payload.get('location_name')

    if tenant_id:
        business = Business.query.filter_by(tenant_id=tenant_id).first()
        if business:
            business_id = business.id

        if location_name:
            outlet = Outlet.query.filter_by(
                tenant_id=tenant_id,
                gbp_location_id=location_name,
            ).first()
            if outlet:
                outlet_id = outlet.id

    # ── 5. Process via upsert callback if provided ───────
    review_id = None
    if upsert_callback is not None:
        try:
            result = upsert_callback(
                tenant_id=tenant_id,
                business_id=business_id,
                outlet_id=outlet_id,
                event_payload=event_payload,
            )
            review_id = result.get('review_id') if isinstance(result, dict) else None
        except Exception:
            logger.exception('upsert_callback failed for event %s', event.id)
            event.processing_status = 'upsert_failed'
            db.session.commit()
            return {
                'status': 'upsert_failed',
                'event_id': event.id,
                'review_id': None,
            }

    # ── 6. Mark as processed ─────────────────────────────
    event.processing_status = 'processed'
    event.processed_at = datetime.now(timezone.utc)
    # Update tenant if we now have it resolved
    if tenant_id and not event.tenant_id:
        event.tenant_id = tenant_id

    db.session.commit()

    logger.info(
        'Event %s processed: type=%s, event_id=%s, review_id=%s',
        event.id, event_type, event.id, review_id,
    )

    return {
        'status': 'created',
        'event_id': event.id,
        'review_id': review_id,
    }


def process_mock_event(
    event_type: str,
    tenant_id: str,
    business_id: str,
    outlet_id: str,
    review_data: dict,
) -> dict:
    """Generate and process a mock Pub/Sub event for testing.

    Builds an ``event_payload`` mimicking a real Pub/Sub message and
    delegates to :func:`process_event` with a synthetic upsert callback
    that inserts the provided ``review_data``.

    Parameters
    ----------
    event_type : str
        ``'NEW_REVIEW'`` or ``'UPDATED_REVIEW'``.
    tenant_id : str
    business_id : str
    outlet_id : str
    review_data : dict
        Review fields:
            reviewer_display_name, star_rating, comment,
            create_time, update_time, source_review_name

    Returns
    -------
    dict
        Same structure as :func:`process_event`.
    """
    import uuid as _uuid_mod

    now_iso = _now_iso()

    # Build a realistic payload mimicking a Pub/Sub push message
    mock_message_id = f'mock-{_uuid_mod.uuid4().hex[:12]}'
    mock_review_name = review_data.get(
        'source_review_name',
        f'accounts/{tenant_id}/locations/{outlet_id}/reviews/{_uuid_mod.uuid4().hex[:16]}',
    )
    mock_location_name = f'accounts/{tenant_id}/locations/{outlet_id}'

    event_payload = {
        'event_type': event_type,
        'review_name': mock_review_name,
        'location_name': review_data.get('location_name', mock_location_name),
        'message_id': mock_message_id,
        'publish_time': now_iso,
        'google_account_id': f'accounts/{tenant_id}',
        'tenant_id': tenant_id,
    }

    # Build a closure that inserts the review via review_data
    def _mock_upsert(tenant_id, business_id, outlet_id, event_payload):
        """Synthetic upsert — creates/updates a Review row from review_data."""
        from app.models.entities import Review

        source_review_name = review_data.get('source_review_name', '')

        # Try to find existing review by source_review_name
        existing = Review.query.filter_by(
            tenant_id=tenant_id,
            source=event_type,
            source_review_name=source_review_name,
        ).first()

        now = datetime.now(timezone.utc)

        if existing:
            # UPDATED_REVIEW path
            existing.star_rating = review_data.get('star_rating', existing.star_rating)
            existing.comment = review_data.get('comment', existing.comment)
            existing.update_time = _parse_datetime(review_data.get('update_time')) or now
            existing.review_updated = True
            existing.analysis_reassessment_required = True
            existing.last_seen_at = now
            review_pk = existing.id
        else:
            # NEW_REVIEW path
            create_time = _parse_datetime(review_data.get('create_time')) or now
            update_time = _parse_datetime(review_data.get('update_time')) or now
            comment = review_data.get('comment', '')
            has_text = bool(comment and comment.strip())

            review = Review(
                tenant_id=tenant_id,
                business_id=business_id,
                outlet_id=outlet_id,
                source=event_type,
                source_review_name=source_review_name,
                reviewer_display_name=review_data.get('reviewer_display_name', 'Anonymous'),
                reviewer_is_anonymous=not bool(review_data.get('reviewer_display_name')),
                star_rating=review_data.get('star_rating', 5),
                comment=comment,
                has_text=has_text,
                create_time=create_time,
                update_time=update_time,
                last_seen_at=now,
            )
            db.session.add(review)
            review_pk = review.id

        return {'review_id': review_pk}

    return process_event(
        event_payload=event_payload,
        upsert_callback=_mock_upsert,
    )


# ─── Validation ──────────────────────────────────────────


def validate_event(event_payload: dict) -> tuple[bool, list[str]]:
    """Validate an event payload structure.

    Returns
    -------
    (is_valid, errors_list)
        ``is_valid`` is ``True`` when all checks pass.
        ``errors_list`` contains human-readable error messages.
    """
    errors: list[str] = []

    # Check required fields exist and are non-empty
    for field in REQUIRED_FIELDS:
        value = event_payload.get(field)
        if not value:
            errors.append(f'Missing or empty required field: {field}')

    # Validate event_type against allowed values
    event_type = event_payload.get('event_type')
    if event_type and event_type not in VALID_EVENT_TYPES:
        errors.append(
            f"Invalid event_type '{event_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}"
        )

    return (len(errors) == 0, errors)


# ─── Pub/Sub health check ────────────────────────────────


def pubsub_health_check() -> dict:
    """Check Pub/Sub pipeline readiness."""
    from app.services.feature_flags import is_production_configured
    is_prod = is_production_configured()
    block_reasons = []
    if not is_prod:
        block_reasons.append('GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET belum dikonfigurasi')
    return {
        'pubsub_mode': 'production' if is_prod else 'mock',
        'production_pubsub_connected': is_prod,
        'blocking_reason': block_reasons,
    }


# ─── Production Pub/Sub push handler ───────────────────


def process_pubsub_push(push_body: dict) -> dict:
    """Process a Google Cloud Pub/Sub push notification.

    Google Pub/Sub push format::

        {
            "message": {
                "attributes": {"key": "value"},
                "data": "<base64-encoded-json>",
                "message_id": "...",
                "publish_time": "..."
            },
            "subscription": "projects/.../subscriptions/..."
        }

    The ``data`` field is base64-decoded and parsed as JSON, then
    passed to :func:`process_event` for tenant resolution, duplication
    check, and upsert.

    Returns standard process_event result or ``invalid`` if parsing
    fails.
    """
    import base64

    if not _validate_pubsub_push(push_body):
        logger.warning('Invalid Pub/Sub push envelope: %s', list(push_body.keys())[:3])
        return {'status': 'invalid', 'errors': ['Invalid Pub/Sub push envelope']}

    message = push_body['message']
    subscription = push_body.get('subscription', '')

    # Base64-decode the data field
    raw_data = message.get('data', '')
    try:
        decoded = base64.b64decode(raw_data).decode('utf-8')
        event_payload = json.loads(decoded)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.error('Pub/Sub data decode/parse failed: %s', exc)
        return {'status': 'invalid', 'errors': [f'Cannot decode Pub/Sub data: {exc}']}

    # Override message_id and publish_time from the envelope
    event_payload.setdefault('message_id', message.get('message_id', ''))
    event_payload.setdefault('publish_time', message.get('publish_time', ''))

    # Extract attributes (Google's Pub/Sub may put metadata here)
    attributes = message.get('attributes', {}) or {}
    if attributes.get('google_account_id'):
        event_payload.setdefault('google_account_id', attributes['google_account_id'])
    if attributes.get('tenant_id'):
        event_payload.setdefault('tenant_id', attributes['tenant_id'])

    # If subscription is registered, derive tenant_id from it
    if not event_payload.get('tenant_id'):
        from flask import current_app
        tenant_sub_map = current_app.config.get('PUBSUB_TENANT_MAP', {})
        for tenant_id, sub_pattern in tenant_sub_map.items():
            if sub_pattern and subscription and sub_pattern == subscription:
                event_payload['tenant_id'] = tenant_id
                break

    # Process the event
    result = process_event(event_payload=event_payload, upsert_callback=None)
    # If this is from a real Pub/Sub subscription, trigger sync
    if result.get('status') == 'created' and subscription:
        _trigger_event_sync(event_payload, subscription)

    return result


def _validate_pubsub_push(push_body: dict) -> bool:
    """Basic structural validation of a Pub/Sub push HTTP body."""
    if not isinstance(push_body, dict):
        return False
    msg = push_body.get('message')
    if not isinstance(msg, dict):
        return False
    return bool(msg.get('message_id') or msg.get('data'))


def _trigger_event_sync(event_payload: dict, subscription: str) -> None:
    """Queue an event-driven sync for the affected tenant."""
    tenant_id = event_payload.get('tenant_id')
    if not tenant_id:
        return
    try:
        from app.services.sync_service import trigger_sync_for_tenant
        trigger_sync_for_tenant(tenant_id, source='pubsub_event')
    except Exception:
        logger.exception('Event-driven sync failed for tenant %s', tenant_id)


# ─── Internal helpers ────────────────────────────────────


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string to a timezone-aware datetime.

    Returns ``None`` when the value is ``None`` or unparseable.
    """
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        logger.warning('Cannot parse datetime: %r', value)
        return None


def _payload_hash(event_payload: dict) -> str:
    """Consistent SHA-256 hex digest of the serialised payload."""
    raw = json.dumps(event_payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _now_iso() -> str:
    """Current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
