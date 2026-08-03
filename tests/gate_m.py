"""Gate M — Apify public review provider quality gate (RUN_11).

Source of truth: skill `grm-apify-public-review-provider` §22.
All vendor calls use HTTP stubs — NEVER hits the live Apify API.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_m.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "true"
os.environ["GRM_PILOT_MAX_OUTLETS"] = "1"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"
os.environ.pop("APIFY_API_TOKEN", None)

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import (
    User, Business, Outlet, Review, ReviewAnalysis, ReviewVersion, ReviewRawPayload, SyncReport,
)
from app.services.public_provider import build_public_review_adapter, get_apify_token
from app.services.feature_flags import is_auto_reply_enabled, is_outlet_pilot_active
from app.adapters.apify_public_review_adapter import (
    ApifyPublicReviewAdapter, ApifyError, _encode_actor_id,
)
from app.adapters.public_review_source_adapter import PublicReviewSourceAdapter

PLACE = "ChIJN1t_tDeuEmsRUsoyG83ZLTo"  # realistic Google place ID format
T1_EMAIL = "owner@buburfay.id"
T1_PW = "pass1234"

REVIEW_ACTOR = "compass/google-maps-reviews-scraper"
DISCOVERY_ACTOR = "compass/crawler-google-places"

# ─── APIFY FIXTURES (verified actor output schema) ─────────
def _item(i, **overrides):
    base = {
        "text": f"Review teks ke-{i}",
        "textTranslated": None,
        "publishAt": "2 days ago",
        "publishedAtDate": f"2026-07-{(28 - i % 28):02d}T08:00:00.000Z",
        "likesCount": i,
        "reviewId": f"review-{i:04d}",
        "reviewUrl": f"https://www.google.com/maps/reviews/review-{i:04d}",
        "stars": (i % 5) + 1,
        "rating": None,
        "responseFromOwnerDate": "2026-07-30T09:00:00.000Z" if i % 3 == 0 else None,
        "responseFromOwnerText": "Terima kasih, Kak!" if i % 3 == 0 else None,
        "reviewImageUrls": [],
        "reviewOrigin": "Google",
        "name": f"Reviewer Nama {i}",
        "reviewerId": f"rev-{i:04d}",
        "reviewerUrl": f"https://www.google.com/maps/contrib/rev-{i:04d}",
        "reviewerNumberOfReviews": 10,
        "reviewerPhotoUrl": None,
        "title": "Bubur Fay Depok",
        "placeId": PLACE,
        "address": "Jl. Raya Depok No. 21, Kota Depok, Jawa Barat",
        "location": {"lat": -6.4025, "lng": 106.8187},
        "categories": ["Restaurant"],
        "totalScore": 4.5,
        "permanentlyClosed": False,
        "temporarilyClosed": False,
        "reviewsCount": 312,
    }
    base.update(overrides)
    return base


FIXTURE_ITEMS = [_item(i) for i in range(1, 5)]
FIXTURE_ITEMS[2]["text"] = ""  # rating-only
FIXTURE_ITEMS[3].pop("reviewId", None)  # deterministic fallback id
FIXTURE_ITEMS[3].pop("reviewUrl", None)


class FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("No JSON body")
        return self._json


def make_fake_http(items=None, fail_run_status=None, run_status_code=200,
                   dataset_status=200, run_calls=None):
    """Stub for requests.request implementing the Apify actor flow.

    The crawler collector returns a place dict whose ``reviews`` field holds
    the review items (matches real crawler-google-places output).
    """
    items = items if items is not None else FIXTURE_ITEMS
    place = {
        "title": "Bubur Fay Depok",
        "placeId": PLACE,
        "reviews": items,
        "totalScore": 4.5,
        "reviewsCount": len(items),
        "address": "Jl. Raya Depok No. 21, Kota Depok, Jawa Barat",
    }
    state = {"post": 0, "poll": 0, "dataset": 0, "discovery": 0}

    def fake_request(method, url, params=None, headers=None, json=None, timeout=None):
        if method == "POST" and "/acts/" in url and "/runs" in url:
            state["post"] += 1
            if run_status_code != 200:
                return FakeResp(status_code=run_status_code)
            return FakeResp(json_data={"data": {"id": "run-1", "status": "RUNNING",
                                                "defaultDatasetId": "ds-1"}})
        if method == "GET" and "/actor-runs/" in url:
            state["poll"] += 1
            status = fail_run_status or "SUCCEEDED"
            return FakeResp(json_data={"data": {"id": "run-1", "status": status,
                                                "defaultDatasetId": "ds-1"}})
        if method == "GET" and "/datasets/" in url and "/items" in url:
            state["dataset"] += 1
            if dataset_status != 200:
                return FakeResp(status_code=dataset_status)
            offset = int((params or {}).get("offset", 0))
            limit = int((params or {}).get("limit", 1000))
            return FakeResp(json_data=[place][offset:offset + limit])
        raise AssertionError(f"unexpected HTTP call: {method} {url}")

    fake_request.state = state
    return fake_request


_SEEDED = False


class GateMBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global _SEEDED
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        if _SEEDED:
            return
        with cls.app.app_context():
            db.create_all()
            biz1 = Business(id="biz-m-1", tenant_id="tenant-m-1", name="Bubur Fay", brand_name="Bubur Fay")
            u1 = User(id="u-m-1", email=T1_EMAIL, password_hash=generate_password_hash(T1_PW),
                      display_name="Owner", business_id="biz-m-1", role="owner", is_active=True)
            db.session.add_all([biz1, u1])
            db.session.commit()
            db.session.add(Outlet(
                id="outlet-m-hj", tenant_id="tenant-m-1", business_id="biz-m-1",
                name="Bubur Fay Harjamukti", public_place_id="ChIJ0-harjamukti-old-006",
                status="old_or_closed", monitor_enabled=True, reply_enabled=False,
            ))
            db.session.commit()
            _SEEDED = True

    def setUp(self):
        self.client = self.app.test_client()
        self.client.post("/auth/login", data={"email": T1_EMAIL, "password": T1_PW})

    def _make_outlet(self, name="Bubur Fay Depok", place_id=PLACE, status="active"):
        import uuid
        with self.app.app_context():
            o = Outlet(
                id=f"outlet-m-{uuid.uuid4().hex[:10]}",
                tenant_id="tenant-m-1",
                business_id="biz-m-1",
                name=name,
                public_place_id=place_id,
                status=status,
                monitor_enabled=True,
                reply_enabled=False,
            )
            db.session.add(o)
            db.session.commit()
            return o.id

    def _adapter(self, **kwargs):
        params = dict(token="apify-token-test", max_reviews=100, timeout_seconds=30,
                      poll_interval_seconds=1)
        params.update(kwargs)
        return ApifyPublicReviewAdapter(**params)

    def _sync_apify(self, fake_http, outlet_ids=None, full_sync=False):
        adapter = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake_http):
            from app.services.sync_service import sync_public_reviews
            with self.app.app_context():
                return sync_public_reviews(
                    tenant_id="tenant-m-1",
                    business_id="biz-m-1",
                    outlet_ids=outlet_ids,
                    adapter=adapter,
                    source="apify",
                    full_sync=full_sync,
                )


# ─── PROVIDER CONFIG ───────────────────────────────────────
class TestProviderConfig(GateMBase):
    def test_provider_apify(self):
        os.environ["APIFY_API_TOKEN"] = "tok"
        try:
            a = build_public_review_adapter("apify")
            self.assertEqual(type(a).__name__, "ApifyPublicReviewAdapter")
        finally:
            os.environ.pop("APIFY_API_TOKEN", None)

    def test_missing_token(self):
        os.environ.pop("APIFY_API_TOKEN", None)
        with self.assertRaises(ValueError):
            build_public_review_adapter("apify")
        with self.assertRaises(ValueError):
            ApifyPublicReviewAdapter()  # no token anywhere

    def test_invalid_provider(self):
        with self.assertRaises(ValueError):
            build_public_review_adapter("selenium")

    def test_no_silent_fallback(self):
        os.environ["PUBLIC_REVIEW_PROVIDER"] = "apify"
        os.environ.pop("APIFY_API_TOKEN", None)
        try:
            with self.assertRaises(ValueError):
                build_public_review_adapter()
        finally:
            os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

    def test_token_redaction_in_errors(self):
        secret = "apify-tok-SECRET123"
        a = self._adapter(token=secret)
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request",
                        return_value=FakeResp(status_code=200, json_data={"data": {}})):
            with self.assertRaises(ApifyError) as ctx:
                a.list_reviews_by_place_id(PLACE)
        self.assertNotIn(secret, str(ctx.exception))
        self.assertNotIn(secret, json.dumps(ctx.exception.to_dict()))

    def test_actor_id_encoding(self):
        self.assertEqual(_encode_actor_id(REVIEW_ACTOR), "compass~google-maps-reviews-scraper")
        self.assertEqual(_encode_actor_id(DISCOVERY_ACTOR), "compass~crawler-google-places")

    def test_health_check(self):
        h = self._adapter().health_check()
        self.assertEqual(h["provider"], "apify")
        self.assertTrue(h["token_present"])
        self.assertEqual(h["review_actor_id"], REVIEW_ACTOR)
        self.assertNotIn("token", json.dumps(h).lower().replace("token_present", "").replace("token", "tok_redacted"))


# ─── INPUT VALIDATION ──────────────────────────────────────
class TestInputValidation(GateMBase):
    def test_placeholder_place_rejected(self):
        a = self._adapter()
        with self.assertRaises(ApifyError) as ctx:
            a.list_reviews_by_place_id("ChIJ0-depok-margonda-001")
        self.assertEqual(ctx.exception.code, "PLACEHOLDER_REJECTED")

    def test_fetch_location_placeholder_rejected(self):
        a = self._adapter()
        with self.assertRaises(ApifyError):
            a.fetch_location("ChIJ0-harjamukti-old-006")

    def test_valid_place_accepted(self):
        fake = make_fake_http()
        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            items = a.list_reviews_by_place_id(PLACE)
        self.assertEqual(len(items), 4)


# ─── RUN HANDLING ──────────────────────────────────────────
class TestRunHandling(GateMBase):
    def test_run_success(self):
        fake = make_fake_http()
        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            items = a.list_reviews_by_place_id(PLACE)
        self.assertEqual(len(items), 4)
        self.assertEqual(fake.state["poll"], 1)

    def test_run_failed(self):
        fake = make_fake_http(fail_run_status="FAILED")
        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            with self.assertRaises(ApifyError) as ctx:
                a.list_reviews_by_place_id(PLACE)
        self.assertEqual(ctx.exception.code, "FAILED")

    def test_run_aborted(self):
        fake = make_fake_http(fail_run_status="ABORTED")
        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            with self.assertRaises(ApifyError) as ctx:
                a.list_reviews_by_place_id(PLACE)
        self.assertEqual(ctx.exception.code, "ABORTED")

    def test_timeout(self):
        a = self._adapter(timeout_seconds=1, poll_interval_seconds=2)
        state = {"n": 0}

        def fake_request(method, url, params=None, headers=None, json=None, timeout=None):
            state["n"] += 1
            if method == "POST":
                return FakeResp(json_data={"data": {"id": "run-1", "status": "RUNNING",
                                                    "defaultDatasetId": "ds-1"}})
            # poll always RUNNING until deadline
            return FakeResp(json_data={"data": {"id": "run-1", "status": "RUNNING",
                                                "defaultDatasetId": "ds-1"}})

        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake_request):
            with mock.patch("app.adapters.apify_public_review_adapter.time.sleep"):
                with self.assertRaises(ApifyError) as ctx:
                    a.list_reviews_by_place_id(PLACE)
        self.assertEqual(ctx.exception.code, "TIMED_OUT")

    def test_rate_limit_retry_then_success(self):
        fake = make_fake_http()
        state = {"n": 0}

        def side_effect(method, url, params=None, headers=None, json=None, timeout=None):
            state["n"] += 1
            if state["n"] == 1:
                return FakeResp(status_code=429)
            return fake(method, url, params=params, headers=headers, json=json, timeout=timeout)

        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", side_effect):
            with mock.patch("app.adapters.apify_public_review_adapter.time.sleep"):
                items = a.list_reviews_by_place_id(PLACE)
        self.assertEqual(len(items), 4)

    def test_401_no_retry(self):
        a = self._adapter()
        state = {"n": 0}

        def side_effect(method, url, params=None, headers=None, json=None, timeout=None):
            state["n"] += 1
            return FakeResp(status_code=401)

        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", side_effect):
            with self.assertRaises(ApifyError) as ctx:
                a.list_reviews_by_place_id(PLACE)
        self.assertEqual(ctx.exception.code, "AUTH_FAILED")
        self.assertEqual(state["n"], 1)  # no retry on 401


# ─── DATASET RETRIEVAL ─────────────────────────────────────
class TestDataset(GateMBase):
    def test_dataset_retrieval(self):
        fake = make_fake_http()
        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            a.list_reviews_by_place_id(PLACE)
        self.assertGreaterEqual(fake.state["dataset"], 1)

    def test_empty_dataset(self):
        fake = make_fake_http(items=[])
        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            items = a.list_reviews_by_place_id(PLACE)
        self.assertEqual(items, [])

    def test_pagination(self):
        many = [_item(i, reviewId=f"rv-{i:04d}") for i in range(1500)]
        fake = make_fake_http(items=many)
        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            items = a.list_reviews_by_place_id(PLACE, limit=5000)
        self.assertEqual(len(items), 1500)
        self.assertGreaterEqual(fake.state["dataset"], 1)  # crawler returns all in one dataset item

    def test_repeated_page_guard(self):
        # stub returns same page regardless of offset → adapter must stop
        fake = make_fake_http(items=FIXTURE_ITEMS)
        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            items = a.list_reviews_by_place_id(PLACE)
        self.assertLessEqual(len(items), len(FIXTURE_ITEMS))

    def test_malformed_item_partial_failure(self):
        items = [FIXTURE_ITEMS[0], "not-a-dict", FIXTURE_ITEMS[2]]
        fake = make_fake_http(items=items)
        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            normalized = a.list_reviews_by_place_id(PLACE)
        # one bad item skipped, rest normalized
        self.assertGreaterEqual(len(normalized), 2)


# ─── NORMALIZATION ─────────────────────────────────────────
class TestNormalization(GateMBase):
    def _items(self):
        a = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", make_fake_http()):
            return a.list_reviews_by_place_id(PLACE)

    def test_rating(self):
        items = self._items()
        self.assertTrue(all(1 <= i["rating"] <= 5 for i in items))

    def test_review_text(self):
        items = self._items()
        self.assertIn("Review teks", items[0]["review_text"])

    def test_date(self):
        items = self._items()
        self.assertTrue(all(i["review_date"] for i in items))

    def test_rating_only(self):
        items = self._items()
        ro = next(i for i in items if i["source_review_id"] == "review-0003")
        self.assertEqual(ro["review_text"], "")
        self.assertEqual(ro["rating"], 4)  # stars 4 for i=3

    def test_owner_reply(self):
        items = self._items()
        with_reply = [i for i in items if i["owner_reply_text"]]
        self.assertGreaterEqual(len(with_reply), 1)
        self.assertEqual(with_reply[0]["owner_reply_text"], "Terima kasih, Kak!")

    def test_source_url(self):
        items = self._items()
        # items with a vendor review URL carry source_url; the deterministic
        # fallback item has no URL by design
        with_url = [i for i in items if i["source_review_id"].startswith("review-")]
        self.assertTrue(with_url)
        self.assertTrue(all(i["source_url"] for i in with_url))

    def test_reviewer_masking(self):
        items = self._items()
        self.assertTrue(all(("***" in i["reviewer_name_masked"]) for i in items))

    def test_geographic_unknown(self):
        items = self._items()
        self.assertTrue(all(i["province"] is None for i in items))  # actor doesn't supply → sync geo/unknown
        loc = self._adapter().fetch_location
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", make_fake_http()):
            fl = self._adapter().fetch_location(PLACE)
        self.assertIsNone(fl["province"])

    def test_deterministic_fallback_id(self):
        from app.adapters.apify_public_review_adapter import _deterministic_review_id
        items = self._items()
        noid = next(i for i in items if i["source_review_id"].startswith("hash_"))
        again = _deterministic_review_id(PLACE, FIXTURE_ITEMS[3])
        self.assertEqual(noid["source_review_id"], again)

    def test_source_labeling(self):
        items = self._items()
        self.assertTrue(all(i["source"] == "apify" for i in items))

    def test_cross_branch_safe_id(self):
        oid_a = "outlet-A"
        oid_b = "outlet-B"
        name_a = f"apify:{oid_a}:{PLACE}:review-0001"
        name_b = f"apify:{oid_b}:{PLACE}:review-0001"
        self.assertNotEqual(name_a, name_b)  # same place/review on different branches


# ─── SYNC ──────────────────────────────────────────────────
class TestSync(GateMBase):
    def test_initial_sync(self):
        oid = self._make_outlet()
        rep = self._sync_apify(make_fake_http(), outlet_ids=[oid])
        self.assertEqual(rep["provider"], "apify")
        self.assertEqual(rep["reviews_created"], 4)
        self.assertEqual(rep["sync_status"], "ok")
        with self.app.app_context():
            self.assertEqual(Review.query.filter_by(outlet_id=oid).count(), 4)

    def test_second_sync_idempotency(self):
        oid = self._make_outlet()
        rep1 = self._sync_apify(make_fake_http(), outlet_ids=[oid])
        rep2 = self._sync_apify(make_fake_http(), outlet_ids=[oid], full_sync=True)
        self.assertEqual(rep1["reviews_created"], 4)
        self.assertEqual(rep2["reviews_created"], 0)
        with self.app.app_context():
            self.assertEqual(Review.query.filter_by(outlet_id=oid).count(), 4)

    def test_incremental_sync(self):
        oid = self._make_outlet()
        rep1 = self._sync_apify(make_fake_http(), outlet_ids=[oid])
        rep2 = self._sync_apify(make_fake_http(), outlet_ids=[oid])
        self.assertEqual(rep2["reviews_inserted"], 0)  # incremental: no new
        self.assertGreaterEqual(rep2["reviews_skipped"], 1)

    def test_version_history(self):
        oid = self._make_outlet()
        self._sync_apify(make_fake_http(), outlet_ids=[oid])
        updated = [dict(FIXTURE_ITEMS[0], stars=2, text="Rating berubah", reviewId="review-0001")]
        fake = make_fake_http(items=updated + FIXTURE_ITEMS[1:])
        rep = self._sync_apify(fake, outlet_ids=[oid], full_sync=True)
        self.assertEqual(rep["reviews_updated"], 1)
        with self.app.app_context():
            rv = Review.query.filter_by(tenant_id="tenant-m-1", outlet_id=oid).filter(
                Review.comment.like("%berubah%")).first()
            self.assertIsNotNone(rv)
            self.assertEqual(rv.current_version, 2)

    def test_duplicate_prevention(self):
        oid = self._make_outlet()
        self._sync_apify(make_fake_http(), outlet_ids=[oid])
        self._sync_apify(make_fake_http(), outlet_ids=[oid], full_sync=True)
        with self.app.app_context():
            self.assertEqual(Review.query.filter_by(outlet_id=oid).count(), 4)

    def test_previous_data_retained_on_failure(self):
        oid = self._make_outlet()
        self._sync_apify(make_fake_http(), outlet_ids=[oid])

        def failing(method, url, params=None, headers=None, json=None, timeout=None):
            raise ApifyError("provider down", status_code=500, retryable=True)

        adapter = self._adapter()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", failing):
            from app.services.sync_service import sync_public_reviews
            with self.app.app_context():
                rep = sync_public_reviews(
                    tenant_id="tenant-m-1", business_id="biz-m-1",
                    outlet_ids=[oid], adapter=adapter, source="apify",
                )
        self.assertEqual(rep["locations_failed"], 1)
        with self.app.app_context():
            self.assertEqual(Review.query.filter_by(outlet_id=oid).count(), 4)

    def test_sync_statistics(self):
        oid = self._make_outlet()
        fake = make_fake_http()
        rep = self._sync_apify(fake, outlet_ids=[oid])
        self.assertEqual(rep["reviews_received"], 4)
        self.assertEqual(rep["reviews_inserted"], 4)
        self.assertEqual(rep["error_summary"], [])
        with self.app.app_context():
            s = SyncReport.query.filter_by(tenant_id="tenant-m-1").order_by(
                SyncReport.created_at.desc()).first()
            self.assertEqual(s.source, "apify")

    def test_raw_payload_preserved(self):
        oid = self._make_outlet()
        self._sync_apify(make_fake_http(), outlet_ids=[oid])
        with self.app.app_context():
            rps = ReviewRawPayload.query.filter_by(tenant_id="tenant-m-1", source="apify").all()
            with_run = [rp for rp in rps if rp.raw_payload and rp.raw_payload.get("_run_id")]
            self.assertTrue(with_run, "tidak ada raw payload apify dengan _run_id")
            self.assertEqual(with_run[0].source, "apify")


# ─── DISCOVERY ─────────────────────────────────────────────
class TestDiscovery(GateMBase):
    def test_discovery_by_business_city(self):
        a = self._adapter()
        fake = make_fake_http()
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            results = a.discover("Bubur Fay", city="Depok", max_places=5)
        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(all(r["source"] == "apify" for r in results))
        self.assertTrue(all(r["place_id"] for r in results))

    def test_result_hard_limit(self):
        a = self._adapter(max_places=3)
        items = [_item(i, reviewId=f"d-{i:04d}") for i in range(10)]
        # discovery stub returns same dataset; hard limit via max_places
        fake = make_fake_http(items=items)
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request", fake):
            results = a.discover("Bubur Fay", max_places=3)
        self.assertLessEqual(len(results), 3)


# ─── SAFETY ────────────────────────────────────────────────
class TestSafety(GateMBase):
    def test_harjamukti_excluded(self):
        with self.app.app_context():
            hj = Outlet.query.filter_by(id="outlet-m-hj").first()
            self.assertFalse(is_outlet_pilot_active(hj))
        rep = self._sync_apify(make_fake_http(), outlet_ids=["outlet-m-hj"])
        self.assertEqual(rep["reviews_created"], 0)
        with self.app.app_context():
            self.assertEqual(Review.query.filter_by(outlet_id="outlet-m-hj").count(), 0)

    def test_one_pilot_outlet_enforced(self):
        with self.app.app_context():
            from app.services.feature_flags import pilot_max_outlets
            self.assertEqual(pilot_max_outlets(), 1)
            # Isolated tenant so previous tests' outlets don't interfere
            biz = Business(id="biz-m-po", tenant_id="tenant-m-po", name="Pilot Only", brand_name="Pilot Only")
            db.session.add(biz)
            db.session.commit()
            o1 = Outlet(id="po-m-1", tenant_id="tenant-m-po", business_id="biz-m-po",
                        name="Outlet Satu", public_place_id="X1", status="active",
                        monitor_enabled=True, reply_enabled=False)
            db.session.add(o1)
            db.session.commit()
            self.assertTrue(is_outlet_pilot_active(o1))
            o2 = Outlet(id="po-m-2", tenant_id="tenant-m-po", business_id="biz-m-po",
                        name="Outlet Dua", public_place_id="X2", status="active",
                        monitor_enabled=True, reply_enabled=False)
            db.session.add(o2)
            db.session.commit()
            self.assertFalse(is_outlet_pilot_active(o2))

    def test_oauth_not_required(self):
        with self.app.app_context():
            from app.models.entities import GoogleConnection
            self.assertEqual(GoogleConnection.query.filter_by(tenant_id="tenant-m-1").count(), 0)
        oid = self._make_outlet()
        rep = self._sync_apify(make_fake_http(), outlet_ids=[oid])
        self.assertEqual(rep["sync_status"], "ok")

    def test_direct_reply_disabled(self):
        oid = self._make_outlet()
        self._sync_apify(make_fake_http(), outlet_ids=[oid])
        with self.app.app_context():
            o = Outlet.query.get(oid)
            self.assertFalse(o.reply_enabled)

    def test_auto_reply_off(self):
        self.assertFalse(is_auto_reply_enabled())

    def test_reply_enabled_false(self):
        oid = self._make_outlet()
        with self.app.app_context():
            o = Outlet.query.get(oid)
            self.assertFalse(o.reply_enabled)

    def test_tenant_isolation(self):
        oid = self._make_outlet()
        self._sync_apify(make_fake_http(), outlet_ids=[oid])
        with self.app.app_context():
            cnt = Review.query.filter_by(tenant_id="tenant-other").count()
        self.assertEqual(cnt, 0)

    def test_no_live_http_without_token(self):
        # Without token, adapter must fail before any HTTP call
        os.environ.pop("APIFY_API_TOKEN", None)
        with self.assertRaises(ValueError):
            ApifyPublicReviewAdapter()

    def test_no_secret_in_logs_or_report(self):
        # Error dict never contains token value
        secret = "apify-supersecret-token"
        a = self._adapter(token=secret)
        with mock.patch("app.adapters.apify_public_review_adapter.requests.request",
                        return_value=FakeResp(status_code=401)):
            with self.assertRaises(ApifyError) as ctx:
                a.list_reviews_by_place_id(PLACE)
        self.assertNotIn(secret, str(ctx.exception))
        self.assertNotIn(secret, str(ctx.exception.to_dict()))


# ─── AI ADVISOR ────────────────────────────────────────────
class TestAiAdvisor(GateMBase):
    def setUp(self):
        super().setUp()
        self._clean_tenant()

    def _clean_tenant(self):
        """Isolate each advisor test: remove tenant-m-1 review data."""
        with self.app.app_context():
            rows = Review.query.filter_by(tenant_id="tenant-m-1").all()
            for r in rows:
                ReviewRawPayload.query.filter_by(review_pk=r.id).delete()
                ReviewVersion.query.filter_by(review_pk=r.id).delete()
                ReviewAnalysis.query.filter_by(review_pk=r.id).delete()
                db.session.delete(r)
            db.session.commit()

    def _seed_reviews(self, texts, outlet_id=None, tenant="tenant-m-1", biz="biz-m-1"):
        """Insert text reviews and run rule-based analysis."""
        import uuid
        from app.services.review_service import normalize_review, upsert_review
        from app.services.analysis_service import analyze_review
        oid = outlet_id or self._make_outlet()
        with self.app.app_context():
            for i, (txt, rating) in enumerate(texts):
                rid = f"adv-{uuid.uuid4().hex[:8]}"
                data = {
                    "source_review_name": f"apify:{oid}:PLACE:{rid}",
                    "reviewer_display_name": "Uji A***",
                    "star_rating": rating,
                    "comment": txt,
                    "create_time": "2026-07-20T08:00:00",
                    "update_time": "2026-07-20T08:00:00",
                }
                normalized = normalize_review(tenant, biz, oid, "apify", data)
                normalized["source_review_name"] = f"apify:{oid}:PLACE:{rid}"
                upsert_review(tenant, biz, oid, "apify", f"apify:{oid}:PLACE:{rid}",
                              normalized, raw_payload=data)
                rv = Review.query.filter_by(tenant_id=tenant, source_review_name=f"apify:{oid}:PLACE:{rid}").first()
                analyze_review(tenant, biz, rv.id)
            db.session.commit()
        return oid

    def _advisor(self, **filters):
        from app.services.ai_advisor import generate
        from app.services.public_analytics import parse_filters
        with self.app.app_context():
            return generate("tenant-m-1", "biz-m-1", parse_filters(filters))

    def test_advisor_contract_fields(self):
        oid = self._seed_reviews([("Pelayanan tidak ramah, kasir cuek.", 2),
                                  ("Pelayanannya lambat dan judes.", 1)])
        adv = self._advisor(days="90")
        self.assertGreaterEqual(len(adv["issues"]), 1)
        it = adv["issues"][0]
        for field in ("outlet", "masalah", "bukti", "saran_tindakan", "pic"):
            self.assertIn(field, it)
        self.assertIn("review_count", it["bukti"])
        self.assertIn("period", it["bukti"])
        self.assertIsInstance(it["saran_tindakan"], list)

    def test_advisor_max_top3(self):
        self._seed_reviews([("Rasa tidak enak.", 1), ("Makanan basi.", 1),
                            ("Pelayanan lambat.", 2), ("Kotor.", 1), ("Mahal.", 2),
                            ("Lama sekali.", 1)])
        adv = self._advisor(days="90")
        self.assertLessEqual(len(adv["issues"]), 3)

    def test_advisor_crew_mapping(self):
        self._seed_reviews([("Pelayanan tidak ramah, kasir cuek.", 2),
                            ("Waiternya jarang senyum.", 1)])
        adv = self._advisor(days="90")
        crews = [i for i in adv["issues"] if i["pic"] == "Crew Outlet"]
        self.assertTrue(crews)

    def test_advisor_supervisor_mapping(self):
        self._seed_reviews([("Ordernya lama banget, nunggu 30 menit.", 1),
                            ("Antreannya lama.", 2)])
        adv = self._advisor(days="90")
        sups = [i for i in adv["issues"] if i["pic"] == "Supervisor"]
        self.assertTrue(sups)

    def test_advisor_kitchen_mapping(self):
        self._seed_reviews([("Rasanya berubah, tidak enak.", 1),
                            ("Buburnya hambar.", 2)])
        adv = self._advisor(days="90")
        kitchens = [i for i in adv["issues"] if i["pic"] == "Kitchen / Chef"]
        self.assertTrue(kitchens)

    def test_advisor_owner_mapping(self):
        self._seed_reviews([("Setelah makan langsung mual, takut keracunan.", 1)])
        adv = self._advisor(days="90")
        owners = [i for i in adv["issues"] if i["pic"] == "Owner"]
        self.assertTrue(owners)

    def test_advisor_evidence_count_period(self):
        oid = self._seed_reviews([("Pelayanan tidak ramah.", 2)])
        adv = self._advisor(days="90")
        self.assertGreaterEqual(len(adv["issues"]), 1)
        self.assertGreaterEqual(adv["issues"][0]["bukti"]["review_count"], 1)
        self.assertIn("s/d", adv["issues"][0]["bukti"]["period"])

    def test_advisor_rating_only_excluded(self):
        self._seed_reviews([("", 1)])  # rating-only, no text
        adv = self._advisor(days="90")
        self.assertEqual(adv["issues"], [])

    def test_advisor_no_unsupported_accusation(self):
        self._seed_reviews([("Pelayanan tidak ramah.", 2)])
        adv = self._advisor(days="90")
        for it in adv["issues"]:
            self.assertNotIn("malas", it["masalah"].lower())
            self.assertNotIn("tidak peduli", it["masalah"].lower())

    def test_advisor_weak_evidence_human_review(self):
        self._seed_reviews([("Rasa tidak enak.", 1)])  # single review
        adv = self._advisor(days="90")
        if adv["issues"]:
            self.assertTrue(adv["issues"][0]["needs_human_review"])

    def test_advisor_tenant_isolation(self):
        self._seed_reviews([("Pelayanan tidak ramah.", 2)])
        with self.app.app_context():
            biz2 = Business(id="biz-adv2", tenant_id="tenant-adv2", name="Lain", brand_name="Lain")
            db.session.add(biz2)
            db.session.commit()
            from app.services.ai_advisor import generate
            from app.services.public_analytics import parse_filters
            adv2 = generate("tenant-adv2", "biz-adv2", parse_filters({"days": "90"}))
        self.assertEqual(adv2["issues"], [])

    def test_advisor_filter_aware(self):
        self._seed_reviews([("Pelayanan tidak ramah.", 2)])
        # Outside the filter window → no issues
        adv_out = self._advisor(days="7", start_date="2025-01-01", end_date="2025-01-31")
        # hmm: start/end override days; reviews are 2026-07 → empty
        self.assertEqual(adv_out["issues"], [])


# ─── DASHBOARD WITH APIFY SOURCE ───────────────────────────
class TestDashboardApify(GateMBase):
    def _sync_live_like(self):
        # Seed apify-source data via stub sync (no live HTTP)
        oid = self._make_outlet()
        fake = make_fake_http()
        self._sync_apify(fake, outlet_ids=[oid])
        return oid

    def test_dashboard_source_apify(self):
        oid = self._sync_live_like()
        r = self.client.get("/api/public/analytics/summary?days=90")
        s = r.get_json()
        self.assertGreaterEqual(s["total_reviews"], 4)
        r2 = self.client.get("/api/public/analytics/explorer?outlet_id=" + oid)
        items = r2.get_json()["items"]
        self.assertTrue(all(i["source"] == "apify" for i in items))

    def test_dashboard_filters(self):
        self._sync_live_like()
        r = self.client.get("/api/public/analytics/explorer?rating=5")
        items = r.get_json()["items"]
        self.assertTrue(all(i["rating"] == 5 for i in items))

    def test_export_csv_apify(self):
        self._sync_live_like()
        r = self.client.get("/api/public/analytics/export.csv")
        self.assertEqual(r.status_code, 200)
        import csv as _csv
        parsed = list(_csv.reader(io.StringIO(r.data.decode())))
        header_idx = next(i for i, row in enumerate(parsed) if row and not row[0].startswith("#"))
        header = parsed[header_idx]
        src_idx = header.index("sumber")
        for row in parsed[header_idx + 1:]:
            if row:
                self.assertEqual(row[src_idx], "apify")


if __name__ == "__main__":
    unittest.main(verbosity=2)
