"""Quality Gate HF-006 — Sinkronkan Outlet Trial → Dashboard.

Tests:
 HF006-01: Trial step3 sync uses public provider path → reviews land in DB (tenant-scoped)
 HF006-02: After successful sync + activation, dashboard data shows reviews > 0
 HF006-03: Cross-tenant: syncing tenant A's outlet never touches tenant B data
 HF006-04: Idempotency — second full sync run creates no duplicate reviews
 HF006-05: Double-click/retry on start → single task, no parallel duplicate spawn
 HF006-06: Unknown place at provider → friendly error, no crash, no partial write
 HF006-07: Progress endpoint safe for unknown task ids (no 500)
 HF006-08: Worker thread uses captured primitives (structural guard)
 HF006-09: No silent mock fallback — source label matches adapter.source_name
 HF006-10: setup_progress step3 marked done only after a successful sync
"""
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review, SyncReport
from app.routes.trial import _SYNC_PROGRESS


TEST_EMAIL_A = 'gate_hf006_a@example.com'
TEST_EMAIL_B = 'gate_hf006_b@example.com'
TEST_EMAIL_F = 'gate_hf006_fail@example.com'
TEST_EMAIL_S = 'gate_hf006_ok@example.com'
TEST_BRAND = 'TestHF006'
PLACE_A = 'ChIJHF006PlaceA'
PLACE_B = 'ChIJHF006PlaceB'
PLACE_UNKNOWN = 'ChIJHF006Unknown'

POLL_N = 60


@pytest.fixture()
def app_context():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
    _SYNC_PROGRESS.clear()


@pytest.fixture(autouse=True)
def _clean_progress():
    yield
    _SYNC_PROGRESS.clear()


def _client(app):
    return app.test_client()


def _login(client, email):
    return client.post('/auth/login', data={
        'email': email, 'password': 'test123456',
    }, follow_redirects=False)


def _mk_user(app, email, place_id):
    """Create user+business(trialing)+outlet without gbp_location_id.

    Returns (biz_id, tenant_id, outlet_id).
    """
    with app.app_context():
        User.query.filter_by(email=email).delete()
        db.session.commit()
        user = User(
            email=email, display_name='GateHF006',
            password_hash=generate_password_hash('test123456'),
        )
        db.session.add(user)
        db.session.flush()
        biz = Business(
            name=TEST_BRAND, brand_name=TEST_BRAND, city='Depok',
            status='trialing',
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
            setup_complete=False,
            setup_started_at=datetime.now(timezone.utc),
            setup_progress=json.dumps({'step1': 'done', 'step2': 'done'}),
        )
        db.session.add(biz)
        db.session.flush()
        user.business_id = biz.id
        outlet = Outlet(
            tenant_id=biz.tenant_id, business_id=biz.id,
            name=f'Outlet {place_id}', address='Jl. Test No. 1',
            public_place_id=place_id,
            business_rating=4.5, business_review_count=3,
            monitor_enabled=True, source='public_scraping',
            # NOTE: deliberately NO gbp_location_id — trial outlets never have one.
        )
        db.session.add(outlet)
        db.session.commit()
        return biz.id, biz.tenant_id, outlet.id


def _mk_adapter(ok_places=(PLACE_A,), n_reviews=3):
    """MagicMock standing in for the configured public review adapter.

    Contract-faithful: raises ValueError for unknown places (no fabricated
    data), returns complete geo metadata so no network enrichment happens.
    """
    adapter = MagicMock()
    adapter.source_name = 'mock'
    base = datetime.now(timezone.utc)

    def _reviews():
        out = []
        for i in range(n_reviews):
            out.append({
                'source_review_id': f'rev-{i:03d}',
                'rating': 5 if i % 2 == 0 else 2,
                'review_text': f'Teks review uji {i}',
                'review_date': (base - timedelta(days=i)).isoformat(),
                'review_datetime_raw': f'day -{i}',
                'owner_reply_text': None,
                'owner_reply_date': None,
                'source': 'mock',
                'source_url': f'https://maps.example/{i}',
                'reviewer_name_masked': f'Anonim {i}',
                'raw_payload': {'k': i},
            })
        return out

    def _list_reviews(place_id, since=None, limit=100, **kw):
        if place_id not in ok_places:
            raise ValueError(f'unknown place: {place_id}')
        return [dict(r) for r in _reviews()]

    def _fetch_location(place_id):
        if place_id not in ok_places:
            raise ValueError(f'unknown place: {place_id}')
        return {
            'place_id': place_id, 'business_name': 'Uji',
            'full_address': 'Jl. Uji 1, Kec. Beji, Kota Depok, Jawa Barat',
            'latitude': -6.4, 'longitude': 106.8,
            'maps_url': 'https://maps.example',
            'business_rating': 4.5, 'business_review_count': n_reviews,
            'province': 'Jawa Barat', 'city_regency': 'Kota Depok',
            'district': 'Beji', 'source': 'mock',
        }

    adapter.list_reviews_by_place_id.side_effect = _list_reviews
    adapter.fetch_location.side_effect = _fetch_location
    return adapter


