"""Quality Gate HF-004 — Skip Activation Optimization.

Tests:
 HF004-01: Eligible user (has outlet) → skip succeeds → setup_complete=True
 HF004-02: Ineligible user (no outlet) → skip redirects to activation
 HF004-03: Already-complete user → skip redirects to dashboard (idempotent)
 HF004-04: No business user → skip redirects to dashboard (safety)
 HF004-05: Skip called twice → idempotent (no double state)
 HF004-06: Eligible user → skip link visible in welcome template
 HF004-07: Ineligible user → skip link hidden in welcome template
 HF004-08: Eligible user → skip link visible in activate template
 HF004-09: Ineligible user → skip link hidden in activate template
 HF004-10: Skip does not bypass auth (login_required)
 HF004-11: Skip does not cross tenant boundaries
 HF004-12: Existing activation flow not regressed
"""
import pytest
from app import create_app, db
from app.models.entities import User, Business, Outlet
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash

TEST_EMAIL = 'gate_hf004_test@example.com'
TEST_BRAND = 'TestHF004'
TEST_CITY = 'Jakarta'


@pytest.fixture()
def app_context():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _client(app):
    return app.test_client()


def _register_and_login(app, client, email=TEST_EMAIL, setup_complete=False,
                        expiring_days=14, progress=None, with_outlet=False):
    """Register a fresh trial user, login, return (user_id, business_id)."""
    with app.app_context():
        User.query.filter_by(email=email).delete()
        db.session.commit()
        user = User(
            email=email, display_name='GateHF004',
            password_hash=generate_password_hash('test123456'),
        )
        db.session.add(user)
        db.session.flush()
        business = Business(
            name=TEST_BRAND, brand_name=TEST_BRAND, city=TEST_CITY,
            status='trialing',
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=expiring_days),
            setup_complete=setup_complete,
            setup_progress=progress or {},
        )
        db.session.add(business)
        db.session.flush()
        user.business_id = business.id
        db.session.commit()
        uid, bid = user.id, business.id

        # Optionally create an outlet
        if with_outlet:
            outlet = Outlet(
                tenant_id=business.tenant_id, business_id=business.id,
                name='Test Outlet', address='Jl. Test No. 1',
                public_place_id='ChIJTest123',
                business_rating=4.5, business_review_count=100,
                monitor_enabled=True, source='public_scraping',
            )
            db.session.add(outlet)
            db.session.commit()

    with app.test_request_context():
        client.post('/auth/login', data={
            'email': email, 'password': 'test123456',
        })
    return uid, bid


# ═══════════════════════════════════════════════════════════
# ELIGIBLE USER → SKIP SUCCEEDS
# ═══════════════════════════════════════════════════════════

class TestHF004_EligibleSkip:

    def test_eligible_user_skip_succeeds(self, app_context):
        """HF004-01: User with outlet → skip → setup_complete=True."""
        app = app_context
        client = _client(app)
        _, bid = _register_and_login(app, client, with_outlet=True)

        resp = client.get('/trial/skip')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

        with app.app_context():
            b = db.session.get(Business, bid)
            assert b.setup_complete is True
            assert b.wow_moment_reached_at is not None


# ═══════════════════════════════════════════════════════════
# INELIGIBLE USER → REDIRECT TO ACTIVATION
# ═══════════════════════════════════════════════════════════

class TestHF004_IneligibleRedirect:

    def test_ineligible_user_redirected_to_activation(self, app_context):
        """HF004-02: User without outlet → skip → redirect to activation."""
        app = app_context
        client = _client(app)
        _, bid = _register_and_login(app, client, with_outlet=False)

        resp = client.get('/trial/skip')
        assert resp.status_code == 302
        assert '/trial/activate' in resp.headers['Location']

        with app.app_context():
            b = db.session.get(Business, bid)
            assert b.setup_complete is False


# ═══════════════════════════════════════════════════════════
# IDEMPOTENCY
# ═══════════════════════════════════════════════════════════

