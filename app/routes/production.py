"""Production readiness diagnostic — checks all blockers before live activation.

This endpoint is safe to call without credentials. It never returns
secrets, tokens, or sensitive configuration values.
"""
from flask import Blueprint, jsonify, current_app
from datetime import datetime, timezone
import os
import uuid

from app import db
from app.services.feature_flags import (
    is_production_configured,
    is_pilot_mode,
    is_auto_reply_enabled,
    is_reply_enabled_globally,
    pilot_max_outlets,
    pilot_outlet_whitelist,
    rollback_available,
)

bp = Blueprint('production', __name__, url_prefix='/production')


def _redacted(value: str) -> str:
    """Return first 4 + '...' if value is set, else '⛔ NOT SET'."""
    if not value:
        return '⛔ NOT SET'
    return value[:4] + '****'


def _yes_no(val: bool) -> str:
    return '✅ YES' if val else '⛔ NO'


@bp.route('/readiness')
def readiness():
    """Full production readiness diagnostic.

    Categories:
      1. Google OAuth — credentials, redirect URI, scopes
      2. Business Profile API — base URL configured
      3. Pub/Sub — project, topic, subscription
      4. Pilot mode — current limits and whitelist
      5. Security — auto-reply, reply enabled, approval, rollback
      6. Infrastructure — env file, database type, Caddy/domain
    """
    cfg = current_app.config

    # ── 1. Google OAuth ──────────────────────────────────────
    cid = cfg.get('GOOGLE_CLIENT_ID', '')
    csec = cfg.get('GOOGLE_CLIENT_SECRET', '')
    redirect_uri = cfg.get('GOOGLE_REDIRECT_URI', '')
    oauth_scopes = cfg.get('GOOGLE_SCOPES', [])
    prod_configured = is_production_configured()

    oauth = {
        'production_configured': _yes_no(prod_configured),
        'client_id': _redacted(cid),
        'client_secret': _redacted(csec),
        'redirect_uri': redirect_uri,
        'scopes': oauth_scopes,
        'blocker': 'GOOGLE_CLIENT_ID dan/atau GOOGLE_CLIENT_SECRET belum diset' if not prod_configured else None,
    }

    # ── 2. GBP API ──────────────────────────────────────────
    gbp_base_url = cfg.get('GBP_API_BASE_URL', 'https://businessprofile.googleapis.com/v1')
    gbp = {
        'api_base_url': gbp_base_url,
        'api_version': cfg.get('GBP_API_VERSION', 'v1'),
    }

    # ── 3. Pub/Sub ──────────────────────────────────────────
    gcp_project = cfg.get('GCP_PROJECT_ID', '')
    pubsub_topic = cfg.get('PUBSUB_TOPIC', '')
    pubsub_subscription = cfg.get('PUBSUB_SUBSCRIPTION', '')
    pubsub_sa_json = cfg.get('PUBSUB_SERVICE_ACCOUNT_JSON', '')

    pubsub = {
        'gcp_project': _redacted(gcp_project),
        'topic': _redacted(pubsub_topic),
        'subscription': _redacted(pubsub_subscription),
        'service_account_json': _redacted(pubsub_sa_json),
        'blocker': 'Pub/Sub belum dikonfigurasi (GCP Project, Topic, Subscription)' if not gcp_project else None,
    }

    # ── 4. Pilot Mode ───────────────────────────────────────
    pilot = {
        'pilot_mode': is_pilot_mode(),
        'max_outlets': pilot_max_outlets(),
        'outlet_whitelist': pilot_outlet_whitelist(),
        'harjamukti_excluded': True,  # hard rule in feature_flags
    }

    # ── 5. Security ─────────────────────────────────────────
    security = {
        'auto_reply_enabled': is_auto_reply_enabled(),
        'reply_enabled_globally': is_reply_enabled_globally(),
        'publish_requires_approval': True,  # hard rule in pilot
        'rollback': rollback_available(),
    }

    # ── 6. Infrastructure ───────────────────────────────────
    env_file_exists = os.path.isfile(
        os.path.join(current_app.root_path, '..', '.env')
    )
    db_uri = cfg.get('SQLALCHEMY_DATABASE_URI', '')
    db_is_postgres = db_uri.startswith('postgresql')
    hostname = os.uname().nodename

    infra = {
        'env_file': '✅ EXISTS' if env_file_exists else '⛔ MISSING',
        'env_file_permissions': None,  # not checked here (OS-level)
        'database_type': 'PostgreSQL' if db_is_postgres else 'SQLite',
        'database_uri': _redacted(db_uri.split('://')[0] + '://' + db_uri.split('://')[1].split('@')[-1] if '@' in db_uri else db_uri.split('://')[0] + '://...'),
        'hostname': hostname,
        'app_port': cfg.get('APP_PORT', 8083),
    }

    # ── Overall Status ──────────────────────────────────────
    blockers = []
    if not prod_configured:
        blockers.append('🔴 GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET belum diset')
    if not gcp_project:
        blockers.append('🔴 GCP_PROJECT_ID belum diset — Pub/Sub tidak bisa aktif')
    if not pubsub_topic:
        blockers.append('🔴 PUBSUB_TOPIC belum diset')
    if not pubsub_subscription:
        blockers.append('🔴 PUBSUB_SUBSCRIPTION belum diset')
    if not redirect_uri.startswith('https://') and prod_configured:
        blockers.append('🔴 Redirect URI pakai http — tidak bisa untuk Google OAuth production')
    if is_auto_reply_enabled():
        blockers.append('⚠️ Auto-reply AKTIF — pastikan sudah siap')
    if is_reply_enabled_globally():
        blockers.append('⚠️ reply_enabled_globally AKTIF — pastikan sudah siap')

    overall = {
        'status': 'blocked' if blockers else 'ready_for_live_activation',
        'summary': f"{len(blockers)} blocker(s) ditemukan" if blockers else "✅ Semua siap — tidak ada blocker",
        'blockers': blockers,
    }

    # ── DB check ────────────────────────────────────────────
    db_ok = False
    try:
        db.session.execute(db.text('SELECT 1'))
        db_ok = True
    except Exception:
        pass
    infra['database_reachable'] = _yes_no(db_ok)
    if not db_ok:
        blockers.append('🔴 Database tidak reachable')

    return jsonify({
        'endpoint': '/production/readiness',
        'timestamp': datetime.now().isoformat(),
        'app_name': cfg.get('APP_NAME', 'Google Reviews Monitoring'),
        'overall': overall,
        'oauth': oauth,
        'gbp_api': gbp,
        'pubsub': pubsub,
        'pilot': pilot,
        'security': security,
        'infrastructure': infra,
    })