def _run_step3_sync(client, outlet_id, expect_status=True):
    """Start step3 sync and poll until terminal status. Returns progress."""
    with client.session_transaction() as sess:
        sess['trial_outlet_id'] = outlet_id
    rv = client.post('/trial/activate/step3/start')
    assert rv.status_code == 200, rv.get_data(as_text=True)
    body = rv.get_json()
    assert isinstance(body.get('task_id'), str)
    prog = {}
    for _ in range(POLL_N):
        pr = client.get(f"/trial/activate/step3/progress/{body['task_id']}")
        assert pr.status_code == 200
        prog = pr.get_json()
        if prog.get('status') in ('done', 'error'):
            break
        time.sleep(0.05)
    return prog


# ─── HF006-01 ──────────────────────────────────────────────────────────
def test_01_step3_sync_public_path_stores_reviews(app_context):
    app = app_context
    biz_id, tenant_a, outlet_id = _mk_user(app, TEST_EMAIL_A, PLACE_A)
    adapter = _mk_adapter()

    with patch('app.services.public_provider.build_public_review_adapter', return_value=adapter):
        client = _client(app)
        assert _login(client, TEST_EMAIL_A).status_code in (302, 303)
        prog = _run_step3_sync(client, outlet_id)
        assert prog['status'] == 'done', prog

    with app.app_context():
        stored = Review.query.filter_by(
            tenant_id=tenant_a, business_id=biz_id, outlet_id=outlet_id,
        ).all()
        assert len(stored) == 3
        assert all(r.tenant_id == tenant_a for r in stored)


# ─── HF006-02 ──────────────────────────────────────────────────────────
def test_02_dashboard_data_shows_synced_reviews(app_context):
    app = app_context
    biz_id, tenant_a, outlet_id = _mk_user(app, TEST_EMAIL_A, PLACE_A)
    adapter = _mk_adapter()

    with patch('app.services.public_provider.build_public_review_adapter', return_value=adapter):
        client = _client(app)
        assert _login(client, TEST_EMAIL_A).status_code in (302, 303)
        prog = _run_step3_sync(client, outlet_id)
        assert prog['status'] == 'done'
        # Complete activation (step4 sets setup_complete) then open dashboard
        client.get('/trial/activate/step4')
        page = client.get('/dashboard/')
        assert page.status_code == 200

    with app.app_context():
        from app.services.public_analytics import parse_filters, executive_summary
        biz = Business.query.get(biz_id)
        summary = executive_summary(biz.tenant_id, biz.id, parse_filters({}))
        # THE bug: before fix this is 0 because trial sync used the GBP path
        assert summary.get('total_reviews', 0) > 0


# ─── HF006-03 ──────────────────────────────────────────────────────────
def test_03_cross_tenant_isolation(app_context):
    app = app_context
    biz_a, tenant_a, outlet_a = _mk_user(app, TEST_EMAIL_A, PLACE_A)
    biz_b, tenant_b, outlet_b = _mk_user(app, TEST_EMAIL_B, PLACE_B)
    assert tenant_a != tenant_b
    adapter = _mk_adapter()

    with patch('app.services.public_provider.build_public_review_adapter', return_value=adapter):
        client = _client(app)
        assert _login(client, TEST_EMAIL_A).status_code in (302, 303)
        prog = _run_step3_sync(client, outlet_a)
        assert prog['status'] == 'done'

    with app.app_context():
        assert Review.query.filter_by(tenant_id=tenant_a).count() == 3
        assert Review.query.filter_by(tenant_id=tenant_b).count() == 0
        out_b = Outlet.query.get(outlet_b)
        assert out_b.business_rating == 4.5  # untouched by A's sync


