"""Quality Gate HF-005 — Preview Binding.

Tests:
 HF005-01: Authenticated user with outlet → preview shows real data (tenant-scoped)
 HF005-02: Authenticated user without outlet → preview shows mock data
 HF005-03: Unauthenticated user → preview shows mock data (public)
 HF005-04: Cross-tenant: user A's outlet NOT visible to user B
 HF005-05: Tampered place_id → returns error page (no crash)
 HF005-06: Missing outlet → falls back to mock data
 HF005-07: Idempotency — same request returns same data
 HF005-08: Branch selector scoped to tenant (no cross-tenant outlets)
 HF005-09: Preview does not mutate production data
 HF005-10: get_preview_data() with tenant_id=None still works (backward compat)
 HF005-11: Preview page renders without error for authenticated user
 HF005-12: Preview page renders without error for unauthenticated user
"""
import pytest
from unittest.mock import patch, MagicMock
from app import create_app, db
from app.models.entities import User, Business, Outlet, Review
from app.services.preview import (
    get_preview_data, MockPreview, _query_real_outlet,
    _cache_key, _cache_get,
)
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash

TEST_EMAIL_A = 'gate_hf005_a@example.com'
TEST_EMAIL_B = 'gate_hf005_b@example.com'
TEST_BRAND = 'TestHF005'
TEST_CITY = 'Jakarta'
PLACE_ID = 'ChIJTestHF005Place1'
TEST_TENANT_A = None  # deprecated constant — tests resolve tenant_id at runtime


@pytest.fixture()
def app_context():
    """App fixture — HF-005 hardening.

    Setup/teardown each push their own app context, but NO app context is
    active while the test body runs. This forces every test-client request
    to push a FRESH app context (Flask 3 reuses a matching top-of-stack
    context otherwise), so `g` (incl. flask_login's cached _login_user) is
    per-request — matching production behaviour and preventing cross-client
    identity bleed INSIDE tests masking real leaks.
    """
    app = create_app('testing')
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def _client(app):
    return app.test_client()


def _create_user_with_outlet(app, email, place_id=PLACE_ID, tenant_id=None):
    """Create a user with business and outlet. Return (user_id, business_id, outlet_id)."""
    with app.app_context():
        User.query.filter_by(email=email).delete()
        db.session.commit()
        user = User(
            email=email, display_name='GateHF005',
            password_hash=generate_password_hash('test123456'),
        )
        db.session.add(user)
        db.session.flush()
        business = Business(
            name=TEST_BRAND, brand_name=TEST_BRAND, city=TEST_CITY,
            status='trialing',
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
            setup_complete=True,
        )
        if tenant_id:
            business.tenant_id = tenant_id
        db.session.add(business)
        db.session.flush()
        user.business_id = business.id
        db.session.commit()

        outlet = Outlet(
            tenant_id=business.tenant_id, business_id=business.id,
            name='Test Outlet HF005', address='Jl. Test No. 1',
            public_place_id=place_id,
            business_rating=4.5, business_review_count=100,
            monitor_enabled=True, source='public_scraping',
        )
        db.session.add(outlet)
        db.session.commit()

        # Add some reviews
        for i in range(5):
            review = Review(
                tenant_id=business.tenant_id, business_id=business.id,
                outlet_id=outlet.id, source='test',
                source_review_name=f'review_{i}',
                star_rating=5 if i < 3 else 2,
                comment='Bagus' if i < 3 else 'Lambat pelayanannya',
            )
            db.session.add(review)
        db.session.commit()

        return user.id, business.id, outlet.id


def _login(client, email):
    """Login a user."""
    client.post('/auth/login', data={
        'email': email, 'password': 'test123456',
    })


# ═══════════════════════════════════════════════════════════
# AUTHENTICATED USER WITH OUTLET → REAL DATA
# ═══════════════════════════════════════════════════════════

class TestHF005_AuthenticatedRealData:

    def test_authenticated_user_sees_real_data(self, app_context):
        """HF005-01: Authenticated user with outlet → preview shows real data."""
        app = app_context
        client = _client(app)
        uid, bid, oid = _create_user_with_outlet(app, TEST_EMAIL_A)
        _login(client, TEST_EMAIL_A)

        resp = client.get(f'/preview?place_id={PLACE_ID}')
        assert resp.status_code == 200
        # Real data should show the outlet name
        assert b'Test Outlet HF005' in resp.data


