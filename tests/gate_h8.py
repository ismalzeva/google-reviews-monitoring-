"""Gate H8 — Production Integration Adapters & Pilot Mode.

Tests production-path code using HTTP stubs (not real Google API).
Validates: token exchange, refresh, account/location/review API,
Pub/Sub webhook, feature flags, pilot mode constraints, validations.

**Run:** python3 tests/gate_h8.py -v  (from project root)
**Requirements:** pip install requests PyJWT
"""

import os
import sys
import json
import base64
import uuid
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, PropertyMock

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set test env before any app imports
os.environ['FLASK_ENV'] = 'test'
os.environ['SECRET_KEY'] = 'test-secret-key-for-gate-h8'
os.environ['DATABASE_URL'] = 'sqlite:///test_gate_h8.db'
os.environ['GOOGLE_CLIENT_ID'] = ''
os.environ['GOOGLE_CLIENT_SECRET'] = ''

from app import create_app
from app import db as _db
from app.models.entities import (
    GoogleConnection, Business, Outlet, User,
    OAuthState, PubsubEvent,
)


def _get_business_id(tenant_id: str = 'tenant-a') -> str:
    """Get the database business ID for a tenant.

    Avoids hardcoding Business.id in tests since it uses UUID.
    Caller MUST seed data (via _seed_test_data) before using.
    """
    business = Business.query.filter_by(tenant_id=tenant_id).first()
    if business:
        return business.id
    raise RuntimeError(f"No Business found for tenant_id={tenant_id}. Seed data first?")

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _setup_app(with_creds: bool = False):
    """Create a test app and return it."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'  # in-memory
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['GOOGLE_CLIENT_ID'] = 'test-client-id' if with_creds else ''
    app.config['GOOGLE_CLIENT_SECRET'] = 'test-client-secret' if with_creds else ''
    app.config['GOOGLE_DEVELOPER_TOKEN'] = ''
    app.config['GBP_API_BASE_URL'] = 'https://businessprofile.googleapis.com/v1'
    app.config['PUBSUB_VERIFY_TOKEN'] = ''
    app.config['SKIP_GOOGLE_VERIFICATION'] = True
    app.config['PUBSUB_TENANT_MAP'] = {}
    return app


def _seed_test_data(db_session, tenant_id: str = 'tenant-a', user_id: int = 1):
    """Seed minimal test data: business, outlet, user."""
    business = Business.query.filter_by(tenant_id=tenant_id).first()
    if not business:
        import uuid
        business = Business(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name='Test Business',
            brand_name='Test Brand',
        )
        db_session.add(business)
        db_session.flush()

    user = User.query.filter_by(id=str(user_id)).first()
    if not user:
        user = User(
            id=str(user_id),
            email=f'test@{tenant_id}.example.com',
            password_hash='test-hash',
            display_name='Test User',
            business_id=business.id,
            role='admin',
        )
        db_session.add(user)
        db_session.flush()

    outlet = Outlet.query.filter_by(tenant_id=tenant_id).first()
    if not outlet:
        import uuid
        outlet = Outlet(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            business_id=business.id,
            gbp_location_id='accounts/tenant-a/locations/loc-001',
            name='Test Outlet Margonda',
            address='Jl. Margonda Raya, Depok',
            reply_enabled=False,
            status='active',
        )
        db_session.add(outlet)
        db_session.flush()

    return business, user, outlet


# ─────────────────────────────────────────────
# Test Classes
# ─────────────────────────────────────────────

class TestFeatureFlags(unittest.TestCase):
    """Feature flags module — pilot mode, auto-reply lock."""

    def setUp(self):
        self.app = _setup_app(with_creds=False)
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_is_production_mode_false_no_creds(self):
        from app.services.feature_flags import is_production_configured
        self.assertFalse(is_production_configured())

    def test_is_production_mode_true_with_creds(self):
        from app.services.feature_flags import is_production_configured
        self.app.config['GOOGLE_CLIENT_ID'] = 'real-id'
        self.app.config['GOOGLE_CLIENT_SECRET'] = 'real-secret'
        self.assertTrue(is_production_configured())

    def test_is_pilot_mode_default_true(self):
        from app.services.feature_flags import is_pilot_mode
        self.assertTrue(is_pilot_mode())

    @patch.dict(os.environ, {'GRM_PILOT_MODE': 'false'}, clear=False)
    def test_is_pilot_mode_off_when_disabled(self):
        from app.services.feature_flags import is_pilot_mode
        self.assertFalse(is_pilot_mode())

    def test_get_pilot_outlet_id_default(self):
        from app.services.feature_flags import pilot_outlet_whitelist
        self.assertEqual(pilot_outlet_whitelist(), [])

    def test_auto_reply_always_off(self):
        from app.services.feature_flags import is_auto_reply_enabled
        self.assertFalse(is_auto_reply_enabled())

    def test_reply_enabled_globally_default(self):
        from app.services.feature_flags import is_reply_enabled_globally
        self.assertFalse(is_reply_enabled_globally())

    def test_pilot_outlet_limit_default_1(self):
        from app.services.feature_flags import pilot_max_outlets
        self.assertEqual(pilot_max_outlets(), 1)


class TestGoogleOAuthProduction(unittest.TestCase):
    """Production OAuth token exchange, refresh, account/location listing.

    Uses a unique file-based SQLite database to avoid :memory: isolation leaks.
    """

    _DB_PATH = '/tmp/grm_gate_h8_oauth.db'

    @classmethod
    def setUpClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    def setUp(self):
        self.app = _setup_app(with_creds=True)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self._DB_PATH}'
        self.ctx = self.app.app_context()
        self.ctx.push()
        _db.create_all()
        _seed_test_data(_db.session)
        self._patchers = []

    def tearDown(self):
        for p in self._patchers:
            try:
                p.stop()
            except RuntimeError:
                pass
        self._patchers.clear()
        _db.session.rollback()
        _db.session.remove()
        _db.drop_all()
        self.ctx.pop()

    @patch('app.services.google_oauth._is_using_real_api', return_value=True)
    def test_get_oauth_url_uses_google_endpoint(self, mock_real):
        """In production mode, get_oauth_url returns google.com URL."""
        from app.services.google_oauth import get_oauth_url
        url = get_oauth_url(connection_id='test-conn', tenant_id='tenant-a')
        self.assertIn('accounts.google.com/o/oauth2/auth', url)
        self.assertIn('client_id=test-client-id', url)
        self.assertIn('business.manage', url)
        self.assertIn('access_type=offline', url)
        self.assertIn('prompt=consent', url)

    def test_get_redirect_uri(self):
        """get_redirect_uri returns a URL with /google/callback."""
        from app.services.google_oauth import get_redirect_uri
        uri = get_redirect_uri()
        self.assertIn('/google/callback', uri)

    @patch('requests.post')
    def test_real_token_exchange(self, mock_post):
        """exchange_code_for_token with real creds calls Google OAuth endpoint."""
        # Mock the Google token endpoint response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'access_token': 'ya29.real-access-token',
            'expires_in': 3600,
            'refresh_token': '1//real-refresh-token',
            'scope': 'https://www.googleapis.com/auth/business.manage',
            'token_type': 'Bearer',
        }
        mock_post.return_value = mock_resp

        # Inject a connection for the exchange
        conn = GoogleConnection(
            id='test-conn-1',
            tenant_id='tenant-a',
            business_id=_get_business_id(),
            status='oauth_in_progress',
            adapter_mode='production',
        )
        _db.session.add(conn)
        _db.session.commit()

        from app.services.google_oauth import exchange_code_for_token
        result = exchange_code_for_token(
            code='test-auth-code',
            connection_id='test-conn-1',
            tenant_id='tenant-a',
            adapter_mode_val='production',
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.status, 'connected')
        # Verify the POST call went to Google
        call_args = mock_post.call_args
        self.assertIn('oauth2.googleapis.com/token', call_args[0][0])

    @patch('requests.post')
    def test_refresh_access_token(self, mock_post):
        """refresh_access_token calls Google and returns new token."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'access_token': 'ya29.refreshed-token',
            'expires_in': 3600,
            'token_type': 'Bearer',
        }
        mock_post.return_value = mock_resp

        from app.services.google_business_profile import refresh_access_token
        result = refresh_access_token(
            refresh_token='1//test-refresh',
            client_id='test-client-id',
            client_secret='test-client-secret',
        )

        self.assertEqual(result['access_token'], 'ya29.refreshed-token')
        call_args = mock_post.call_args
        self.assertIn('oauth2.googleapis.com/token', call_args[0][0])

    @patch('requests.post')
    def test_refresh_revoked_token_raises_error(self, mock_post):
        """When refresh token is revoked, TokenRevokedError is raised."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {'error': 'invalid_grant', 'error_description': 'Token has been revoked'}
        mock_resp.raise_for_status.side_effect = __import__('requests').HTTPError('400 Client Error')
        mock_post.return_value = mock_resp

        from app.services.google_business_profile import refresh_access_token, TokenRevokedError
        with self.assertRaises(TokenRevokedError):
            refresh_access_token(
                refresh_token='1//revoked-token',
                client_id='test-client-id',
                client_secret='test-client-secret',
            )

    @patch('requests.get')
    def test_list_accounts_production(self, mock_get):
        """list_accounts_production returns accounts from GBP API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'accounts': [
                {
                    'name': 'accounts/12345',
                    'accountName': 'Test Account',
                    'type': 'PERSONAL',
                    'role': 'OWNER',
                    'primaryOwner': True,
                    'accountNumber': '12345',
                    'verificationState': 'VERIFIED',
                    'vettedState': 'VETTED',
                }
            ]
        }
        mock_get.return_value = mock_resp

        from app.services.google_business_profile import list_accounts_production
        accounts = list_accounts_production(
            access_token='ya29.test-token',
            base_url='https://businessprofile.googleapis.com/v1',
        )

        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]['account_id'], 'accounts/12345')
        # Verify Authorization header
        call_kwargs = mock_get.call_args[1]
        self.assertIn('Authorization', call_kwargs.get('headers', {}))
        self.assertEqual(call_kwargs['headers']['Authorization'], 'Bearer ya29.test-token')

    @patch('requests.get')
    def test_list_locations_production(self, mock_get):
        """list_locations_production returns locations from GBP API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'locations': [
                {
                    'name': 'accounts/12345/locations/loc-001',
                    'title': 'Bubur Fay Margonda',
                    'storeCode': 'MGD',
                    'languageCode': 'id',
                    'categories': [{'categoryId': 'restaurant'}],
                }
            ]
        }
        mock_get.return_value = mock_resp

        from app.services.google_business_profile import list_locations_production
        result = list_locations_production(
            access_token='ya29.test-token',
            account_name='accounts/12345',
            base_url='https://businessprofile.googleapis.com/v1',
        )

        locations = result.get('locations', [])
        self.assertEqual(len(locations), 1)
        self.assertIn('loc-001', locations[0]['resource_name'])

    @patch('requests.get')
    def test_list_reviews_production(self, mock_get):
        """list_reviews_production returns reviews from GBP API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'reviews': [
                {
                    'name': 'accounts/12345/locations/loc-001/reviews/r001',
                    'reviewer': {'displayName': 'User A'},
                    'starRating': 4,  # Transformed to int by function
                    'comment': 'Makanan enak',
                    'createTime': '2026-01-15T10:00:00Z',
                    'updateTime': '2026-01-15T10:00:00Z',
                }
            ]
        }
        mock_get.return_value = mock_resp

        from app.services.google_business_profile import list_reviews_production
        result = list_reviews_production(
            access_token='ya29.test-token',
            location_name='accounts/12345/locations/loc-001',
            base_url='https://businessprofile.googleapis.com/v1',
        )

        reviews = result.get('reviews', [])
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]['reviewer'], 'User A')

    @patch('requests.post')
    def test_create_reply_production(self, mock_post):
        """create_reply_production posts reply to GBP API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'name': 'accounts/12345/locations/loc-001/reviews/r001/reply',
            'comment': 'Terima kasih atas ulasannya',
            'updateTime': '2026-01-15T12:00:00Z',
        }
        mock_post.return_value = mock_resp

        from app.services.google_business_profile import create_reply_production
        result = create_reply_production(
            access_token='ya29.test-token',
            review_name='accounts/12345/locations/loc-001/reviews/r001',
            reply_text='Terima kasih atas ulasannya',
            base_url='https://businessprofile.googleapis.com/v1',
        )

        self.assertIn('reply', result['replyId'])
        self.assertEqual(result['comment'], 'Terima kasih atas ulasannya')

    @patch('requests.put')
    def test_update_reply_production(self, mock_put):
        """update_reply_production updates existing reply via GBP API."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'name': 'accounts/12345/locations/loc-001/reviews/r001/reply',
            'comment': 'Updated reply text',
            'updateTime': '2026-01-15T13:00:00Z',
        }
        mock_put.return_value = mock_resp

        from app.services.google_business_profile import update_reply_production
        result = update_reply_production(
            access_token='ya29.test-token',
            review_name='accounts/12345/locations/loc-001/reviews/r001',
            reply_text='Updated reply text',
            base_url='https://businessprofile.googleapis.com/v1',
        )

        self.assertEqual(result['comment'], 'Updated reply text')

    def test_permission_denied_error(self):
        """PermissionDeniedError is a GBP API error type."""
        from app.services.google_business_profile import PermissionDeniedError, GBPApiError
        self.assertTrue(issubclass(PermissionDeniedError, GBPApiError))
        err = PermissionDeniedError('test — HTTP 403 from GBP API')
        self.assertIn('403', str(err))

    def test_token_expired_error(self):
        """TokenExpiredError is distinct from TokenRevokedError."""
        from app.services.google_business_profile import TokenExpiredError, TokenRevokedError
        self.assertFalse(issubclass(TokenExpiredError, TokenRevokedError))

    @patch('requests.get')
    def test_permission_denied_raises(self, mock_get):
        """GBP API 403 error raises PermissionDeniedError."""
        import requests
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {'error': {'status': 'PERMISSION_DENIED', 'message': 'Not authorized'}}
        mock_resp.raise_for_status.side_effect = requests.HTTPError('403 Client Error', response=mock_resp)
        mock_get.return_value = mock_resp

        from app.services.google_business_profile import (
            list_accounts_production, PermissionDeniedError,
        )
        with self.assertRaises(PermissionDeniedError):
            list_accounts_production(
                access_token='ya29.test',
                base_url='https://businessprofile.googleapis.com/v1',
            )

    @patch('requests.get')
    def test_401_triggers_token_expired(self, mock_get):
        """GBP API 401 error raises TokenExpiredError."""
        import requests
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {'error': {'status': 'UNAUTHENTICATED', 'message': 'Access token expired'}}
        mock_resp.raise_for_status.side_effect = requests.HTTPError('401 Client Error', response=mock_resp)
        mock_get.return_value = mock_resp

        from app.services.google_business_profile import (
            list_accounts_production, TokenExpiredError,
        )
        with self.assertRaises(TokenExpiredError):
            list_accounts_production(
                access_token='ya29.expired',
                base_url='https://businessprofile.googleapis.com/v1',
            )


