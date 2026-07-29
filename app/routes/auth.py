"""Authentication routes — register, login, logout."""
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify, g
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from app.models.entities import User, Business, ROLES
from app.services.audit import log_audit

bp = Blueprint('auth', __name__)


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


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'GET':
        return render_template('auth/register.html')

    data = request.form
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    display_name = data.get('display_name', '').strip()
    business_name = data.get('business_name', '').strip()
    brand_name = data.get('brand_name', '').strip()

    # Validation
    errors = []
    if not email or '@' not in email:
        errors.append('Email tidak valid')
    if not password or len(password) < 8:
        errors.append('Password minimal 8 karakter')
    if not display_name:
        errors.append('Nama wajib diisi')
    if not business_name:
        errors.append('Nama bisnis wajib diisi')
    if not brand_name:
        errors.append('Brand wajib diisi')
    if User.query.filter_by(email=email).first():
        errors.append('Email sudah terdaftar')

    if errors:
        return render_template('auth/register.html', errors=errors, data=data), 400

    # Create business (tenant)
    business = Business(name=business_name, brand_name=brand_name)
    db.session.add(business)
    db.session.flush()  # Get business.id

    # Create user as owner
    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        display_name=display_name,
        role='owner',
        business_id=business.id,
    )
    db.session.add(user)
    db.session.flush()

    log_audit('user.registered', 'User', user.id, after={'email': email, 'role': 'owner', 'business': business_name}, tenant_id=business.tenant_id, actor_type='system')
    log_audit('business.created', 'Business', business.id, after={'name': business_name, 'brand': brand_name}, tenant_id=business.tenant_id, actor_type='system')
    db.session.commit()

    login_user(user)
    return redirect(url_for('dashboard.index'))


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


# ─── RBAC DECORATOR ─────────────────────────────────────
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
