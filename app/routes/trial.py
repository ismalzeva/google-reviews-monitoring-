"""Trial Activation blueprint — GRM-007.

Flow: Welcome → Step 1 (Add Outlet) → Step 2 (Verify) → Step 3 (Sync) → Step 4 (WOW).
"""
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

from flask import Blueprint, current_app, render_template, redirect, url_for, request, jsonify, session
from flask_login import login_required, current_user

from app import db
from app.models.entities import Business, Outlet
from app.services.ai_advisor import generate as advisor_generate

logger = logging.getLogger(__name__)
bp = Blueprint('trial', __name__, url_prefix='/trial')

_SYNC_PROGRESS = {}
_PROGRESS_TTL_SECONDS = 3600


def _now():
    return datetime.now(timezone.utc)


def _get_business():
    return current_user.business if current_user.is_authenticated else None


def _log_event(event: str, biz: Business, extra: dict = None):
    try:
        from app.services.audit import log_audit
        payload = {'event': event, 'tenant_id': biz.tenant_id}
        if extra:
            payload.update(extra)
        log_audit(event, 'Business', biz.id, after=payload,
                  tenant_id=biz.tenant_id, actor_type='system')
    except Exception:
        logger.warning("tracking event failed: %s", event, exc_info=True)


import json

import ast

def _parse_progress(val):
    """Parse setup_progress from DB (string repr → dict)."""
    if isinstance(val, dict):
        return val
    if not val:
        return {}
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        try:
            return json.loads(val.replace("'", '"').replace('True', 'true').replace('False', 'false'))
        except (json.JSONDecodeError, TypeError):
            try:
                return ast.literal_eval(val)
            except (ValueError, SyntaxError):
                return {}


def _write_progress(val):
    """Convert dict to JSON string for storage."""
    return json.dumps(val) if isinstance(val, dict) else val


def _update_progress(biz, step, done=True):
    progress = _parse_progress(biz.setup_progress)
    progress[step] = 'done' if done else 'in_progress'
    biz.setup_progress = _write_progress(progress)
    db.session.commit()


def _get_current_step(biz: Business) -> str:
    progress = _parse_progress(biz.setup_progress)
    if not biz.setup_started_at:
        return 'welcome'
    if not progress.get('step1'):
        return 'step1'
    if not progress.get('step2'):
        return 'step2'
    if not progress.get('step3'):
        return 'step3'
    return 'step4'


def redirect_trialing_user():
    """Called by dashboard.before_request to redirect trialing users."""
    biz = _get_business()
    if not biz or biz.status != 'trialing' or biz.setup_complete:
        return None
    step = _get_current_step(biz)
    if step == 'welcome':
        return url_for('trial.welcome')
    return url_for('trial.activate')


# ═══════════════════════════════════════════════════════════
# PAGES
# ═══════════════════════════════════════════════════════════

@bp.route('/welcome')
@login_required
def welcome():
    biz = _get_business()
    if not biz:
        return redirect(url_for('dashboard.index'))
    if biz.setup_complete:
        return redirect(url_for('dashboard.index'))

    if not biz.setup_started_at:
        biz.setup_started_at = _now()
        if not biz.setup_progress or biz.setup_progress == '{}':
            biz.setup_progress = '{}'
            _log_event('trial_started', biz)
        db.session.commit()

    progress = _parse_progress(biz.setup_progress)
    return render_template(
        'trial/welcome.html',
        business=biz,
        days_left=biz.trial_days_left,
        trial_status=biz.trial_status,
        outlet_count=biz.outlet_count,
        progress=progress,
    )


@bp.route('/activate')
@login_required
def activate():
    """Entry point — redirect to current activation step."""
    biz = _get_business()
    if not biz or biz.setup_complete:
        return redirect(url_for('dashboard.index'))

    step = _get_current_step(biz)
    if step == 'welcome':
        return redirect(url_for('trial.welcome'))
    if step == 'step1':
        return redirect(url_for('trial.step1_search'))
    if step == 'step2':
        return redirect(url_for('trial.step2_verify'))
    if step == 'step3':
        return redirect(url_for('trial.step3_sync'))
    return redirect(url_for('trial.step4_wow'))


