"""Google Business Profile connection routes — OAuth, account selection,
location listing, reconciliation, health check, and disconnect.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app.models.entities import db, GoogleConnection, Outlet, LocationCandidate, OAuthState
from app.services import google_oauth as goog
from app.services.audit import log_audit
from datetime import datetime, timezone
from collections import defaultdict
import json
import uuid

google_bp = Blueprint('google', __name__, url_prefix='/google')


def _get_business():
    if current_user.is_anonymous:
        return None
    from app.models.entities import Business
    return Business.query.get(current_user.business_id)


def _adapter_mode() -> str:
    """Return 'mock' or 'production' based on env config."""
    from app.services.feature_flags import is_production_configured
    return 'production' if is_production_configured() else 'mock'


# ─── CONNECT ──────────────────────────────────────────────

@google_bp.route('/connect')
@login_required
def connect():
    """Start OAuth flow — secure crypto state, server-side storage."""
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    # Check existing connection
    existing = goog._get_connection(business.id, business.tenant_id)
    if existing and existing.status in (goog.STATUS_CONNECTED, goog.STATUS_MOCK_CONNECTED):
        flash('Akun Google sudah terhubung.', 'info')
        return redirect(url_for('google.status'))

    # Create new connection record
    conn = GoogleConnection(
        id=str(uuid.uuid4()),
        tenant_id=business.tenant_id,
        business_id=business.id,
        status=goog.STATUS_OAUTH_IN_PROGRESS,
        connected_by=current_user.id,
        adapter_mode=_adapter_mode(),
    )
    db.session.add(conn)
    db.session.commit()

    if not goog._is_using_real_api():
        # Mock mode: create secure server-side state
        state_nonce = goog.create_oauth_state(
            user_id=current_user.id,
            tenant_id=business.tenant_id,
            business_id=business.id,
            connection_id=conn.id,
            intent='/google/accounts',
        )
        redirect_url = goog.get_redirect_uri()
        callback_url = f"{redirect_url}?code=mock_auth_code&state={state_nonce}"
        return redirect(callback_url)

    # Production OAuth: build real Google OAuth URL
    state_nonce = goog.create_oauth_state(
        user_id=current_user.id,
        tenant_id=business.tenant_id,
        business_id=business.id,
        connection_id=conn.id,
        intent='/google/accounts',
    )
    from flask import current_app
    cid = current_app.config.get('GOOGLE_CLIENT_ID')
    redirect_uri = goog.get_redirect_uri()
    oauth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={cid}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=https://www.googleapis.com/auth/business.manage"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state_nonce}"
    )
    return redirect(oauth_url)


@google_bp.route('/callback')
def callback():
    """Handle OAuth callback — validate state with full security checks."""
    code = request.args.get('code', '')
    state_nonce = request.args.get('state', '')

    if not code:
        flash('Parameter OAuth tidak lengkap (missing code).', 'error')
        return redirect(url_for('dashboard.index'))

    if not state_nonce:
        flash('Parameter OAuth tidak lengkap (missing state).', 'error')
        return redirect(url_for('dashboard.index'))

    # Require authenticated user for state validation
    if current_user.is_anonymous:
        flash('Sesi telah berakhir. Silakan login ulang.', 'error')
        return redirect(url_for('auth.login'))

    business = _get_business()
    if not business:
        flash('Akses ditolak — business tidak ditemukan.', 'error')
        return redirect(url_for('auth.login'))

    # Validate state with full security checks
    try:
        state = goog.validate_oauth_state(
            state_nonce=state_nonce,
            user_id=current_user.id,
            tenant_id=business.tenant_id,
            business_id=business.id,
        )
    except ValueError as e:
        error_msg = str(e)
        error_map = {
            'oauth_state_empty': 'State OAuth kosong.',
            'oauth_state_invalid': 'State OAuth tidak valid — potensi CSRF.',
            'oauth_state_replayed': 'State OAuth sudah pernah digunakan — potensi replay attack.',
            'oauth_state_expired': 'State OAuth sudah kedaluwarsa. Silakan coba lagi.',
            'oauth_state_user_mismatch': 'State OAuth milik pengguna lain.',
            'oauth_state_tenant_mismatch': 'State OAuth milik tenant lain.',
            'oauth_state_business_mismatch': 'State OAuth milik bisnis lain.',
        }
        flash(error_map.get(error_msg, f'State OAuth tidak valid: {error_msg}'), 'error')

        # Audit the failed attempt
        log_audit(
            action='oauth_callback_failed',
            entity_type='google_connection',
            tenant_id=business.tenant_id,
            actor_id=current_user.id,
            reason=f'OAuth state validation failed: {error_msg}',
        )
        db.session.commit()
        return redirect(url_for('dashboard.index'))

    # Consume the state (single-use)
    try:
        goog.consume_oauth_state(state)
    except Exception:
        db.session.rollback()

    # Exchange code for tokens
    try:
        adapter = _adapter_mode()
        goog.exchange_code_for_token(code, state.connection_id, business.tenant_id, adapter_mode_val=adapter)
        flash('Akun Google berhasil terhubung!', 'success')

        log_audit(
            action='oauth_callback_success',
            entity_type='google_connection',
            entity_id=state.connection_id,
            tenant_id=business.tenant_id,
            actor_id=current_user.id,
            reason='OAuth callback completed successfully',
        )
        db.session.commit()
        return redirect(url_for('google.accounts'))
    except PermissionError:
        flash('Akses ditolak saat menghubungkan akun Google.', 'error')
        return redirect(url_for('dashboard.index'))
    except Exception as e:
        flash(f'Gagal menghubungkan: {str(e)}', 'error')
        return redirect(url_for('google.connect'))


# ─── ACCOUNTS ─────────────────────────────────────────────

@google_bp.route('/accounts')
@login_required
def accounts():
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    conn = goog._get_connection(business.id, business.tenant_id)
    is_mock = conn and conn.adapter_mode == 'mock'

    try:
        accounts_list = goog.list_accounts(business.id, business.tenant_id)
    except ValueError as e:
        flash(str(e), 'warning')
        return redirect(url_for('google.connect'))

    return render_template(
        'google/accounts.html',
        accounts=accounts_list,
        business=business,
        is_mock=is_mock,
        connection=conn,
    )


@google_bp.route('/select-account', methods=['POST'])
@login_required
def select_account():
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    account_id = request.form.get('account_id', '').strip()
    if not account_id:
        flash('Pilih account terlebih dahulu.', 'warning')
        return redirect(url_for('google.accounts'))

    # Tenant isolation check
    conn = goog._get_connection(business.id, business.tenant_id)
    if not conn:
        flash('Koneksi tidak ditemukan.', 'error')
        return redirect(url_for('google.connect'))

    # Check if already has a different account
    if conn.selected_account_id and conn.selected_account_id != account_id:
        flash(f'Mengganti account dari {conn.selected_account_id} ke {account_id}.', 'info')

    try:
        goog.select_account(business.id, business.tenant_id, account_id, user_id=current_user.id)
        flash('Account berhasil dipilih!', 'success')
        return redirect(url_for('google.locations'))
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('google.accounts'))


# ─── LOCATIONS ────────────────────────────────────────────

@google_bp.route('/locations')
@login_required
def locations():
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    conn = goog._get_connection(business.id, business.tenant_id)
    is_mock = conn and conn.adapter_mode == 'mock'

    try:
        locations_list = goog.list_locations(business.id, business.tenant_id)
    except ValueError as e:
        flash(str(e), 'warning')
        conn = goog._get_connection(business.id, business.tenant_id)
        if not conn or not conn.selected_account_id:
            return redirect(url_for('google.accounts'))
        return redirect(url_for('google.status'))

    return render_template(
        'google/locations.html',
        locations=locations_list,
        business=business,
        is_mock=is_mock,
        connection=conn,
    )


# ─── RECONCILIATION ───────────────────────────────────────

@google_bp.route('/reconciliation')
@login_required
def reconciliation():
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    conn = goog._get_connection(business.id, business.tenant_id)
    is_mock = conn and conn.adapter_mode == 'mock'

    try:
        results = goog.reconcile_candidates(business.id, business.tenant_id)
    except ValueError as e:
        flash(str(e), 'warning')
        return redirect(url_for('google.status'))

    has_ambiguous = any(r['match_status'] == 'ambiguous_match' for r in results)
    matched = sum(1 for r in results if r['match_status'] == 'matched_to_gbp')
    unmatched = sum(1 for r in results if r['match_status'] == 'unmatched_to_gbp')
    ambiguous = sum(1 for r in results if r['match_status'] == 'ambiguous_match')
    owner_blocked = sum(1 for r in results if r.get('owner_blocked'))

    return render_template(
        'google/reconciliation.html',
        results=results,
        has_ambiguous=has_ambiguous,
        matched=matched,
        unmatched=unmatched,
        ambiguous=ambiguous,
        owner_blocked=owner_blocked,
        business=business,
        is_mock=is_mock,
        connection=conn,
    )


@google_bp.route('/resolve-ambiguous', methods=['POST'])
@login_required
def resolve_ambiguous():
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    decisions = defaultdict(dict)
    for key, value in request.form.items():
        if key.startswith('candidate_'):
            cand_id = key.replace('candidate_', '')
            try:
                decisions[cand_id] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                continue

    try:
        results_before = goog.reconcile_candidates(business.id, business.tenant_id)
        # Tenant-safe: reconcile_candidates already filters by business_id + tenant_id
        goog.save_reconciliation(
            business.id, business.tenant_id,
            results_before,
            resolve_ambiguous=decisions,
            user_id=current_user.id,
        )
        flash('Rekonsiliasi berhasil disimpan!', 'success')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('google.reconciliation'))


@google_bp.route('/save-reconciliation', methods=['POST'])
@login_required
def save_reconciliation():
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    try:
        results = goog.reconcile_candidates(business.id, business.tenant_id)
        goog.save_reconciliation(business.id, business.tenant_id, results, user_id=current_user.id)
        flash('Rekonsiliasi berhasil disimpan!', 'success')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('google.reconciliation'))


# ─── STATUS / HEALTH ─────────────────────────────────────

@google_bp.route('/status')
@login_required
def status():
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    conn = goog._get_connection(business.id, business.tenant_id)
    health = None
    if conn and conn.status in (goog.STATUS_CONNECTED, goog.STATUS_MOCK_CONNECTED,
                                goog.STATUS_PARTIAL_ACCESS, goog.STATUS_TOKEN_EXPIRED):
        try:
            health = goog.check_connection_health(business.id, business.tenant_id)
        except Exception:
            health = {'error': 'Health check failed'}

    is_mock = conn and conn.adapter_mode == 'mock'

    return render_template(
        'google/status.html',
        connection=conn,
        health=health,
        business=business,
        is_mock=is_mock,
    )


# ─── DISCONNECT ───────────────────────────────────────────

@google_bp.route('/disconnect', methods=['POST'])
@login_required
def disconnect():
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    revoke = request.form.get('revoke', '') == 'yes'

    # Tenant isolation check
    conn = goog._get_connection(business.id, business.tenant_id)
    if not conn:
        flash('Tidak ada koneksi untuk diputuskan.', 'error')
        return redirect(url_for('google.status'))

    try:
        goog.disconnect(business.id, business.tenant_id, revoke=revoke, user_id=current_user.id)
        flash('Koneksi Google berhasil diputuskan.', 'info')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('google.status'))


# ─── API ──────────────────────────────────────────────────

@google_bp.route('/api/status')
@login_required
def api_status():
    """JSON endpoint for connection health (used by dashboard)."""
    business = _get_business()
    if not business:
        return jsonify({'success': False, 'errors': [{'code': 'no_business'}]}), 403

    try:
        health = goog.check_connection_health(business.id, business.tenant_id)
        return jsonify({'success': True, 'data': health})
    except ValueError as e:
        return jsonify({
            'success': False,
            'errors': [{'code': 'not_connected', 'message': str(e)}],
        }), 200


# ─── PUB/SUB WEBHOOK ───────────────────────────────────


@google_bp.route('/pubsub-push', methods=['POST'])
def pubsub_push():
    """Google Cloud Pub/Sub push subscription endpoint."""
    from app.services.event_service import process_pubsub_push
    from flask import current_app

    body = request.get_json(silent=True)
    if not body:
        return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

    # Validate the push via Google JWT
    authorization = request.headers.get('Authorization', '')
    is_verified = False
    if authorization and current_app.config.get('PUBSUB_VERIFY_TOKEN'):
        import re
        match = re.match(r'^Bearer\s+(\S+)', authorization)
        if match:
            from app.services.google_business_profile import verify_pubsub_token
            is_verified = verify_pubsub_token(match.group(1)) is not None
    else:
        is_verified = True  # fallback for dev/test environments

    if not is_verified and authorization:
        logger.warning('Pub/Sub push without valid OIDC token')
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    result = process_pubsub_push(body)
    if result.get('status') == 'invalid':
        return jsonify(result), 400

    return jsonify(result), 200


@google_bp.route('/pubsub-health')
def pubsub_endpoint_health():
    """Return Pub/Sub endpoint health status."""
    from app.services.event_service import pubsub_health_check
    health = pubsub_health_check()
    health['endpoint'] = url_for('google.pubsub_push', _external=True)
    return jsonify(health), 200
