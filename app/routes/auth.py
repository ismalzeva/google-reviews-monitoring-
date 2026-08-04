"""Authentication routes — register, login, logout."""
import collections
import logging
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify, g, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from app.models.entities import User, Business, ROLES
from app.services.audit import log_audit

bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# ─── In-memory rate limiter for registration ──────────────
_rate_window = 60
_rate_limit = 10
_rate_buckets: dict[str, collections.deque] = {}

# ─── Analytics tracker ────────────────────────────────────
_registration_events: list[dict] = []


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@bp.before_app_request
def set_tenant_context():
    """Set tenant_id in g for audit logging."""
    if current_user.is_authenticated:
        g.current_user_id = current_user.id
        g.tenant_id = current_user.business.tenant_id if current_user.business else None
    else:
        g.current_user_id = None
        g.tenant_id = None


# ─── REGISTER (2-Step Wizard) ─────────────────────────────

@bp.route('/register', methods=['GET', 'POST'])
def register():
    # AC-20: already logged in → redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'GET':
        # AC-28: wizard resume — if session has step1 data, show step 2
        reg_data = session.get('registration_step1')
        is_back = request.args.get('back') == '1'

        if reg_data and not is_back:
            created = reg_data.get('created_at', 0)
            if time.time() - created < 600:  # 10 min TTL
                return render_template(
                    'auth/register.html',
                    step=2,
                    email=reg_data.get('email', ''),
                    display_name=reg_data.get('display_name', ''),
                )
            # Expired → clear stale session
            session.pop('registration_step1', None)

        # AC-28: "back" param → show step 1 with pre-filled data from session
        if is_back and reg_data:
            return render_template(
                'auth/register.html',
                step=1,
                email=reg_data.get('email', ''),
                display_name=reg_data.get('display_name', ''),
            )

        return render_template('auth/register.html', step=1)

    # ─── POST handler ──────────────────────────────────────

    # AC-17: rate limit 10 POST/menit per IP
    ip = request.remote_addr or '127.0.0.1'
    if not _check_rate(ip):
        return render_template(
            'auth/register.html', step=1, error='Terlalu banyak percobaan. Silakan tunggu 1 menit.'
        ), 429

    step = request.form.get('step', '1')

    if step == '1':
        return _handle_step1()
    elif step == '2':
        return _handle_step2()
    else:
        return render_template('auth/register.html', step=1, error='Langkah tidak valid'), 400


def _handle_step1():
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    display_name = request.form.get('display_name', '').strip()

    errors = []
    if not email or '@' not in email:
        errors.append('Email tidak valid')
    if not password or len(password) < 8:
        errors.append('Password minimal 8 karakter')
    if not display_name:
        errors.append('Nama wajib diisi')

    if User.query.filter_by(email=email).first():
        errors.append('Email sudah terdaftar')

    if errors:
        return render_template('auth/register.html', step=1, error=errors[0], email=email, display_name=display_name), 400

    # AC-06: hash password BEFORE storing in session (never plaintext in cookie)
    session['registration_step1'] = {
        'email': email,
        'display_name': display_name,
        'password_hash': generate_password_hash(password),
        'created_at': time.time(),
    }
    session['registration_csrf'] = _uuid_short()

    return render_template(
        'auth/register.html',
        step=2,
        email=email,
        display_name=display_name,
    )