# ═══════════════════════════════════════════════════════════
# AUTHENTICATED USER WITHOUT OUTLET → MOCK DATA
# ═══════════════════════════════════════════════════════════

class TestHF005_AuthenticatedNoOutlet:

    def test_authenticated_user_without_outlet_sees_mock(self, app_context):
        """HF005-02: Authenticated user without outlet → preview shows mock data."""
        app = app_context
        client = _client(app)

        # Create user without outlet
        with app.app_context():
            user = User(
                email=TEST_EMAIL_B, display_name='GateHF005B',
                password_hash=generate_password_hash('test123456'),
            )
            db.session.add(user)
            db.session.flush()
            business = Business(
                name='OtherBrand', brand_name='OtherBrand', city=TEST_CITY,
                status='trialing',
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
            )
            db.session.add(business)
            db.session.flush()
            user.business_id = business.id
            db.session.commit()

        _login(client, TEST_EMAIL_B)

        # Use a place_id that exists in MOCK_BRANCHES
        resp = client.get('/preview?place_id=ChIJ0_depok-margonda-001')
        assert resp.status_code == 200
        assert b'Bubur Fay Depok' in resp.data  # mock data


# ═══════════════════════════════════════════════════════════
# UNAUTHENTICATED USER → MOCK DATA
# ═══════════════════════════════════════════════════════════

class TestHF005_UnauthenticatedMock:

    def test_unauthenticated_user_sees_mock_data(self, app_context):
        """HF005-03: Unauthenticated user → preview shows mock data."""
        app = app_context
        client = _client(app)

        resp = client.get('/preview?place_id=ChIJ0_depok-margonda-001')
        assert resp.status_code == 200
        assert b'Bubur Fay Depok' in resp.data


# ═══════════════════════════════════════════════════════════
# CROSS-TENANT ISOLATION
# ═══════════════════════════════════════════════════════════

class TestHF005_CrossTenantIsolation:

    def test_cross_tenant_outlet_not_visible(self, app_context):
        """HF005-04: User A's outlet NOT visible to user B via preview page."""
        app = app_context
        client = _client(app)

        # Create user A with outlet
        uid_a, bid_a, oid_a = _create_user_with_outlet(app, TEST_EMAIL_A, PLACE_ID)

        # Create user B (different tenant)
        uid_b, bid_b, oid_b = _create_user_with_outlet(
            app, TEST_EMAIL_B, 'ChIJOtherPlace', tenant_id='tenant-b-custom'
        )

        # Login as user B
        _login(client, TEST_EMAIL_B)

        # User B tries to see User A's outlet data
        resp = client.get(f'/preview?place_id={PLACE_ID}')
        assert resp.status_code == 200

        # Should NOT show User A's real data
        assert b'Test Outlet HF005' not in resp.data, \
            "Cross-tenant data leakage detected!"


# ═══════════════════════════════════════════════════════════
# TAMPERED PLACE ID
# ═══════════════════════════════════════════════════════════

class TestHF005_TamperedPlaceId:

    def test_tampered_place_id_no_crash(self, app_context):
        """HF005-05: Tampered place_id → no crash, returns error page."""
        app = app_context
        client = _client(app)

        # SQL injection attempt
        resp = client.get("/preview?place_id='; DROP TABLE outlets; --")
        assert resp.status_code in (200, 302, 400)

        # XSS attempt
        resp = client.get('/preview?place_id=<script>alert(1)</script>')
        assert resp.status_code in (200, 302, 400)

        # Empty string
        resp = client.get('/preview?place_id=')
        assert resp.status_code in (200, 302)

        # Very long string
        resp = client.get(f'/preview?place_id={"A" * 1000}')
        assert resp.status_code in (200, 302, 400)


# ═══════════════════════════════════════════════════════════
# MISSING OUTLET → FALLBACK
# ═══════════════════════════════════════════════════════════

class TestHF005_MissingOutletFallback:

    def test_missing_outlet_falls_back_to_mock(self, app_context):
        """HF005-06: Outlet not found → falls back to mock data."""
        app = app_context
        client = _client(app)

        # Non-existent place_id
        resp = client.get('/preview?place_id=ChIJNonExistent999')
        assert resp.status_code == 200
        # Should show "data tidak tersedia" error
        assert b'belum tersedia' in resp.data or b'Tidak ada data' in resp.data

        # Place ID that exists in mock
        resp = client.get('/preview?place_id=ChIJ0_depok-margonda-001')
        assert resp.status_code == 200
        assert b'Bubur Fay Depok' in resp.data


