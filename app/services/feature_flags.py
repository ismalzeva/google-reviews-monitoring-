"""Feature flags for pilot/production mode control.

Rules enforced by this module:
- auto-reply is permanently OFF in pilot
- all publishes require human approval in pilot
- only 1 outlet active per tenant in pilot unless overridden
- Harjamukti is permanently excluded
"""
import os
from flask import current_app


def is_production_configured() -> bool:
    """True if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set."""
    cid = current_app.config.get('GOOGLE_CLIENT_ID', '')
    csec = current_app.config.get('GOOGLE_CLIENT_SECRET', '')
    return bool(cid and csec)


def adapter_mode() -> str:
    """Returns 'production' if credentials exist, else 'mock'."""
    return 'production' if is_production_configured() else 'mock'


def is_pilot_mode() -> bool:
    """Pilot mode limits active outlets and locks auto-reply."""
    return os.environ.get('GRM_PILOT_MODE', 'true').lower() == 'true'


def pilot_max_outlets() -> int:
    """Max outlets per tenant in pilot mode. Default 1."""
    raw = os.environ.get('GRM_PILOT_MAX_OUTLETS', '1')
    try:
        return max(1, int(raw))
    except (ValueError, TypeError):
        return 1


def pilot_outlet_whitelist() -> list:
    """Outlet IDs or names whitelisted in pilot. Empty = auto-pick first active."""
    raw = os.environ.get('GRM_PILOT_OUTLET_WHITELIST', '')
    if not raw:
        return []
    return [x.strip() for x in raw.split(',')]


def is_auto_reply_enabled() -> bool:
    """Auto-reply is permanently OFF in pilot. Only for future use."""
    if is_pilot_mode():
        return False
    return os.environ.get('GRM_AUTO_REPLY_ENABLED', 'false').lower() == 'true'


def is_reply_enabled_globally() -> bool:
    """Global reply enable. Off by default, ON only after pilot validated."""
    return os.environ.get('GRM_REPLY_ENABLED_GLOBAL', 'false').lower() == 'true'


def is_grm_manage_enabled() -> bool:
    """Master switch for the optional 'GRM Manage' subsystem (Google OAuth
    connect/callback/account/location/reconciliation routes, and the
    reply draft/approval/publish/moderation API).

    OFF by default. Per GRM_PRODUCT_MASTER skill §3, OAuth / direct reply /
    auto-reply must never activate without an explicit owner decision.
    When this flag is false, the routes in app.routes.google and
    app.routes.response are not registered at all — they do not exist on
    the running app (404), regardless of whether GOOGLE_CLIENT_ID/SECRET
    happen to be configured. Flip to true only after an explicit owner
    decision to start using GRM Manage.
    """
    return os.environ.get('GRM_MANAGE_ENABLED', 'false').lower() == 'true'


def publish_requires_approval() -> bool:
    """In pilot mode, all publishes require human approval."""
    return True


def is_outlet_pilot_active(outlet) -> bool:
    """Check if an outlet can be active in pilot mode."""
    from app.models.entities import Outlet

    # Hard rule: Harjamukti is always excluded
    if outlet.name and 'harjamukti' in outlet.name.lower():
        return False
    if outlet.status == 'old_or_closed':
        return False

    if not is_pilot_mode():
        return outlet.monitor_enabled and outlet.status != 'old_or_closed'

    # Pilot: check whitelist
    whitelist = pilot_outlet_whitelist()
    if whitelist:
        return outlet.id in whitelist or outlet.name in whitelist

    if not outlet.monitor_enabled:
        return False

    # Pilot: enforce maximum active outlets (safety hardening).
    # Keep the oldest active pilot outlets up to the limit; reject the rest.
    # Harjamukti excluded. Limit raised only via a RUN decision.
    max_outlets = pilot_max_outlets()
    active_all = (
        Outlet.query.filter(
            Outlet.tenant_id == outlet.tenant_id,
            Outlet.monitor_enabled == True,  # noqa: E712
            Outlet.status != 'old_or_closed',
        )
        .filter(~Outlet.name.ilike('%harjamukti%'))
        .order_by(Outlet.created_at.asc())
        .all()
    )
    if len(active_all) > max_outlets:
        keep_ids = {o.id for o in active_all[:max_outlets]}
        return outlet.id in keep_ids
    return True


def rollback_available() -> dict:
    """Return rollback readiness info."""
    return {
        'rollback_plan_exists': True,
        'auto_reply_off': not is_auto_reply_enabled(),
        'approval_required': True,
        'mock_adapter_available': True,
        'database_backup_available': os.environ.get('DATABASE_URL', '').startswith('postgresql'),
        'feature_flags_readable': True,
    }