@bp.route('/activate/step1')
@login_required
def step1_search():
    biz = _get_business()
    if not biz or biz.setup_complete:
        return redirect(url_for('dashboard.index'))
    return render_template('trial/activate.html',
                           business=biz, step=1, step_label='Cari Outlet',
                           total_steps=4, outlet_count=biz.outlet_count)


@bp.route('/activate/step1/search', methods=['POST'])
@login_required
def step1_do_search():
    biz = _get_business()
    if not biz or biz.setup_complete:
        return jsonify({'error': 'Already activated'}), 400

    query = (request.form.get('query') or '').strip()
    if not query:
        return jsonify({'results': [], 'error': 'Masukkan nama bisnis'}), 400

    results = []
    try:
        from app.services.public_provider import build_public_review_adapter
        adapter = build_public_review_adapter()
        if adapter and hasattr(adapter, 'discover'):
            cities = ['Depok', 'Bekasi', 'Jakarta', 'Bogor', 'Tangerang', 'Bandung']
            places, _ = adapter.discover(query, cities=cities)
            results = places[:5]
    except Exception:
        pass

    if not results:
        from app.services.discovery import search_places
        raw = search_places(query)
        results = raw[:5]

    return jsonify({
        'results': [{
            'place_id': r.get('place_id', ''),
            'display_name': r.get('display_name', r.get('name', '')),
            'rating': r.get('rating'),
            'review_count': r.get('review_count', r.get('total_reviews', 0)),
            'address': r.get('address', r.get('vicinity', '')),
        } for r in results]
    })


@bp.route('/activate/step1/select', methods=['POST'])
@login_required
def step1_select():
    biz = _get_business()
    if not biz or biz.setup_complete:
        return jsonify({'error': 'Already activated'}), 400
    if biz.outlet_count >= 1:
        return jsonify({'error': 'Trial hanya untuk 1 outlet'}), 403

    place_id = (request.form.get('place_id') or '').strip()
    name = (request.form.get('name') or '').strip()
    address = (request.form.get('address') or '').strip()
    rating = request.form.get('rating', type=float)
    review_count = request.form.get('review_count', type=int)

    if not place_id or not name:
        return jsonify({'error': 'Data outlet tidak lengkap'}), 400

    # Save candidate to session for step 2
    from flask import session
    session['trial_selected_outlet'] = {
        'place_id': place_id, 'name': name, 'address': address,
        'rating': rating, 'review_count': review_count,
    }
    _update_progress(biz, 'step1')
    _log_event('outlet_added', biz, {'outlet_name': name, 'place_id': place_id})
    return jsonify({'ok': True, 'redirect': url_for('trial.step2_verify')})


@bp.route('/activate/step2')
@login_required
def step2_verify():
    biz = _get_business()
    if not biz or biz.setup_complete:
        return redirect(url_for('dashboard.index'))

    selected = session.get('trial_selected_outlet')
    if not selected:
        return redirect(url_for('trial.step1_search'))

    return render_template('trial/activate.html',
                           business=biz, step=2, step_label='Verifikasi',
                           total_steps=4, outlet=selected)


@bp.route('/activate/step2/confirm', methods=['POST'])
@login_required
def step2_confirm():
    biz = _get_business()
    if not biz or biz.setup_complete:
        return jsonify({'error': 'Already activated'}), 400
    if biz.outlet_count >= 1:
        return jsonify({'error': 'Trial hanya untuk 1 outlet'}), 403

    selected = session.get('trial_selected_outlet')
    if not selected:
        return jsonify({'error': 'Sesi habis. Ulangi dari Step 1.'}), 400

    outlet = Outlet(
        tenant_id=biz.tenant_id, business_id=biz.id,
        name=selected['name'], address=selected.get('address', ''),
        public_place_id=selected['place_id'],
        business_rating=selected.get('rating'),
        business_review_count=selected.get('review_count', 0),
        monitor_enabled=True, source='public_scraping',
    )
    db.session.add(outlet)
    db.session.flush()
    session['trial_outlet_id'] = outlet.id
    _update_progress(biz, 'step2')
    session.pop('trial_selected_outlet', None)
    return jsonify({'ok': True, 'redirect': url_for('trial.step3_sync')})