# ═══════════════════════════════════════════════════════════
# IDEMPOTENCY
# ═══════════════════════════════════════════════════════════

class TestHF005_Idempotency:

    def test_same_request_returns_same_data(self, app_context):
        """HF005-07: Same request returns same data (idempotent)."""
        app = app_context
        client = _client(app)
        uid, bid, oid = _create_user_with_outlet(app, TEST_EMAIL_A)
        _login(client, TEST_EMAIL_A)

        resp1 = client.get(f'/preview?place_id={PLACE_ID}')
        resp2 = client.get(f'/preview?place_id={PLACE_ID}')

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.data == resp2.data


# ═══════════════════════════════════════════════════════════
# BRANCH SELECTOR TENANT SCOPING
# ═══════════════════════════════════════════════════════════

class TestHF005_BranchSelectorScoping:

    def test_branch_selector_scoped_to_tenant(self, app_context):
        """HF005-08: Branch selector only shows outlets from same tenant."""
        app = app_context
        client = _client(app)

        # Create user A with 2 outlets
        uid_a, bid_a, oid_a = _create_user_with_outlet(app, TEST_EMAIL_A, PLACE_ID)

        with app.app_context():
            business_a = db.session.get(Business, bid_a)
            # Add second outlet in same tenant
            outlet2 = Outlet(
                tenant_id=business_a.tenant_id, business_id=business_a.id,
                name='Test Outlet 2', address='Jl. Test No. 2',
                public_place_id='ChIJTestHF005Place2',
                business_rating=4.0, business_review_count=50,
                monitor_enabled=True, source='public_scraping',
            )
            db.session.add(outlet2)
            db.session.commit()

        # Create user B with outlet (different tenant)
        uid_b, bid_b, oid_b = _create_user_with_outlet(
            app, TEST_EMAIL_B, 'ChIJOtherPlaceB'
        )

        # Login as user A
        _login(client, TEST_EMAIL_A)

        resp = client.get(f'/preview?place_id={PLACE_ID}')
        assert resp.status_code == 200

        # Branch selector should NOT contain user B's outlet
        assert b'ChIJOtherPlaceB' not in resp.data, \
            "Cross-tenant outlet leaked into branch selector!"


# ═══════════════════════════════════════════════════════════
# NO PRODUCTION DATA MUTATION
# ═══════════════════════════════════════════════════════════

class TestHF005_NoMutation:

    def test_preview_does_not_mutate_data(self, app_context):
        """HF005-09: Preview does not mutate production data."""
        app = app_context
        client = _client(app)
        uid, bid, oid = _create_user_with_outlet(app, TEST_EMAIL_A)
        _login(client, TEST_EMAIL_A)

        with app.app_context():
            outlet_count_before = Outlet.query.count()
            review_count_before = Review.query.count()
            user_count_before = User.query.count()

        # Call preview multiple times
        for _ in range(3):
            client.get(f'/preview?place_id={PLACE_ID}')

        with app.app_context():
            outlet_count_after = Outlet.query.count()
            review_count_after = Review.query.count()
            user_count_after = User.query.count()

        assert outlet_count_before == outlet_count_after, "Outlet count changed!"
        assert review_count_before == review_count_after, "Review count changed!"
        assert user_count_before == user_count_after, "User count changed!"


# ═══════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════

