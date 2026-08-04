"""Gate AB — Trial Activation (GRM-007).

Tests: trial welcome after registration, dashboard lock, activation step
flow, progress memory, WOW moment, empty AI handling, skip functionality.

Must not touch GRM-001 through GRM-006 locked functionality.
"""
import pytest
from app import create_app, db
from app.models.entities import User, Business
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash

TEST_EMAIL = 'gate_ab_trial@example.com'
TEST_BRAND = 'TestTrialGate'
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
                        expiring_days=14, progress=None):
    """Register a fresh trial user, login, return (user_id, business_id)."""
    with app.app_context():
        User.query.filter_by(email=email).delete()
        db.session.commit()
        user = User(
            email=email, display_name='GateAB',
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

    with app.test_request_context():
        client.post('/auth/login', data={
            'email': email, 'password': 'test123456',
        })
    return uid, bid


# ═══════════════════════════════════════════════════════════
# WELCOME PAGE
# ═══════════════════════════════════════════════════════════

class TestGateAB_TrialWelcome:

    def test_welcome_loads_with_progress(self, app_context):
        """AC-6: Trial Welcome loads with progress checklist, trial status, CTA."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client)

        resp = client.get('/trial/welcome')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Checklist Aktivasi' in html
        assert 'Verifikasi' in html
        assert 'AI Advisor' in html
        assert 'MASA TRIAL' in html
        assert 'Mulai Aktivasi' in html or 'Lanjutkan' in html
        assert 'Lewati' in html

    def test_welcome_trial_status_active(self, app_context):
        """AC-7: Trial status 'Aktif' when >3 days remaining."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, expiring_days=14)

        resp = client.get('/trial/welcome')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Aktif' in html

    def test_welcome_trial_status_expiring(self, app_context):
        """AC-7: Trial status 'Segera Berakhir' when ≤3 days."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, expiring_days=2)

        resp = client.get('/trial/welcome')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Segera Berakhir' in html

    def test_welcome_trial_status_expired(self, app_context):
        """AC-7: Trial status 'Kedaluwarsa' when past trial_ends_at."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, expiring_days=-1)

        resp = client.get('/trial/welcome')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Kedaluwarsa' in html


# ═══════════════════════════════════════════════════════════
# DASHBOARD LOCK
# ═══════════════════════════════════════════════════════════

class TestGateAB_DashboardLock:

    def test_dashboard_redirects_when_not_setup(self, app_context):
        """AC-30: Dashboard redirects to /trial/welcome if not setup_complete."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, setup_complete=False)

        resp = client.get('/dashboard/')
        assert resp.status_code == 302
        assert '/trial/' in resp.headers['Location']  # /trial/welcome or /trial/activate

    def test_dashboard_accessible_after_setup(self, app_context):
        """AC-30: Dashboard works after setup_complete=True."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, setup_complete=True)

        # Must use fresh client session
        resp = client.get('/dashboard/')
        if resp.status_code == 302:
            assert '/trial/' not in resp.headers['Location']
        else:
            assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════
# SKIP
# ═══════════════════════════════════════════════════════════

class TestGateAB_Skip:

    def test_skip_sets_setup_complete(self, app_context):
        """Skip marks setup_complete=True, redirects to dashboard."""
        app = app_context
        client = _client(app)
        _, bid = _register_and_login(app, client, setup_complete=False)

        resp = client.get('/trial/skip')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

        with app.app_context():
            b = db.session.get(Business, bid)
            assert b.setup_complete is True


# ═══════════════════════════════════════════════════════════
# PROGRESS MEMORY
# ═══════════════════════════════════════════════════════════

class TestGateAB_ProgressMemory:

    def test_progress_persists_across_sessions(self, app_context):
        """AC-32: setup_progress persists and shows 'Lanjutkan' on welcome."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, progress={'step1': True, 'step2': True})

        resp = client.get('/trial/welcome')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Lanjutkan' in html


# ═══════════════════════════════════════════════════════════
# EMPTY AI HANDLING
# ═══════════════════════════════════════════════════════════

class TestGateAB_EmptyAIHandling:

    def test_wow_page_shows_empty_state(self, app_context):
        """AC-33: Step 4 with no reviews shows friendly empty state."""
        app = app_context
        client = _client(app)
        _register_and_login(app, client, progress={'step1': True, 'step2': True, 'step3': True})

        resp = client.get('/trial/activate/step4')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'masih terlalu sedikit' in html.lower() or 'siap' in html.lower()