@bp.route('/activate/step3')
@login_required
def step3_sync():
    biz = _get_business()
    if not biz or biz.setup_complete:
        return redirect(url_for('dashboard.index'))

    outlet_id = session.get('trial_outlet_id')
    if not outlet_id:
        return redirect(url_for('trial.step1_search'))

    outlet = Outlet.query.get(outlet_id)
    return render_template('trial/activate.html',
                           business=biz, step=3, step_label='Sinkronkan',
                           total_steps=4, outlet=outlet)


def build_public_review_adapter(source=None):
    """HF-006: Public adapter builder used by trial step3 sync.

    Thin re-export so tests can patch a single trial-module entrypoint and so
    the sync path is explicit about using the PUBLIC provider (place_id-based,
    no Google OAuth) — never the GBP path.
    """
    from app.services.public_provider import build_public_review_adapter as _build
    return _build(source)


@bp.route('/activate/step3/start', methods=['POST'])
@login_required
def step3_start_sync():
    biz = _get_business()
    outlet_id = session.get('trial_outlet_id')
    if not biz or not outlet_id:
        return jsonify({'error': 'Sesi tidak valid'}), 400

    # HF-006 fail-closed ownership check: the session outlet must belong to
    # THIS business+tenant. Session tampering must never touch other tenants.
    outlet = Outlet.query.filter_by(
        id=outlet_id, tenant_id=biz.tenant_id, business_id=biz.id,
    ).first()
    if not outlet:
        return jsonify({'error': 'Outlet tidak ditemukan'}), 404

    now = time.time()
    existing = _SYNC_PROGRESS.get(outlet_id)
    if (
        isinstance(existing, dict)
        and existing.get('status') == 'running'
        and now - existing.get('created_ts', 0) < _PROGRESS_TTL_SECONDS
    ):
        # HF-006 idempotent start: reuse the running task instead of spawning
        # a parallel duplicate sync for the same outlet.
        return jsonify({'task_id': existing['task_id']})
    if isinstance(existing, dict) and now - existing.get('created_ts', 0) >= _PROGRESS_TTL_SECONDS:
        _SYNC_PROGRESS.pop(outlet_id, None)

    task_id = str(uuid.uuid4())
    _SYNC_PROGRESS[outlet_id] = {
        'task_id': task_id, 'status': 'running',
        'total': outlet.business_review_count or 0,
        'synced': 0, 'percent': 0, 'error': None,
        'created_ts': now,
    }

    _log_event('first_sync_started', biz, {'outlet': outlet.name})

    # HF-006: capture PRIMITIVES before starting the worker thread — the
    # worker never touches ORM instances from another thread's session.
    _app = current_app._get_current_object()
    tenant_id = biz.tenant_id
    business_id = biz.id

    def _run_sync():
        with _app.app_context():
            try:
                from app.services.sync_service import sync_public_reviews
                adapter = build_public_review_adapter()
                result = sync_public_reviews(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    outlet_ids=[outlet_id],
                    adapter=adapter,
                    source=getattr(adapter, 'source_name', None),
                )
                failed = result.get('locations_failed', 0)
                succeeded = result.get('locations_succeeded', 0)
                if failed and not succeeded:
                    raise RuntimeError(
                        '; '.join(
                            e.get('error', 'sync error')
                            for e in (result.get('errors') or [])
                        ) or 'sync failed'
                    )
                synced = result.get('reviews_created', 0) + result.get('reviews_updated', 0)
                _SYNC_PROGRESS[outlet_id] = {
                    'task_id': task_id, 'status': 'done',
                    'total': result.get('reviews_received', 0),
                    'synced': synced, 'percent': 100, 'error': None,
                    'created_ts': time.time(),
                }
                with db.session() as s:
                    biz_row = s.get(Business, business_id)
                    if biz_row is not None:
                        progress = _parse_progress(biz_row.setup_progress)
                        if progress.get('step3') != 'done':
                            progress['step3'] = 'done'
                            biz_row.setup_progress = _write_progress(progress)
                            s.commit()
            except Exception as e:
                logger.error("Trial step3 public sync failed for biz=%s outlet=%s: %s",
                             business_id, outlet_id, e, exc_info=True)
                _SYNC_PROGRESS[outlet_id] = {
                    'task_id': task_id, 'status': 'error', 'total': 0,
                    'synced': 0, 'percent': 0,
                    'error': 'Sinkronisasi gagal. Periksa koneksi internet Anda dan coba lagi.',
                    'created_ts': time.time(),
                }

    threading.Thread(target=_run_sync, daemon=True).start()
    return jsonify({'task_id': task_id})


