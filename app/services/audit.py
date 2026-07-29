"""Audit logging service — records all state changes."""
import uuid
from flask import g
from app import db
from app.models.entities import AuditLog


def log_audit(action: str, entity_type: str = None, entity_id: str = None,
              before: dict = None, after: dict = None, reason: str = None,
              tenant_id: str = None, actor_type: str = 'user', actor_id: str = None):
    """Create an audit log entry. Never stores secrets."""
    # Redact sensitive fields from before/after
    before = _redact(before) if before else None
    after = _redact(after) if after else None

    entry = AuditLog(
        tenant_id=tenant_id or getattr(g, 'tenant_id', None),
        actor_type=actor_type,
        actor_id=actor_id or (getattr(g, 'current_user_id', None)),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before,
        after_json=after,
        reason=reason,
        trace_id=str(uuid.uuid4()),
    )
    db.session.add(entry)
    # Caller must commit


REDACTED_FIELDS = {'password', 'password_hash', 'secret', 'token', 'access_token',
                   'refresh_token', 'encrypted_access_token_ref',
                   'encrypted_refresh_token_ref', 'api_key', 'credential'}


def _redact(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    return {k: '***REDACTED***' if k.lower() in REDACTED_FIELDS else v
            for k, v in data.items()}