# ─── HF006-04 ──────────────────────────────────────────────────────────
def test_04_idempotent_resync_no_duplicates(app_context):
    app = app_context
    biz_id, tenant_a, outlet_id = _mk_user(app, TEST_EMAIL_A, PLACE_A)
    adapter = _mk_adapter()

    with patch('app.services.public_provider.build_public_review_adapter', return_value=adapter):
        client = _client(app)
        assert _login(client, TEST_EMAIL_A).status_code in (302, 303)

        prog1 = _run_step3_sync(client, outlet_id)
        assert prog1['status'] == 'done'
        with app.app_context():
            c1 = Review.query.filter_by(outlet_id=outlet_id).count()
            assert c1 == 3

        # Retry/re-click: same fixed review ids → upsert, NOT new inserts
        prog2 = _run_step3_sync(client, outlet_id)
        assert prog2['status'] == 'done'
        with app.app_context():
            c2 = Review.query.filter_by(outlet_id=outlet_id).count()
        assert c1 == c2 == 3


# ─── HF006-05 ──────────────────────────────────────────────────────────
def test_05_double_start_single_task(app_context):
    app = app_context
    biz_id, tenant_a, outlet_id = _mk_user(app, TEST_EMAIL_A, PLACE_A)
    adapter = _mk_adapter()

    with patch('app.services.public_provider.build_public_review_adapter', return_value=adapter):
        client = _client(app)
        assert _login(client, TEST_EMAIL_A).status_code in (302, 303)
        with client.session_transaction() as sess:
            sess['trial_outlet_id'] = outlet_id

        r1 = client.post('/trial/activate/step3/start').get_json()
        r2 = client.post('/trial/activate/step3/start').get_json()
        assert r1['task_id'] == r2['task_id']

        prog = {}
        for _ in range(POLL_N):
            prog = client.get(f"/trial/activate/step3/progress/{r1['task_id']}").get_json()
            if prog.get('status') in ('done', 'error'):
                break
            time.sleep(0.05)
        assert prog['status'] == 'done'


# ─── HF006-06 ──────────────────────────────────────────────────────────
def test_06_unknown_place_friendly_error_no_partial_write(app_context):
    app = app_context
    biz_id, tenant_a, outlet_id = _mk_user(app, TEST_EMAIL_A, PLACE_UNKNOWN)
    adapter = _mk_adapter()  # PLACE_UNKNOWN → ValueError at provider level

    with patch('app.services.public_provider.build_public_review_adapter', return_value=adapter):
        client = _client(app)
        assert _login(client, TEST_EMAIL_A).status_code in (302, 303)
        prog = _run_step3_sync(client, outlet_id)
        assert prog['status'] == 'error', prog
        msg = (prog.get('error') or '').lower()
        assert ('sinkronisasi' in msg) or ('gagal' in msg)
        assert 'traceback' not in msg
        assert 'valueerror' not in msg

    with app.app_context():
        assert Review.query.filter_by(outlet_id=outlet_id).count() == 0
        rep = SyncReport.query.filter_by(business_id=biz_id).order_by(
            SyncReport.created_at.desc()).first()
        assert rep is not None
        assert rep.locations_failed >= 1


# ─── HF006-07 ──────────────────────────────────────────────────────────
def test_07_progress_unknown_task_safe(app_context):
    app = app_context
    _b, _t, _o = _mk_user(app, TEST_EMAIL_A, PLACE_A)
    client = _client(app)
    assert _login(client, TEST_EMAIL_A).status_code in (302, 303)
    rv = client.get('/trial/activate/step3/progress/not-a-real-task-id')
    assert rv.status_code == 200
    assert rv.get_json().get('status') == 'unknown'


# ─── HF006-08 ──────────────────────────────────────────────────────────
def test_08_worker_captures_primitives_structurally(app_context):
    """Worker must be started with captured primitive values (ids), and must
    verify outlet ownership against captured tenant — never rely on detached
    ORM instances across threads."""
    import inspect
    import app.routes.trial as trial_mod

    src = inspect.getsource(trial_mod.step3_start_sync)
    before_thread = src.split('threading.Thread')[0]
    # primitives captured as plain locals BEFORE thread start
    assert 'tenant_id' in before_thread
    assert 'outlet_id' in before_thread
    # ownership verification exists (fail-closed against foreign outlet ids)
    assert 'public_place_id' in src or 'filter_by' in src