class TestHF004_Idempotency:

    def test_already_complete_redirects_to_dashboard(self, app_context):
        """HF004-03: Already-complete user → skip → dashboard (no-op)."""
        app = app_context
        client = _client(app)
        _, bid = _register_and_login(app, client, setup_complete=True)

        resp = client.get('/trial/skip')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

    def test_no_business_redirects_to_dashboard(self, app_context):
        """HF004-04: No business → skip → dashboard (safety)."""
        app = app_context
        client = _client(app)
        # Register but don't create business
        with app.app_context():
            User.query.filter_by(email=TEST_EMAIL).delete()
            db.session.commit()
            user = User(
                email=TEST_EMAIL, display_name='NoBiz',
                password_hash=generate_password_hash('test123456'),
            )
            db.session.add(user)
            db.session.commit()

        with app.test_request_context():
            client.post('/auth/login', data={
                'email': TEST_EMAIL, 'password': 'test123456',
            })

        resp = client.get('/trial/skip')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

    def test_skip_twice_idempotent(self, app_context):
        """HF004-05: Skip called twice → second is no-op redirect."""
        app = app_context
        client = _client(app)
        _, bid = _register_and_login(app, client, with_outlet=True)

        # First skip
        resp1 = client.get('/trial/skip')
        assert resp1.status_code == 302
        assert '/dashboard' in resp1.headers['Location']

        with app.app_context():
            b = db.session.get(Business, bid)
            assert b.setup_complete is True

        # Second skip — should be idempotent
        resp2 = client.get('/trial/skip')
        assert resp2.status_code == 302
        assert '/dashboard' in resp2.headers['Location']


# ═══════════════════════════════════════════════════════════
# TEMPLATE VISIBILITY
# ═══════════════════════════════════════════════════════════

class TestHF004_TemplateVisibility:

    def test_welcome_skip_visible_with_outlet(self, app_context):
        """HF004-06: Welcome page shows skip link when user has outlet."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, with_outlet=True)

        resp = client.get('/trial/welcome')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Lewati' in html

    def test_welcome_skip_hidden_without_outlet(self, app_context):
        """HF004-07: Welcome page hides skip link when user has no outlet."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, with_outlet=False)

        resp = client.get('/trial/welcome')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Lewati' not in html

    def test_activate_skip_visible_with_outlet(self, app_context):
        """HF004-08: Activate step1 shows skip link when user has outlet."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, with_outlet=True)

        resp = client.get('/trial/activate/step1')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Lewati' in html

    def test_activate_skip_hidden_without_outlet(self, app_context):
        """HF004-09: Activate step1 hides skip link when user has no outlet."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, with_outlet=False)

        resp = client.get('/trial/activate/step1')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Lewati' not in html


# ═══════════════════════════════════════════════════════════
# SECURITY
# ═══════════════════════════════════════════════════════════

class TestHF004_Security:

    def test_skip_requires_login(self, app_context):
        """HF004-10: Skip requires authentication."""
        app = app_context
        client = _client(app)

        resp = client.get('/trial/skip')
        # Should redirect to login (302) or return 401
        assert resp.status_code in (302, 401)

    def test_skip_tenant_isolation(self, app_context):
        """HF004-11: Skip only affects current user's business."""
        app = app_context
        client = _client(app)

        # Create user A with outlet
        _, bid_a = _register_and_login(app, client, email='user_a@test.com',
                                       with_outlet=True)

        # Create user B without outlet
        with app.app_context():
            user_b = User(
                email='user_b@test.com', display_name='UserB',
                password_hash=generate_password_hash('test123456'),
            )
            db.session.add(user_b)
            db.session.flush()
            biz_b = Business(
                name='BizB', brand_name='BizB', city='Jakarta',
                status='trialing',
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
                setup_complete=False,
            )
            db.session.add(biz_b)
            db.session.flush()
            user_b.business_id = biz_b.id
            db.session.commit()
            bid_b = biz_b.id

        # User A skips (eligible)
        resp = client.get('/trial/skip')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

        # Verify user A is setup_complete
        with app.app_context():
            a = db.session.get(Business, bid_a)
            assert a.setup_complete is True

            # Verify user B is NOT affected
            b = db.session.get(Business, bid_b)
            assert b.setup_complete is False


# ═══════════════════════════════════════════════════════════
# REGRESSION — EXISTING ACTIVATION FLOW
# ═══════════════════════════════════════════════════════════

class TestHF004_Regression:

    def test_activation_flow_not_regressed(self, app_context):
        """HF004-12: Existing activation flow still works."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, with_outlet=False)

        # Welcome loads
        resp = client.get('/trial/welcome')
        assert resp.status_code == 200

        # Activate redirects to step1
        resp = client.get('/trial/activate')
        assert resp.status_code == 302
        assert '/activate/step1' in resp.headers['Location']

        # Step1 loads
        resp = client.get('/trial/activate/step1')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Cari Outlet' in html or 'Cari' in html