class TestHF005_BackwardCompatibility:

    def test_get_preview_data_without_tenant_id_is_fail_closed(self, app_context):
        """HF005-10: tenant_id=None is FAIL-CLOSED — mock only, no real query.

        Even when an outlet with matching place_id EXISTS in the DB,
        a caller without tenant_id must NOT receive real data. The function
        must not select any tenant's outlet and must fall back to static
        mock data only.
        """
        app = app_context
        with app.app_context():
            # Create a real outlet with reviews that COULD match
            uid, bid, oid = _create_user_with_outlet(app, TEST_EMAIL_A, PLACE_ID)
            tenant_a_id = db.session.get(Business, bid).tenant_id

            # 1. Real data WITH tenant_id → outlet owner sees real data
            preview_scoped = get_preview_data(PLACE_ID, tenant_id=tenant_a_id)
            assert preview_scoped is not None
            assert preview_scoped.display_name == 'Test Outlet HF005', \
                "tenant-scoped call should return real data"

            # 2. Same place_id WITHOUT tenant_id → FAIL-CLOSED to mock/None.
            #    Must NOT return the real outlet even though it exists in DB.
            preview_unscoped = get_preview_data(PLACE_ID, tenant_id=None)
            if preview_unscoped is not None:
                assert preview_unscoped.display_name != 'Test Outlet HF005', \
                    "FAIL-CLOSED VIOLATED: unscoped call returned real tenant data!"
                # Only acceptable content is static mock data
                assert preview_unscoped.place_id.startswith('ChIJ0_'), \
                    "Unscoped call returned non-mock data"

            # 3. _query_real_outlet directly without tenant_id → refused
            refused = _query_real_outlet(app, PLACE_ID, tenant_id=None)
            assert refused is None, "fail-closed: no tenant_id must return None"

            # 4. Wrong tenant gets nothing (isolation still holds)
            wrong_tenant = get_preview_data(PLACE_ID, tenant_id='tenant-other')
            assert wrong_tenant is None or \
                wrong_tenant.display_name != 'Test Outlet HF005', \
                "cross-tenant leak via get_preview_data"


class TestHF005_CacheIsolation:

    def test_cache_keys_are_tenant_scoped(self, app_context):
        """HF005-13: Tenant-scoped cache key cannot collide across tenants."""
        app = app_context
        with app.app_context():
            key_a = _cache_key('ChIJX', 'tenant-a-uuid-1234')
            key_b = _cache_key('ChIJX', 'tenant-b-uuid')
            key_anon = _cache_key('ChIJX')

            assert key_a != key_b, "tenant A/B cache keys collide!"
            assert key_a != key_anon, "tenant key collides with anonymous key!"
            assert key_b != key_anon, "tenant B key collides with anonymous key!"
            assert 'tenant-a-uuid-1234' in key_a

    def test_real_data_not_served_via_anonymous_cache(self, app_context):
        """HF005-14: Real tenant data never enters anonymous cache namespace."""
        app = app_context
        client = _client(app)
        uid, bid, oid = _create_user_with_outlet(app, TEST_EMAIL_A, PLACE_ID)
        with app.app_context():
            tenant_a_id = db.session.get(Business, bid).tenant_id

        # Owner fetches → real data cached under TENANT key
        _login(client, TEST_EMAIL_A)
        resp = client.get(f'/preview?place_id={PLACE_ID}')
        assert resp.status_code == 200
        assert b'Test Outlet HF005' in resp.data

        with app.app_context():
            anon_cached = _cache_get(PLACE_ID, None)  # anonymous namespace
            tenant_cached = _cache_get(PLACE_ID, tenant_a_id)

            # Anonymous namespace must NOT hold the real outlet's name
            if anon_cached:
                assert anon_cached.get('display_name') != 'Test Outlet HF005', \
                    "CACHE POISONING: real data leaked into anonymous cache!"

            # Tenant namespace should hold it (or be absent — both fine)
            if tenant_cached:
                assert tenant_cached.get('display_name') == 'Test Outlet HF005'

        # Fresh anonymous client cannot see tenant data
        anon_client = _client(app)
        resp2 = anon_client.get(f'/preview?place_id={PLACE_ID}')
        assert resp2.status_code == 200
        assert b'Test Outlet HF005' not in resp2.data, \
            "Anonymous user received tenant-scoped real data!"


# ═══════════════════════════════════════════════════════════
# PREVIEW PAGE RENDERING
# ═══════════════════════════════════════════════════════════

class TestHF005_PreviewPageRendering:

    def test_preview_page_renders_for_authenticated_user(self, app_context):
        """HF005-11: Preview page renders without error for authenticated user."""
        app = app_context
        client = _client(app)
        uid, bid, oid = _create_user_with_outlet(app, TEST_EMAIL_A)
        _login(client, TEST_EMAIL_A)

        resp = client.get(f'/preview?place_id={PLACE_ID}')
        assert resp.status_code == 200
        assert b'Test Outlet HF005' in resp.data

    def test_preview_page_renders_for_unauthenticated_user(self, app_context):
        """HF005-12: Preview page renders without error for unauthenticated user."""
        app = app_context
        client = _client(app)

        resp = client.get('/preview?place_id=ChIJ0_depok-margonda-001')
        assert resp.status_code == 200
        assert b'Bubur Fay Depok' in resp.data