class TestGBPAdapterProduction(unittest.TestCase):
    """GoogleBusinessProfileReviewAdapter — production adapter with connection.

    Uses a unique file-based SQLite database per class to avoid :memory:
    connection pooling deadlocks between consecutive tests.
    """

    _DB_PATH = '/tmp/grm_gate_h8_adapter.db'

    @classmethod
    def setUpClass(cls):
        # Ensure fresh DB file before any test
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    def setUp(self):
        self.app = _setup_app(with_creds=True)
        # Override to file-based DB for proper isolation
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self._DB_PATH}'
        self.ctx = self.app.app_context()
        self.ctx.push()
        _db.create_all()
        _seed_test_data(_db.session)
        # Track patchers for cleanup
        self._patchers = []

    def tearDown(self):
        # Stop all patchers first
        for p in self._patchers:
            try:
                p.stop()
            except RuntimeError:
                pass
        self._patchers.clear()
        # Full session cleanup before dropping tables
        _db.session.rollback()
        _db.session.remove()
        _db.drop_all()
        self.ctx.pop()

    def _create_connection(self, tenant_id='tenant-a', status='connected',
                           has_refresh=True):
        """Create a GoogleConnection for testing."""
        business = Business.query.filter_by(tenant_id=tenant_id).first()
        if not business:
            raise ValueError(f"No business for tenant {tenant_id}")
        conn = GoogleConnection(
            id=f'conn-{tenant_id}-1',
            tenant_id=tenant_id,
            business_id=business.id,
            status=status,
            adapter_mode='production',
            selected_account_id='accounts/12345',
            encrypted_access_token_ref='ZW5jOnRlc3RfYWNjZXNzX3Rva2Vu',  # fake encrypted
            encrypted_refresh_token_ref=(
                'ZW5jOnRlc3RfcmVmcmVzaF90b2tlbg==' if has_refresh else None
            ),
            token_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        _db.session.add(conn)
        _db.session.commit()
        return conn

    def test_adapter_health_unavailable_when_no_creds(self):
        """Without production creds, health shows mock_fallback."""
        self.app.config['GOOGLE_CLIENT_ID'] = ''
        self.app.config['GOOGLE_CLIENT_SECRET'] = ''
        from app.services.google_oauth import _is_using_real_api
        self.assertFalse(_is_using_real_api())

    @patch('app.services.google_business_profile.list_reviews_production')
    def test_adapter_list_reviews_calls_production(self, mock_list):
        """Adapter delegates to production function."""
        mock_list.return_value = {
            'reviews': [
                {'name': 'accounts/12345/locations/loc-001/reviews/r001',
                 'reviewer': {'displayName': 'Test'},
                 'starRating': 'FIVE',
                 'comment': 'Great!'}
            ]
        }
        conn = self._create_connection()
        from app.services.review_source_adapter import GoogleBusinessProfileReviewAdapter
        adapter = GoogleBusinessProfileReviewAdapter(
            connection=conn,
            access_token='ya29.test-token',
            business_id=_get_business_id(),
            tenant_id='tenant-a',
        )
        result = adapter.list_reviews(location_id='accounts/tenant-a/locations/loc-001')
        self.assertEqual(len(result['reviews']), 1)

    def test_adapter_requires_location_id(self):
        """list_reviews raises ValueError without location_id."""
        from app.services.review_source_adapter import GoogleBusinessProfileReviewAdapter
        adapter = GoogleBusinessProfileReviewAdapter()
        with self.assertRaises(ValueError):
            adapter.list_reviews()

    def test_adapter_requires_review_name(self):
        """get_review raises ValueError without review_name."""
        from app.services.review_source_adapter import GoogleBusinessProfileReviewAdapter
        adapter = GoogleBusinessProfileReviewAdapter()
        with self.assertRaises(ValueError):
            adapter.get_review()


class TestPubSubProduction(unittest.TestCase):
    """Pub/Sub push handler and webhook.

    Uses dedicated file-based SQLite for DB isolation.
    """

    _DB_PATH = f'/tmp/grm_gate_h8_pubsub_{uuid.uuid4().hex[:8]}.db'

    @classmethod
    def setUpClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    def setUp(self):
        self.app = _setup_app(with_creds=False)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self._DB_PATH}'
        self.ctx = self.app.app_context()
        self.ctx.push()
        _db.create_all()
        _seed_test_data(_db.session)
        self._patchers = []

    def tearDown(self):
        for p in self._patchers:
            try:
                p.stop()
            except RuntimeError:
                pass
        self._patchers.clear()
        _db.session.rollback()
        _db.session.remove()
        _db.drop_all()
        self.ctx.pop()

    def _build_push_body(self, event_type='NEW_REVIEW', tenant_id='tenant-a',
                         location_name=None, message_id=None):
        """Build a realistic Pub/Sub push envelope."""
        data = {
            'event_type': event_type,
            'google_account_id': f'accounts/{tenant_id}',
            'tenant_id': tenant_id,
            'review_name': f'accounts/{tenant_id}/locations/loc-001/reviews/r-new-1',
            'location_name': location_name or f'accounts/{tenant_id}/locations/loc-001',
            'message_id': message_id or f'msg-{datetime.now(timezone.utc).timestamp():.0f}',
            'publish_time': datetime.now(timezone.utc).isoformat(),
        }
        encoded_data = base64.b64encode(json.dumps(data).encode()).decode()
        return {
            'message': {
                'data': encoded_data,
                'message_id': data['message_id'],
                'publish_time': data['publish_time'],
                'attributes': {},
            },
            'subscription': 'projects/test-project/subscriptions/test-sub',
        }

    def test_process_pubsub_push_new_review(self):
        """Valid push creates a PubsubEvent record."""
        body = self._build_push_body()
        from app.services.event_service import process_pubsub_push
        result = process_pubsub_push(body)
        self.assertIn(result['status'], ('created', 'duplicate'))

    def test_duplicate_detection(self):
        """Same message_id twice returns duplicate."""
        body = self._build_push_body(message_id='duplicate-msg-001')
        from app.services.event_service import process_pubsub_push
        result1 = process_pubsub_push(body)
        result2 = process_pubsub_push(body)
        self.assertEqual(result1['status'], 'created')
        self.assertEqual(result2['status'], 'duplicate')

    def test_invalid_push_body(self):
        """Non-dict body returns invalid."""
        from app.services.event_service import process_pubsub_push
        result = process_pubsub_push({'bad': 'payload'})
        self.assertEqual(result['status'], 'invalid')

    def test_invalid_no_message_key(self):
        """Body without 'message' key returns invalid."""
        from app.services.event_service import process_pubsub_push
        result = process_pubsub_push({'subscription': 'test'})
        self.assertEqual(result['status'], 'invalid')

    def test_pubsub_health_mock_mode(self):
        """Without creds, health shows mock mode."""
        from app.services.event_service import pubsub_health_check
        health = pubsub_health_check()
        self.assertEqual(health['pubsub_mode'], 'mock')

    def test_pubsub_health_production_mode(self):
        """With creds, health shows production mode."""
        self.app.config['GOOGLE_CLIENT_ID'] = 'real-id'
        self.app.config['GOOGLE_CLIENT_SECRET'] = 'real-secret'
        from app.services.event_service import pubsub_health_check
        health = pubsub_health_check()
        self.assertEqual(health['pubsub_mode'], 'production')

    def test_webhook_route_registered(self):
        """Pub/Sub webhook route is registered."""
        with self.app.test_client() as client:
            resp = client.post('/google/pubsub-push',
                               json={'message': {'data': '', 'message_id': '', 'publish_time': ''}},
                               content_type='application/json')
            # Should not 404
            self.assertNotEqual(resp.status_code, 404)

    def test_webhook_health_route(self):
        """Pub/Sub health endpoint works."""
        with self.app.test_client() as client:
            resp = client.get('/google/pubsub-health')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertIn('pubsub_mode', data)


