"""Trial Activation blueprint — GRM-007.

Flow: Welcome → Step 1 (Add Outlet) → Step 2 (Verify) → Step 3 (Sync) → Step 4 (WOW).
"""
import logging
from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from flask_login import login_required, current_user

from app import db
from app.models.entities import Business, Outlet
from app.services.ai_advisor import generate as advisor_generate

logger = logging.getLogger(__name__)
bp = Blueprint('trial', __name__, url_prefix='/trial')

_SYNC_PROGRESS = {}


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


@bp.route('/activate/step3/start', methods=['POST'])
@login_required
def step3_start_sync():
    biz = _get_business()
    outlet_id = session.get('trial_outlet_id')
    if not biz or not outlet_id:
        return jsonify({'error': 'Sesi tidak valid'}), 400

    outlet = Outlet.query.get(outlet_id)
    if not outlet:
        return jsonify({'error': 'Outlet tidak ditemukan'}), 404

    import uuid
    task_id = str(uuid.uuid4())
    _SYNC_PROGRESS[task_id] = {
        'status': 'running', 'total': outlet.business_review_count or 0,
        'synced': 0, 'percent': 0, 'error': None,
    }

    _log_event('first_sync_started', biz, {'outlet': outlet.name})

    import threading
    def _run_sync():
        try:
            from app.services.sync_service import sync_reviews
            with db.session() as s:
                result = sync_reviews(
                    tenant_id=biz.tenant_id, business_id=biz.id,
                    source='public_scraping',
                    outlet_ids=[outlet.id],
                )
                synced = result.get('reviews_created', 0) + result.get('reviews_updated', 0)
                _SYNC_PROGRESS[task_id] = {
                    'status': 'done', 'total': result.get('reviews_received', 0),
                    'synced': synced, 'percent': 100, 'error': None,
                }
                _log_event('first_sync_completed', biz, {
                    'outlet': outlet.name,
                    'reviews_synced': synced,
                })
        except Exception as e:
            _SYNC_PROGRESS[task_id] = {
                'status': 'error', 'total': 0, 'synced': 0,
                'percent': 0, 'error': str(e),
            }

    threading.Thread(target=_run_sync, daemon=True).start()
    return jsonify({'task_id': task_id})


@bp.route('/activate/step3/progress/<task_id>')
@login_required
def step3_progress(task_id):
    info = _SYNC_PROGRESS.get(task_id, {'status': 'unknown'})
    if info['status'] == 'done' or info['status'] == 'error':
        # Mark step3 as done
        biz = _get_business()
        if biz and info['status'] == 'done':
            _update_progress(biz, 'step3')
        _SYNC_PROGRESS.pop(task_id, None)
    return jsonify(info)


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


@bp.route('/skip')
@login_required
def skip():
    """Skip activation → go to dashboard (with trial banner)."""
    biz = _get_business()
    if biz and not biz.setup_complete:
        biz.setup_complete = True
        biz.wow_moment_reached_at = _now()
        biz.setup_progress = {'step1': 'skipped', 'step2': 'skipped',
                              'step3': 'skipped', 'step4': 'skipped'}
        db.session.commit()
    return redirect(url_for('dashboard.index'))