def test_08b_worker_rejects_foreign_outlet(app_context):
    """Sync must fail-closed when the session outlet id belongs to another
    business/tenant (session tampering scenario)."""
    app = app_context
    _biz_b, tenant_b, outlet_b = _mk_user(app, TEST_EMAIL_B, PLACE_B)
    adapter = _mk_adapter()

    with patch('app.services.public_provider.build_public_review_adapter', return_value=adapter):
        client = _client(app)
        # login as A but inject B's outlet id into the session (tampering)
        _mk_user(app, TEST_EMAIL_A, PLACE_A)
        assert _login(client, TEST_EMAIL_A).status_code in (302, 303)
        with client.session_transaction() as sess:
            sess['trial_outlet_id'] = outlet_b
        rv = client.post('/trial/activate/step3/start')
        # Fail-closed accepted shapes: (a) upfront rejection 4xx, or
        # (b) task runs and terminates without touching B's data.
        if rv.status_code >= 400:
            assert rv.status_code in (403, 404)
            prog = {'status': 'rejected_upfront'}
        else:
            body = rv.get_json()
            assert isinstance(body.get('task_id'), str)
            prog = {}
            for _ in range(POLL_N):
                pr = client.get(f"/trial/activate/step3/progress/{body['task_id']}")
                assert pr.status_code == 200
                prog = pr.get_json()
                if prog.get('status') in ('done', 'error'):
                    break
                time.sleep(0.05)
            assert prog['status'] in ('done', 'error')

    with app.app_context():
        assert Review.query.filter_by(tenant_id=tenant_b).count() == 0
        assert Review.query.filter_by(outlet_id=outlet_b).count() == 0


# ─── HF006-09 ──────────────────────────────────────────────────────────
def test_09_source_label_matches_adapter(app_context):
    app = app_context
    biz_id, tenant_a, outlet_id = _mk_user(app, TEST_EMAIL_A, PLACE_A)
    adapter = _mk_adapter()

    with patch('app.services.public_provider.build_public_review_adapter', return_value=adapter):
        client = _client(app)
        assert _login(client, TEST_EMAIL_A).status_code in (302, 303)
        prog = _run_step3_sync(client, outlet_id)
        assert prog['status'] == 'done'

    with app.app_context():
        rep = SyncReport.query.filter_by(business_id=biz_id).order_by(
            SyncReport.created_at.desc()).first()
        assert rep is not None
        assert rep.source == 'mock'  # adapter.source_name — NOT 'public_scraping'
        for r in Review.query.filter_by(business_id=biz_id).all():
            assert r.source == 'mock'


# ─── HF006-10 ──────────────────────────────────────────────────────────
def _read_progress(biz):
    val = biz.setup_progress
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val or '{}')
    except (TypeError, json.JSONDecodeError):
        return {}


def test_10_step3_done_only_after_success(app_context):
    app = app_context
    adapter = _mk_adapter()

    # Failure path: unknown place → step3 must NOT become done
    biz_f, _t, outlet_f = _mk_user(app, TEST_EMAIL_F, PLACE_UNKNOWN)
    with patch('app.services.public_provider.build_public_review_adapter', return_value=adapter):
        client = _client(app)
        assert _login(client, TEST_EMAIL_F).status_code in (302, 303)
        prog = _run_step3_sync(client, outlet_f)
        assert prog['status'] == 'error'
    with app.app_context():
        assert _read_progress(Business.query.get(biz_f)).get('step3') != 'done'

    # Success path: known place → step3 done marked by the WORKER
    biz_s, _t, outlet_s = _mk_user(app, TEST_EMAIL_S, PLACE_A)
    with patch('app.services.public_provider.build_public_review_adapter', return_value=adapter):
        client2 = _client(app)
        assert _login(client2, TEST_EMAIL_S).status_code in (302, 303)
        prog = _run_step3_sync(client2, outlet_s)
        assert prog['status'] == 'done'
    with app.app_context():
        assert _read_progress(Business.query.get(biz_s)).get('step3') == 'done'