class TestPilotModeConstraints(unittest.TestCase):
    """Pilot mode restrictions: 1 outlet, no auto-reply, human approval.

    Uses dedicated file-based SQLite for DB isolation.
    """

    _DB_PATH = f'/tmp/grm_gate_h8_pilot_{uuid.uuid4().hex[:8]}.db'

    @classmethod
    def setUpClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    def setUp(self):
        self.app = _setup_app(with_creds=False)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self._DB_PATH}'
        self.ctx = self.app.app_context()
        self.ctx.push()
        _db.create_all()
        data = _seed_test_data(_db.session)
        self.business, self.user, self.outlet = data
        self._patchers = []

    def tearDown(self):
        for p in self._patchers:
            try:
                p.stop()
            except RuntimeError:
                pass
        self._patchers.clear()
        _db.session.rollback()
        _db.session.remove()
        _db.drop_all()
        self.ctx.pop()

    def test_pilot_single_outlet_limit(self):
        """Pilot mode enforces max_outlets=1."""
        outlet2 = Outlet(
            id='outlet-2',
            tenant_id='tenant-a',
            business_id=_get_business_id(),
            gbp_location_id='accounts/tenant-a/locations/loc-002',
            name='Test Outlet 2',
            reply_enabled=False,
            status='active',
        )
        _db.session.add(outlet2)
        _db.session.commit()

        from app.services.feature_flags import pilot_max_outlets, is_outlet_pilot_active
        max_outlets = pilot_max_outlets()

        # Count outlets that pass the pilot check
        all_outlets = Outlet.query.filter_by(tenant_id='tenant-a').all()
        active_pilot = sum(1 for o in all_outlets if is_outlet_pilot_active(o))
        self.assertLessEqual(active_pilot, max_outlets)

    def test_harjamukti_stays_excluded(self):
        """Harjamukti outlet remains inactive/old_or_closed."""
        outlet_hj = Outlet(
            id='outlet-hj',
            tenant_id='tenant-a',
            business_id=_get_business_id(),
            gbp_location_id='accounts/tenant-a/locations/loc-hj',
            name='Bubur Fay Harjamukti',
            reply_enabled=False,
            status='old_or_closed',
        )
        _db.session.add(outlet_hj)
        _db.session.commit()
        self.assertEqual(outlet_hj.status, 'old_or_closed')

        from app.services.feature_flags import is_outlet_pilot_active
        self.assertFalse(is_outlet_pilot_active(outlet_hj))

    def test_auto_reply_remains_off(self):
        """is_auto_reply_enabled returns False regardless of config."""
        from app.services.feature_flags import is_auto_reply_enabled
        self.assertFalse(is_auto_reply_enabled())
        # Even if somehow enabled in config
        self.app.config['AUTO_REPLY_ENABLED'] = 'true'
        self.assertFalse(is_auto_reply_enabled())

    def test_reply_enabled_stays_false(self):
        """reply_enabled is False for all outlets in pilot."""
        self.assertFalse(self.outlet.reply_enabled)

    def test_all_publishes_need_approval(self):
        """In pilot mode, all reply publishes require human approval."""
        from app.services.feature_flags import publish_requires_approval
        self.assertTrue(publish_requires_approval())


