"""Gate AA — Registration 2-Step Wizard (GRM-006)."""
import pytest
from app import create_app, db
from app.models.entities import User, Business
from app.routes import auth as auth_mod
from flask_login import logout_user

TEST_EMAIL = 'gate_aa_test@example.com'


def _reset_rate_limiter():
    """Clear rate limiter state between tests."""
    auth_mod._rate_buckets.clear()
    auth_mod._registration_events.clear()


@pytest.fixture()
def app_context():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        _reset_rate_limiter()
        yield app
        db.session.remove()
        db.drop_all()
        _reset_rate_limiter()


def _client(app):
    return app.test_client()


def _post_step1(client, email=TEST_EMAIL, password='rahasia123', display_name='GateAA'):
    return client.post(
        '/auth/register',
        data={'step': '1', 'email': email, 'password': password, 'display_name': display_name},
        follow_redirects=False,
    )


def _post_step2(client, brand_name='GateBrand', business_name='', city='Jakarta'):
    return client.post(
        '/auth/register',
        data={'step': '2', 'brand_name': brand_name, 'business_name': business_name, 'city': city},
        follow_redirects=False,
    )


# ═══════════════════════════════════════════════════════════
# BASE FLOW
# ═══════════════════════════════════════════════════════════

def test_full_registration_flow(app_context):
    """End-to-end: step1 → step2 → auto-login → dashboard."""
    with app_context.app_context():
        c = _client(app_context)
        r1 = _post_step1(c)
        assert r1.status_code == 200
        assert 'Bisnis Anda' in r1.data.decode()

        r2 = _post_step2(c)
        assert r2.status_code == 302
        assert '/dashboard' in r2.headers['Location']

        # Verify DB
        user = User.query.filter_by(email=TEST_EMAIL).first()
        assert user is not None
        assert user.role == 'owner'
        assert user.business.brand_name == 'GateBrand'
        assert user.business.city == 'Jakarta'
        assert user.business.status == 'trialing'
        assert user.business.trial_ends_at is not None

        # Verify auto-login: can access dashboard
        r3 = c.get('/dashboard/')
        assert r3.status_code == 200


# ═══════════════════════════════════════════════════════════
# STEP 1 VALIDATION
# ═══════════════════════════════════════════════════════════

def test_get_step1_renders(app_context):
    with app_context.app_context():
        r = _client(app_context).get('/auth/register')
        assert r.status_code == 200
        html = r.data.decode()
        assert 'Buat Akun' in html
        assert 'Langkah 1 dari 2' in html


def test_step1_invalid_email(app_context):
    with app_context.app_context():
        r = _post_step1(_client(app_context), email='bukanemail')
        assert r.status_code == 400
        assert 'Email tidak valid' in r.data.decode()


def test_step1_short_password(app_context):
    with app_context.app_context():
        r = _post_step1(_client(app_context), password='123')
        assert r.status_code == 400
        assert 'Password minimal' in r.data.decode()


def test_step1_empty_name(app_context):
    with app_context.app_context():
        r = _post_step1(_client(app_context), display_name='')
        assert r.status_code == 400
        assert 'Nama wajib' in r.data.decode()


def test_step1_duplicate_email(app_context):
    with app_context.app_context():
        c = _client(app_context)
        # First registration
        _post_step1(c)
        _post_step2(c)
        # Logout so we can try again
        c.get('/auth/logout')

        # Second attempt with same email
        r = _post_step1(c)
        assert r.status_code == 400
        assert 'Email sudah terdaftar' in r.data.decode()


# ═══════════════════════════════════════════════════════════
# STEP 2 VALIDATION + NON-GOALS
# ═══════════════════════════════════════════════════════════

def test_step2_missing_brand(app_context):
    with app_context.app_context():
        c = _client(app_context)
        _post_step1(c)
        r = _post_step2(c, brand_name='')
        assert r.status_code == 400
        assert 'Nama brand' in r.data.decode()


def test_step2_missing_city(app_context):
    with app_context.app_context():
        c = _client(app_context)
        _post_step1(c)
        r = _post_step2(c, city='')
        assert r.status_code == 400
        assert 'Kota wajib' in r.data.decode()


def test_step2_no_session(app_context):
    with app_context.app_context():
        # Skip step1 → step2 should fail
        r = _post_step2(_client(app_context))
        assert r.status_code == 200
        html = r.data.decode()
        # Should redirect back to step1 or show error
        assert 'Langkah 1' in html or 'Sesi' in html


def test_business_name_optional(app_context):
    with app_context.app_context():
        c = _client(app_context)
        _post_step1(c)
        r = _post_step2(c, brand_name='OnlyBrand', business_name='')
        assert r.status_code == 302
        user = User.query.filter_by(email=TEST_EMAIL).first()
        assert user.business.name == 'OnlyBrand'


def test_no_email_verification_needed(app_context):
    with app_context.app_context():
        c = _client(app_context)
        _post_step1(c)
        _post_step2(c)
        r = c.get('/dashboard/')
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════
# NAVIGATION
# ═══════════════════════════════════════════════════════════

def test_already_logged_in_redirects(app_context):
    with app_context.app_context():
        c = _client(app_context)
        _post_step1(c)
        _post_step2(c)
        r = c.get('/auth/register', follow_redirects=False)
        assert r.status_code == 302
        assert '/dashboard' in r.headers['Location']


def test_wizard_resume_to_step2(app_context):
    with app_context.app_context():
        c = _client(app_context)
        _post_step1(c)
        r = c.get('/auth/register')
        assert r.status_code == 200
        assert 'Bisnis Anda' in r.data.decode()
        assert 'Langkah 2 dari 2' in r.data.decode()


def test_back_button_prefills(app_context):
    with app_context.app_context():
        c = _client(app_context)
        _post_step1(c, email='backtest@x.com', display_name='BackTest')
        r = c.get('/auth/register?back=1')
        assert r.status_code == 200
        html = r.data.decode()
        assert 'Buat Akun' in html
        assert 'backtest@x.com' in html
        assert 'BackTest' in html


# ═══════════════════════════════════════════════════════════
# RATE LIMIT
# ═══════════════════════════════════════════════════════════

def test_rate_limit_blocks_after_limit(app_context):
    with app_context.app_context():
        c = _client(app_context)
        for i in range(10):
            r = _post_step1(c, email=f'rt{i}@x.com')
            assert r.status_code in (200, 400), f'request {i}: {r.status_code}'
        # 11th should be rate limited
        r = _post_step1(c, email='rt11@x.com')
        assert r.status_code == 429
