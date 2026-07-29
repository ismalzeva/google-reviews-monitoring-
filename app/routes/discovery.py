"""Branch Discovery routes — RUN_02.

Endpoints for brand search, candidate display, owner verification, and audit.
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.entities import LocationCandidate, Outlet, AuditLog, Business
from app.services.audit import log_audit
from app.services.discovery import (
    search_places,
    normalize_candidate,
    deduplicate_candidates,
    save_candidates,
    verify_candidate,
)

bp = Blueprint('discovery', __name__, url_prefix='/discover')


def _get_business():
    """Get current user's business or return None."""
    return current_user.business if current_user.is_authenticated else None


# ─── SEARCH FORM + RESULTS ──────────────────────────────
@bp.route('/', methods=['GET'])
@login_required
def search_page():
    """Brand search page — enter brand name and optional city."""
    business = _get_business()
    candidates = LocationCandidate.query.filter_by(
        business_id=business.id
    ).order_by(LocationCandidate.created_at.desc()).all() if business else []

    # Group candidates by verification status for the UI
    verification_options = [
        {'value': 'owner_confirmed', 'label': '✅ Ini cabang Bubur Fay', 'icon': ''},
        {'value': 'owner_rejected', 'label': '❌ Bukan cabang Bubur Fay', 'icon': ''},
        {'value': 'old_or_closed', 'label': '🕰️ Cabang lama/sudah tutup', 'icon': ''},
        {'value': 'possible_duplicate', 'label': '📋 Listing duplikat', 'icon': ''},
        {'value': 'uncertain', 'label': '❓ Belum yakin', 'icon': ''},
        {'value': 'needs_access_review', 'label': '🔍 Perlu diklaim atau diperiksa', 'icon': ''},
    ]

    return render_template(
        'discovery/search.html',
        business=business,
        candidates=candidates,
        verification_options=verification_options,
        search_result=request.args.get('result'),
        error=request.args.get('error'),
    )


@bp.route('/search', methods=['POST'])
@login_required
def search():
    """Execute brand search — calls mock Places API."""
    business = _get_business()
    if not business:
        flash('Belum ada bisnis. Hubungi admin.', 'error')
        return redirect(url_for('discovery.search_page'))

    brand_name = request.form.get('brand_name', '').strip()
    city = request.form.get('city', '').strip()

    if not brand_name:
        flash('Nama brand wajib diisi.', 'error')
        return redirect(url_for('discovery.search_page'))

    # Validate: at least 3 characters
    if len(brand_name) < 3:
        flash('Nama brand minimal 3 karakter.', 'error')
        return redirect(url_for('discovery.search_page'))

    # Search via mock adapter
    try:
        raw_results = search_places(brand_name, city=city if city else None)
    except Exception as e:
        flash(f'Gagal mencari: {str(e)}', 'error')
        return redirect(url_for('discovery.search_page'))

    if not raw_results:
        flash(f'Tidak ditemukan hasil untuk "{brand_name}"'
              + (f' di {city}' if city else '') + '.', 'warning')
        return redirect(url_for('discovery.search_page'))

    # Get existing candidates for dedup
    existing = LocationCandidate.query.filter_by(
        business_id=business.id
    ).all()

    # Normalize and deduplicate
    candidates = []
    for raw in raw_results:
        candidate = normalize_candidate(raw, business.id, business.tenant_id, brand_name)
        candidates.append(candidate)

    deduped = deduplicate_candidates(candidates, existing)

    if not deduped:
        flash('Semua kandidat sudah ada di database (duplikat).', 'info')
    else:
        save_candidates(deduped)
        flash(f'{len(deduped)} kandidat baru ditemukan.', 'success')

    # Audit
    log_audit(
        action="brand_search",
        entity_type="business",
        entity_id=business.id,
        after={
            "brand_name": brand_name,
            "city": city,
            "raw_results": len(raw_results),
            "new_candidates": len(deduped),
        },
        tenant_id=business.tenant_id,
        actor_id=current_user.id,
    )

    return redirect(url_for('discovery.search_page'))


# ─── VERIFY CANDIDATE ───────────────────────────────────
@bp.route('/verify', methods=['POST'])
@login_required
def verify():
    """Owner verification decision for a candidate."""
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    candidate_id = request.form.get('candidate_id', '').strip()
    decision = request.form.get('decision', '').strip()
    note = request.form.get('note', '').strip()

    # Also check 'action' as fallback (for API clients)
    if not decision:
        raw_action = request.form.get('action', '').strip()
        decision_map = {
            'verified': 'owner_confirmed',
            'not_branch': 'owner_rejected',
            'old_or_closed': 'old_or_closed',
            'duplicate': 'possible_duplicate',
            'uncertain': 'uncertain',
            'needs_access': 'needs_access_review',
        }
        decision = decision_map.get(raw_action, raw_action)

    if not candidate_id or not decision:
        flash('Data verifikasi tidak lengkap.', 'error')
        return redirect(url_for('discovery.search_page'))

    # Tenant isolation: verify candidate belongs to current user's business
    candidate_check = LocationCandidate.query.filter_by(
        id=candidate_id,
        business_id=business.id
    ).first()
    if not candidate_check:
        flash('Kandidat tidak ditemukan.', 'error')
        return redirect(url_for('discovery.search_page'), 404)

    result = verify_candidate(
        candidate_id=candidate_id,
        decision=decision,
        user_id=current_user.id,
        note=note,
        tenant_id=business.tenant_id,
    )

    if not result:
        flash('Kandidat tidak ditemukan atau keputusan tidak valid.', 'error')
    else:
        label_map = {
            'owner_confirmed': 'dikonfirmasi sebagai cabang',
            'owner_rejected': 'ditandai bukan cabang',
            'old_or_closed': 'ditandai cabang lama/tutup',
            'possible_duplicate': 'ditandai duplikat',
            'uncertain': 'ditandai belum yakin',
            'needs_access_review': 'ditandai perlu dicek akses',
        }
        flash(f'✅ {result.display_name} {label_map.get(decision, decision)}.', 'success')

    return redirect(url_for('discovery.search_page'))


# ─── CANDIDATES LIST ────────────────────────────────────
@bp.route('/candidates', methods=['GET'])
@login_required
def candidate_list():
    """Full list of candidates with verification status."""
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    page = request.args.get('page', 1, type=int)
    per_page = 20

    status_filter = request.args.get('status', '').strip()
    query = LocationCandidate.query.filter_by(business_id=business.id)

    if status_filter:
        query = query.filter_by(owner_verification_status=status_filter)

    pagination = query.order_by(
        LocationCandidate.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    candidates = pagination.items
    outlets = {o.public_place_id: o for o in Outlet.query.filter_by(business_id=business.id).all()}

    return render_template(
        'discovery/candidates.html',
        business=business,
        candidates=candidates,
        outlets=outlets,
        pagination=pagination,
        status_filter=status_filter,
    )


# ─── AUDIT LOG ──────────────────────────────────────────
@bp.route('/audit', methods=['GET'])
@login_required
def audit_log():
    """Verification audit trail."""
    business = _get_business()
    if not business:
        flash('Akses ditolak.', 'error')
        return redirect(url_for('auth.login'))

    page = request.args.get('page', 1, type=int)
    per_page = 50

    logs = AuditLog.query.filter_by(
        tenant_id=business.tenant_id
    ).filter(
        AuditLog.action.in_(['brand_search', 'candidate_verified', 'candidate_dedup_skipped'])
    ).order_by(
        AuditLog.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'discovery/audit.html',
        business=business,
        logs=logs.items,
        pagination=logs,
    )