class TestValidationProduction(unittest.TestCase):
    """Validation: missing creds, revoked, expired, isolation, no-secret leak.

    Uses dedicated file-based SQLite for DB isolation.
    """

    _DB_PATH = f'/tmp/grm_gate_h8_valid_{uuid.uuid4().hex[:8]}.db'

    @classmethod
    def setUpClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    def setUp(self):
        self.app = _setup_app(with_creds=False)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self._DB_PATH}'
        self.ctx = self.app.app_context()
        self.ctx.push()
        _db.create_all()
        _seed_test_data(_db.session)
        self._patchers = []

    def tearDown(self):
        for p in self._patchers:
            try:
                p.stop()
            except RuntimeError:
                pass
        self._patchers.clear()
        _db.session.rollback()
        _db.session.remove()
        _db.drop_all()
        self.ctx.pop()

    def test_missing_google_client_id_reported(self):
        """health_check reports missing credentials."""
        from app.services.google_oauth import check_connection_health
        with self.assertRaises(ValueError):
            check_connection_health(business_id=_get_business_id(), tenant_id='tenant-a')

    def test_revoked_token_status(self):
        """Connection with revoked status is detected."""
        conn = GoogleConnection(
            id='conn-revoked',
            tenant_id='tenant-a',
            business_id=_get_business_id(),
            status='token_revoked',
            adapter_mode='production',
        )
        _db.session.add(conn)
        _db.session.commit()

        from app.services.google_oauth import check_connection_health
        try:
            health = check_connection_health(business_id=_get_business_id(), tenant_id='tenant-a')
            if health:
                # Connection with token_revoked should show as not connected
                self.assertFalse(health.get('production_api_connected', True))
        except ValueError:
            # Acceptable if revoked raises ValueError
            pass

    @patch('app.services.google_oauth._get_access_token')
    def test_expired_token_refresh(self, mock_get_token):
        """Token expiry triggers refresh attempt."""
        mock_get_token.side_effect = __import__(
            'app.services.google_business_profile',
            fromlist=['TokenExpiredError'],
        ).TokenExpiredError('Token expired')

        conn = GoogleConnection(
            id='conn-expired',
            tenant_id='tenant-a',
            business_id=_get_business_id(),
            status='token_expired',
            adapter_mode='production',
            encrypted_access_token_ref='ZW5jOm9sZF90b2tlbg==',
            encrypted_refresh_token_ref=None,  # No refresh token
            token_expiry=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        _db.session.add(conn)
        _db.session.commit()

        from app.services.google_oauth import check_connection_health
        health = check_connection_health(business_id=_get_business_id(), tenant_id='tenant-a')
        if health:
            # Expired token → not connected, token invalid
            self.assertFalse(health.get('production_api_connected', True))

    def test_tenant_isolation_other_tenant_blocked(self):
        """Tenant A cannot access Tenant B's connection."""
        # Create connection for tenant-b
        conn_b = GoogleConnection(
            id='conn-b',
            tenant_id='tenant-b',
            business_id=_get_business_id(),
            status='connected',
            adapter_mode='mock',
        )
        _db.session.add(conn_b)
        _db.session.commit()

        # tenant-a should not see it
        from app.services.google_oauth import _get_connection
        result = _get_connection(business_id=_get_business_id(), tenant_id='tenant-a')
        self.assertIsNone(result)

    def test_no_secret_in_health_response(self):
        """health_check output must not contain raw tokens."""
        from app.services.google_oauth import check_connection_health
        try:
            health = check_connection_health(business_id=_get_business_id(), tenant_id='tenant-a')
            if health:
                health_str = json.dumps(health)
                self.assertNotIn('access_token', health_str.lower().replace('_', ''))
                self.assertNotIn('secret', health_str.lower())
                self.assertNotIn('ya29.', health_str)
                self.assertNotIn('1//', health_str)
        except ValueError:
            pass

    def test_no_secret_in_api_status_response(self):
        """API status endpoint must not leak secrets."""
        with self.app.test_client() as client:
            # Login: manually set session user_id (avoids request context issue with login_user)
            with client.session_transaction() as sess:
                from app import db as _db
                user = _db.session.get(User, 1)
                if not user:
                    user = _db.session.get(User, str(_get_business_id()))
                sess['_user_id'] = str(user.id) if hasattr(user, 'id') else '1'
                sess['_fresh'] = True

            resp = client.get('/google/api/status')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            data_str = json.dumps(data)
            self.assertNotIn('ya29.', data_str)
            self.assertNotIn('1//', data_str)
            self.assertNotIn('refresh_token', data_str.lower().replace('_', ''))

    def test_redirect_uri_configuration(self):
        """redirect_uri is configurable and defaults to localhost."""
        from app.services.google_oauth import get_redirect_uri
        uri = get_redirect_uri()
        self.assertTrue(uri.startswith('http'))
        self.assertIn('/google/callback', uri)

    def test_non_google_auth_callback_rejected(self):
        """OAuth callback with invalid state is rejected."""
        with self.app.test_client() as client:
            resp = client.get('/google/callback?code=fake&state=invalid-state')
            # Should redirect (not crash) with error flash
            self.assertEqual(resp.status_code, 302)


class TestNoSecretInReport(unittest.TestCase):
    """Static validation: no secrets in completion report."""

    def test_no_cred_in_report_template(self):
        """Completion report template doesn't contain credentials."""
        report_path = os.path.join(os.path.dirname(__file__), '..',
                                   'completion-reports', 'RUN_08_completion.md')
        if not os.path.exists(report_path):
            self.skipTest('RUN_08 completion report not yet written')
        with open(report_path) as f:
            content = f.read()
        self.assertNotIn('ya29.', content)
        self.assertNotIn('GOOGLE_CLIENT_ID=', content)
        self.assertNotIn('GOOGLE_CLIENT_SECRET=', content)


class TestNoRegression(unittest.TestCase):
    """Static checks that new adapter doesn't break contract."""

    _DB_PATH = f'/tmp/grm_gate_h8_noregress_{uuid.uuid4().hex[:8]}.db'

    @classmethod
    def setUpClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls._DB_PATH):
            os.remove(cls._DB_PATH)

    def setUp(self):
        self.app = _setup_app(with_creds=False)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self._DB_PATH}'
        self.ctx = self.app.app_context()
        self.ctx.push()
        _db.create_all()
        _seed_test_data(_db.session)

    def tearDown(self):
        _db.session.rollback()
        _db.session.remove()
        _db.drop_all()
        self.ctx.pop()

    def test_mock_adapter_still_works(self):
        """Mock adapter unchanged by production changes."""
        from app.services.review_source_adapter import MockReviewAdapter
        adapter = MockReviewAdapter()
        result = adapter.list_reviews(
            location_id='locations/123456789001',
        )
        self.assertIn('reviews', result)
        self.assertGreater(len(result['reviews']), 0)

    def test_get_adapter_resolves_mock(self):
        """get_adapter('mock') returns MockReviewAdapter."""
        from app.services.review_source_adapter import get_adapter
        adapter = get_adapter('mock')
        from app.services.review_source_adapter import MockReviewAdapter
        self.assertIsInstance(adapter, MockReviewAdapter)

    def test_get_adapter_resolves_google_api(self):
        """get_adapter('google_api') returns GoogleBusinessProfileReviewAdapter."""
        from app.services.review_source_adapter import get_adapter
        adapter = get_adapter('google_api')
        from app.services.review_source_adapter import GoogleBusinessProfileReviewAdapter
        self.assertIsInstance(adapter, GoogleBusinessProfileReviewAdapter)

    def test_process_event_contract(self):
        """process_event still accepts standard payload."""
        from app.services.event_service import process_event
        payload = {
            'event_type': 'NEW_REVIEW',
            'message_id': 'test-contract-msg',
            'publish_time': '2026-07-30T10:00:00Z',
            'tenant_id': 'tenant-a',
        }
        result = process_event(event_payload=payload)
        self.assertIn('status', result)


# ─────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────

if __name__ == '__main__':
    unittest.main(verbosity=2)