@bp.route('/activate/step3/progress/<task_id>')
@login_required
def step3_progress(task_id):
    _purge_stale_progress()
    info = None
    for entry in _SYNC_PROGRESS.values():
        if isinstance(entry, dict) and entry.get('task_id') == task_id:
            info = entry
            break
    if info is None:
        info = {'status': 'unknown'}
    payload = {
        'status': info['status'],
        'total': info.get('total', 0),
        'synced': info.get('synced', 0),
        'percent': info.get('percent', 0),
    }
    if info.get('error'):
        payload['error'] = info['error']
    return jsonify(payload)


def _purge_stale_progress():
    """HF-006: bound the progress store — drop entries older than TTL."""
    cutoff = time.time() - _PROGRESS_TTL_SECONDS
    stale = [
        k for k, v in _SYNC_PROGRESS.items()
        if not isinstance(v, dict) or v.get('created_ts', 0) < cutoff
    ]
    for k in stale:
        _SYNC_PROGRESS.pop(k, None)


@bp.route('/activate/step4')
@login_required
def step4_wow():
    biz = _get_business()
    if not biz or biz.setup_complete:
        return redirect(url_for('dashboard.index'))

    outlet_id = session.get('trial_outlet_id')
    outlet = Outlet.query.get(outlet_id) if outlet_id else None

    # Generate AI Advisor
    advisor = None
    empty_ai = False
    try:
        from app.services.public_analytics import parse_filters
        f = parse_filters({})
        advisor = advisor_generate(biz.tenant_id, biz.id, f)
    except Exception:
        logger.warning("AI Advisor generation failed", exc_info=True)

    if not advisor or not advisor.get('issues'):
        empty_ai = True

    # Mark WOW moment
    if not biz.wow_moment_reached_at:
        biz.wow_moment_reached_at = _now()
        biz.setup_complete = True
        _update_progress(biz, 'step4')
        _log_event('wow_moment_reached', biz, {
            'outlet': outlet.name if outlet else 'unknown',
            'empty_ai': empty_ai,
        })
        session.pop('trial_outlet_id', None)

    # Count synced reviews for celebration
    from app.models.entities import Review
    review_count = 0
    if outlet:
        review_count = Review.query.filter_by(
            tenant_id=biz.tenant_id, business_id=biz.id
        ).count()

    return render_template('trial/activate.html',
                           business=biz, step=4, step_label='Selesai',
                           total_steps=4, outlet=outlet,
                           advisor=advisor, empty_ai=empty_ai,
                           review_count=review_count)


def _is_skip_eligible(biz: Business) -> bool:
    """HF-004: Check if user can skip activation.

    Eligible: user has at least one monitored outlet (from GBP match,
    prior setup, or discovery). These users have already completed the
    core value step (outlet selection) and don't need to repeat it.

    Ineligible: user has no outlets — must complete activation flow
    to select and verify their outlet.
    """
    if not biz:
        return False
    # Already complete — no need to skip
    if biz.setup_complete:
        return False
    # Has at least one monitored outlet → eligible
    return biz.outlet_count >= 1


@bp.route('/skip')
@login_required
def skip():
    """HF-004: Skip activation with eligibility guard.

    Eligible users (have existing outlets) → skip to dashboard.
    Ineligible users (no outlets) → redirect to activation flow.
    Already-complete users → redirect to dashboard (idempotent).
    """
    biz = _get_business()

    # Idempotent: already complete → dashboard
    if biz and biz.setup_complete:
        return redirect(url_for('dashboard.index'))

    # No business → dashboard (safety)
    if not biz:
        return redirect(url_for('dashboard.index'))

    # Eligibility check
    if not _is_skip_eligible(biz):
        # Ineligible → redirect to activation flow
        return redirect(url_for('trial.activate'))

    # Eligible → skip activation
    biz.setup_complete = True
    biz.wow_moment_reached_at = _now()
    biz.setup_progress = _write_progress({
        'step1': 'skipped', 'step2': 'skipped',
        'step3': 'skipped', 'step4': 'skipped',
    })
    db.session.commit()
    _log_event('activation_skipped', biz, {
        'reason': 'eligible_user_with_outlets',
        'outlet_count': biz.outlet_count,
    })
    return redirect(url_for('dashboard.index'))