def _handle_step2():
    # AC-23: no session → redirect to step 1
    reg_data = session.get('registration_step1')
    if not reg_data:
        return render_template('auth/register.html', step=1, error='Sesi habis, silakan isi ulang')

    # AC-21: check TTL
    created = reg_data.get('created_at', 0)
    if time.time() - created > 600:
        session.pop('registration_step1', None)
        return render_template('auth/register.html', step=1, error='Sesi habis, silakan isi ulang')

    email = reg_data['email']
    display_name = reg_data['display_name']
    password_hash = reg_data['password_hash']

    brand_name = request.form.get('brand_name', '').strip()
    business_name = request.form.get('business_name', '').strip()
    city = request.form.get('city', '').strip()

    errors = []
    if not brand_name:
        errors.append('Nama brand wajib diisi')
    if not city:
        errors.append('Kota wajib diisi')

    if User.query.filter_by(email=email).first():
        errors.append('Email sudah terdaftar')

    if errors:
        return render_template(
            'auth/register.html', step=2,
            email=email, display_name=display_name,
            brand_name=brand_name, business_name=business_name, city=city,
            error=errors[0],
        ), 400

    # Use brand_name as business name if not provided
    final_business_name = business_name or brand_name

    # AC-12: trial_ends_at = now + 14 days
    trial_end = datetime.now(timezone.utc) + timedelta(days=14)

    business = Business(
        name=final_business_name,
        brand_name=brand_name,
        city=city,
        status='trialing',
        trial_ends_at=trial_end,
    )
    db.session.add(business)
    db.session.flush()

    user = User(
        email=email,
        password_hash=password_hash,  # already hashed in step 1
        display_name=display_name,
        role='owner',
        business_id=business.id,
    )
    db.session.add(user)
    db.session.flush()

    # AC-18: audit log + registration event
    log_audit(
        'user.registered', 'User', user.id,
        after={'email': email, 'role': 'owner', 'business': final_business_name},
        tenant_id=business.tenant_id, actor_type='system',
    )
    log_audit(
        'business.created', 'Business', business.id,
        after={'name': final_business_name, 'brand': brand_name, 'city': city},
        tenant_id=business.tenant_id, actor_type='system',
    )

    # AC-19: analytics tracking
    _track_registration(email, business.tenant_id)

    db.session.commit()

    # Clean up session
    session.pop('registration_step1', None)
    session.pop('registration_csrf', None)

    # AC-13: auto-login → redirect to trial welcome (GRM-007)
    login_user(user)
    return redirect(url_for('trial.welcome'))


# ─── LOGIN / LOGOUT ───────────────────────────────────────

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'GET':
        return render_template('auth/login.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return render_template('auth/login.html', error='Email atau password salah'), 401

    if not user.is_active:
        return render_template('auth/login.html', error='Akun tidak aktif'), 403

    log_audit('user.login', 'User', user.id, tenant_id=user.business.tenant_id if user.business else None)
    db.session.commit()

    login_user(user)
    next_url = request.args.get('next')
    return redirect(next_url or url_for('dashboard.index'))


@bp.route('/logout')
@login_required
def logout():
    log_audit('user.logout', 'User', current_user.id, tenant_id=current_user.business.tenant_id if current_user.business else None)
    db.session.commit()
    logout_user()
    return redirect(url_for('auth.login'))


# ─── RBAC DECORATOR ───────────────────────────────────────

def require_role(*roles):
    """Decorator: restrict access to specific roles."""
    from functools import wraps
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.has_role(*roles):
                if request.is_json or request.path.startswith('/api'):
                    return jsonify(success=False, data=None, meta={}, errors=[{"code": "FORBIDDEN", "message": f"Role {current_user.role} tidak memiliki akses", "field": None, "retryable": False}]), 403
                flash('Anda tidak memiliki akses untuk halaman ini', 'error')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ─── Helpers ──────────────────────────────────────────────

def _uuid_short():
    import uuid
    return uuid.uuid4().hex[:12]


def _check_rate(ip: str) -> bool:
    now = time.monotonic()
    bucket = _rate_buckets.get(ip)
    if bucket is None:
        _rate_buckets[ip] = collections.deque([now])
        return True
    while bucket and bucket[0] < now - _rate_window:
        bucket.popleft()
    if len(bucket) < _rate_limit:
        bucket.append(now)
        return True
    return False


def _track_registration(email: str, tenant_id: str) -> None:
    _registration_events.append({
        'event': 'registration_completed',
        'email': email,
        'tenant_id': tenant_id,
        'ip': request.remote_addr,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })
    logger.info('analytics|registration_completed|%s|%s', tenant_id, email[:email.index('@')] + '@***')
