"""Gate K — Production Public Review Adapter quality gate (RUN_10).

Covers the RUN_10 contract: Outscraper adapter, provider config, sync
statistics, incremental sync, export metadata, and safety rules.
All vendor calls are HTTP stubs — NEVER hits the production Outscraper API.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_k.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"
os.environ.pop("OUTSCRAPER_API_KEY", None)

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import (
    User, Business, Outlet, Review, ReviewVersion, ReviewRawPayload, SyncReport,
)
from app.services.public_provider import build_public_review_adapter
from app.adapters.outscraper_public_review_adapter import (
    OutscraperPublicReviewAdapter, OutscraperError,
)
from app.adapters.public_review_source_adapter import PublicReviewSourceAdapter

PLACE = "ChIJ0-depok-margonda-001"
T1_EMAIL = "owner@buburfay.id"
T1_PW = "pass1234"

# ─── OUTSCRAPER FIXTURES ───────────────────────────────────
FIXTURE_LOCATION = {
    "place_id": PLACE,
    "name": "Bubur Fay Depok",
    "full_address": "Jl. Raya Depok No. 21, Kota Depok, Jawa Barat",
    "address": "Jl. Raya Depok No. 21",
    "city": "Depok",
    "state": "Jawa Barat",
    "district": None,
    "rating": 4.5,
    "reviews": 312,
    "latitude": -6.4025,
    "longitude": 106.8187,
    "maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJ0-depok-margonda-001",
}

FIXTURE_REVIEWS = [
    {
        "review_id": "rv-001",
        "author_title": "Budi Santoso",
        "review_rating": 5,
        "review_text": "Buburnya enak banget, kuahnya gurih.",
        "review_datetime_utc": "2026-08-01T07:30:00",
        "review_timestamp": 1754026200,
        "owner_answer": "Terima kasih, Kak!",
        "owner_answer_datetime_utc": "2026-08-01T10:00:00",
        "review_likes": 3,
    },
    {
        "review_id": "rv-002",
        "author_title": "Sari Wulandari",
        "review_rating": 2,
        "review_text": "Porsi kecil, harga naik.",
        "review_datetime_utc": "2026-07-25T08:10:00",
        "owner_answer": None,
        "owner_answer_datetime_utc": None,
    },
    {
        "review_id": "rv-003",
        "author_title": "Anonim",
        "review_rating": 1,
        "review_text": "",
        "review_datetime_utc": "2026-07-20T09:00:00",
    },
    {
        # No vendor ID → deterministic fallback hash
        "author_title": "Rina T",
        "review_rating": 4,
        "review_text": "Kebersihan terjaga.",
        "review_datetime_utc": "2026-07-18T06:55:00",
    },
]


class FakeResp:
    def __init__(self, status_code=200, json_data=None, text=None):
        self.status_code = status_code
        self._json = json_data
        self._text = text

    def json(self):
        if self._json is None:
            raise ValueError("No JSON body")
        return self._json

    @property
    def text(self):
        if self._text is not None:
            return self._text
        return json.dumps(self._json) if self._json is not None else ""


def make_fake_get(location=None, reviews=None, fail_after=None):
    """Build a requests.get stub implementing Outscraper pagination."""
    location = location if location is not None else FIXTURE_LOCATION
    reviews = reviews if reviews is not None else FIXTURE_REVIEWS
    calls = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        if fail_after is not None and calls["n"] > fail_after:
            raise AssertionError("unexpected extra call")
        q = (params or {}).get("query")
        rtype = (params or {}).get("reviewsType")
        if rtype == "only_location":
            return FakeResp(json_data={"data": [location]})
        limit = int((params or {}).get("limit", 100))
        offset = int((params or {}).get("offset", 0))
        page = reviews[offset:offset + limit]
        return FakeResp(json_data={"data": [{"place_id": q, "reviews_data": page}]})

    fake_get.calls = calls
    return fake_get


_SEEDED = False


class GateKBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global _SEEDED
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        if _SEEDED:
            return
        with cls.app.app_context():
            db.create_all()
            biz1 = Business(id="biz-k-1", tenant_id="tenant-k-1", name="Bubur Fay", brand_name="Bubur Fay")
            u1 = User(id="u-k-1", email=T1_EMAIL, password_hash=generate_password_hash(T1_PW),
                      display_name="Owner", business_id="biz-k-1", role="owner", is_active=True)
            biz2 = Business(id="biz-k-2", tenant_id="tenant-k-2", name="Kopi Lain", brand_name="Kopi Lain")
            u2 = User(id="u-k-2", email="k2@koplain.id", password_hash=generate_password_hash("pw2"),
                      display_name="Owner2", business_id="biz-k-2", role="owner", is_active=True)
            db.session.add_all([biz1, u1, biz2, u2])
            db.session.commit()
            cls._seed_harjamukti()
            _SEEDED = True

    @classmethod
    def _seed_harjamukti(cls):
        """Create a Harjamukti outlet marked old_or_closed (must stay excluded)."""
        o = Outlet(
            id="outlet-k-hj",
            tenant_id="tenant-k-1",
            business_id="biz-k-1",
            name="Bubur Fay Harjamukti",
            public_place_id="ChIJ0-harjamukti-old-006",
            status="old_or_closed",
            monitor_enabled=True,
            reply_enabled=False,
        )
        db.session.add(o)
        db.session.commit()

    def setUp(self):
        self.client = self.app.test_client()
        self.client.post("/auth/login", data={"email": T1_EMAIL, "password": T1_PW})

    def _make_outlet(self, name="Bubur Fay Depok", place_id=PLACE):
        import uuid
        with self.app.app_context():
            o = Outlet(
                id=f"outlet-k-{uuid.uuid4().hex[:10]}",
                tenant_id="tenant-k-1",
                business_id="biz-k-1",
                name=name,
                public_place_id=place_id,
                status="active",
                monitor_enabled=True,
                reply_enabled=False,
            )
            db.session.add(o)
            db.session.commit()
            return o.id

    def _sync_outscraper(self, fake_get, outlet_ids=None, **kwargs):
        adapter = OutscraperPublicReviewAdapter(
            api_key="test-key",
            max_retries=0,
            page_size=100,
        )
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", fake_get):
            from app.services.sync_service import sync_public_reviews
            with self.app.app_context():
                return sync_public_reviews(
                    tenant_id="tenant-k-1",
                    business_id="biz-k-1",
                    outlet_ids=outlet_ids,
                    adapter=adapter,
                    **kwargs,
                )


# ─── ADAPTER CONTRACT ──────────────────────────────────────
class TestAdapterContract(GateKBase):
    def test_adapter_implements_interface(self):
        a = OutscraperPublicReviewAdapter(api_key="k")
        self.assertIsInstance(a, PublicReviewSourceAdapter)
        self.assertEqual(a.source_name, "outscraper")

    def test_fetch_location_valid_place_id(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", make_fake_get()):
            loc = a.fetch_location(PLACE)
        self.assertEqual(loc["business_name"], "Bubur Fay Depok")
        self.assertEqual(loc["business_rating"], 4.5)
        self.assertEqual(loc["business_review_count"], 312)
        self.assertEqual(loc["province"], "Jawa Barat")
        self.assertEqual(loc["city_regency"], "Depok")
        self.assertEqual(loc["source"], "outscraper")

    def test_maps_url_input(self):
        # The API layer extracts place_id from Maps URLs; adapter accepts place_id.
        import re
        url = "https://www.google.com/maps/place/?q=place_id:ChIJ0-depok-margonda-001"
        m = re.search(r"place_id[:=]([A-Za-z0-9_:\-]+)", url)
        self.assertEqual(m.group(1), PLACE)
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", make_fake_get()):
            loc = a.fetch_location(m.group(1))
        self.assertEqual(loc["place_id"], PLACE)

    def test_missing_api_key(self):
        os.environ.pop("OUTSCRAPER_API_KEY", None)
        with self.assertRaises(ValueError):
            OutscraperPublicReviewAdapter()  # no key anywhere
        os.environ["OUTSCRAPER_API_KEY"] = "env-key"
        try:
            a = OutscraperPublicReviewAdapter()
            self.assertEqual(a.api_key, "env-key")
        finally:
            os.environ.pop("OUTSCRAPER_API_KEY", None)

    def test_timeout_raises_normalized(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get",
                        side_effect=__import__("requests").exceptions.Timeout()):
            with self.assertRaises(OutscraperError) as ctx:
                a.list_reviews_by_place_id(PLACE)
        self.assertTrue(ctx.exception.retryable)

    def test_retry_then_success(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=2, page_size=100)
        fake = make_fake_get()
        state = {"n": 0}

        def side_effect(url, params=None, headers=None, timeout=None):
            state["n"] += 1
            if state["n"] == 1:
                return FakeResp(status_code=429)
            if state["n"] == 2:
                return FakeResp(status_code=503)
            return fake(url, params=params, headers=headers, timeout=timeout)

        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", side_effect):
            with mock.patch("app.adapters.outscraper_public_review_adapter.time.sleep"):
                items = a.list_reviews_by_place_id(PLACE, limit=100)
        self.assertEqual(len(items), 4)
        self.assertEqual(state["n"], 3)

    def test_rate_limit_handled(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=1, page_size=100)
        fake = make_fake_get()
        state = {"n": 0}

        def side_effect(url, params=None, headers=None, timeout=None):
            state["n"] += 1
            if state["n"] == 1:
                return FakeResp(status_code=429)
            return fake(url, params=params, headers=headers, timeout=timeout)

        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", side_effect):
            with mock.patch("app.adapters.outscraper_public_review_adapter.time.sleep"):
                items = a.list_reviews_by_place_id(PLACE, limit=100)
        self.assertEqual(len(items), 4)

    def test_malformed_payload(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get",
                        return_value=FakeResp(status_code=200, text="not json")):
            with self.assertRaises(OutscraperError):
                a.list_reviews_by_place_id(PLACE)

    def test_provider_error_object(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get",
                        return_value=FakeResp(status_code=200, json_data={"error": "limit exceeded"})):
            with self.assertRaises(OutscraperError) as ctx:
                a.list_reviews_by_place_id(PLACE)
        self.assertIn("limit exceeded", ctx.exception.message)

    def test_empty_result(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        fake = make_fake_get(reviews=[])
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", fake):
            items = a.list_reviews_by_place_id(PLACE)
        self.assertEqual(items, [])

    def test_pagination(self):
        many = FIXTURE_REVIEWS * 60  # 240 reviews
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0, page_size=100)
        fake = make_fake_get(reviews=many)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", fake):
            items = []
            offset = 0
            while True:
                page = a.list_reviews_by_place_id(PLACE, limit=100, offset=offset)
                items.extend(page)
                if len(page) < 100:
                    break
                offset += 100
        self.assertEqual(len(items), 240)
        self.assertEqual(fake.calls["n"], 3)  # exactly three pages

    def test_incremental_since_filter(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        fake = make_fake_get()
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", fake):
            items = a.list_reviews_by_place_id(PLACE, since="2026-07-30T00:00:00")
        self.assertEqual(len(items), 1)  # only rv-001 (2026-08-01)
        self.assertEqual(items[0]["source_review_id"], "rv-001")

    def test_rating_only(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", make_fake_get()):
            items = a.list_reviews_by_place_id(PLACE)
        ro = next(i for i in items if i["source_review_id"] == "rv-003")
        self.assertEqual(ro["review_text"], "")
        self.assertEqual(ro["rating"], 1)

    def test_owner_reply(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", make_fake_get()):
            items = a.list_reviews_by_place_id(PLACE)
        rv = next(i for i in items if i["source_review_id"] == "rv-001")
        self.assertEqual(rv["owner_reply_text"], "Terima kasih, Kak!")
        self.assertIsNotNone(rv["owner_reply_date"])

    def test_reviewer_masking(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", make_fake_get()):
            items = a.list_reviews_by_place_id(PLACE)
        rv = next(i for i in items if i["source_review_id"] == "rv-001")
        self.assertEqual(rv["reviewer_name_masked"], "Budi S***")

    def test_source_labeling(self):
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", make_fake_get()):
            items = a.list_reviews_by_place_id(PLACE)
        self.assertTrue(all(i["source"] == "outscraper" for i in items))

    def test_deterministic_fallback_id(self):
        from app.adapters.outscraper_public_review_adapter import _deterministic_review_id
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", make_fake_get()):
            items = a.list_reviews_by_place_id(PLACE)
        noid = next(i for i in items if i["source_review_id"].startswith("hash_"))
        self.assertTrue(noid["source_review_id"].startswith("hash_"))
        # Deterministic: same payload → same id
        again = _deterministic_review_id(PLACE, FIXTURE_REVIEWS[3])
        self.assertEqual(noid["source_review_id"], again)

    def test_geographic_unknown(self):
        loc = dict(FIXTURE_LOCATION)
        loc["city"] = None
        loc["state"] = None
        loc["district"] = None
        a = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get",
                        make_fake_get(location=loc)):
            out = a.fetch_location(PLACE)
        self.assertIsNone(out["province"])
        self.assertIsNone(out["city_regency"])


# ─── SYNC WITH OUTSCRAPER ──────────────────────────────────
class TestSyncOutscraper(GateKBase):
    def test_sync_creates_reviews(self):
        oid = self._make_outlet()
        rep = self._sync_outscraper(make_fake_get(), outlet_ids=[oid])
        self.assertEqual(rep["provider"], "outscraper")
        self.assertEqual(rep["reviews_created"], 4)
        self.assertEqual(rep["locations_succeeded"], 1)
        with self.app.app_context():
            self.assertEqual(Review.query.filter_by(outlet_id=oid).count(), 4)

    def test_raw_payload_preserved(self):
        oid = self._make_outlet()
        self._sync_outscraper(make_fake_get(), outlet_ids=[oid])
        with self.app.app_context():
            rp = ReviewRawPayload.query.filter_by(tenant_id="tenant-k-1").first()
            self.assertIsNotNone(rp)
            self.assertEqual(rp.source, "outscraper")
            self.assertIn("review_likes", rp.raw_payload)

    def test_duplicate_prevention(self):
        oid = self._make_outlet()
        rep1 = self._sync_outscraper(make_fake_get(), outlet_ids=[oid])
        rep2 = self._sync_outscraper(make_fake_get(), outlet_ids=[oid], full_sync=True)
        self.assertEqual(rep1["reviews_created"], 4)
        self.assertEqual(rep2["reviews_created"], 0)
        self.assertGreaterEqual(rep2["reviews_skipped"], 4)

    def test_review_update_versioning(self):
        oid = self._make_outlet()
        self._sync_outscraper(make_fake_get(), outlet_ids=[oid])
        # Provider returns updated text/rating for rv-002
        updated = [dict(r) for r in FIXTURE_REVIEWS]
        updated[1]["review_rating"] = 3
        updated[1]["review_text"] = "Porsi kecil, tapi rasanya membaik."
        updated[1]["review_datetime_utc"] = "2026-07-26T08:10:00"
        rep = self._sync_outscraper(make_fake_get(reviews=updated), outlet_ids=[oid], full_sync=True)
        self.assertEqual(rep["reviews_updated"], 1)
        with self.app.app_context():
            rv = Review.query.filter_by(tenant_id="tenant-k-1", outlet_id=oid).filter(
                Review.comment.like("%membaik%")).first()
            self.assertEqual(rv.current_version, 2)
            versions = ReviewVersion.query.filter_by(review_pk=rv.id).count()
            self.assertEqual(versions, 2)

    def test_sync_statistics(self):
        oid = self._make_outlet()
        rep = self._sync_outscraper(make_fake_get(), outlet_ids=[oid])
        self.assertEqual(rep["reviews_inserted"], 4)
        self.assertEqual(rep["reviews_updated"], 0)
        self.assertEqual(rep["reviews_skipped"], 0)
        self.assertEqual(rep["sync_status"], "ok")
        self.assertEqual(rep["error_summary"], [])
        with self.app.app_context():
            s = SyncReport.query.filter_by(tenant_id="tenant-k-1").order_by(
                SyncReport.created_at.desc()).first()
            self.assertEqual(s.source, "outscraper")

    def test_previous_data_retained_on_failure(self):
        oid = self._make_outlet()
        self._sync_outscraper(make_fake_get(), outlet_ids=[oid])
        with self.app.app_context():
            before = Review.query.filter_by(outlet_id=oid).count()
        self.assertEqual(before, 4)

        def failing_get(url, params=None, headers=None, timeout=None):
            raise OutscraperError("provider down", status_code=500, retryable=True)

        adapter = OutscraperPublicReviewAdapter(api_key="k", max_retries=0)
        with mock.patch("app.adapters.outscraper_public_review_adapter.requests.get", failing_get):
            from app.services.sync_service import sync_public_reviews
            with self.app.app_context():
                rep = sync_public_reviews(
                    tenant_id="tenant-k-1", business_id="biz-k-1",
                    outlet_ids=[oid], adapter=adapter,
                )
        self.assertEqual(rep["locations_failed"], 1)
        self.assertEqual(rep["sync_status"], "partial_failure")
        self.assertEqual(len(rep["error_summary"]), 1)
        with self.app.app_context():
            after = Review.query.filter_by(outlet_id=oid).count()
        self.assertEqual(after, 4)  # previous data retained

    def test_harjamukti_excluded(self):
        rep = self._sync_outscraper(make_fake_get())
        with self.app.app_context():
            hj = Outlet.query.filter_by(id="outlet-k-hj").first()
            cnt = Review.query.filter_by(outlet_id=hj.id).count()
        self.assertEqual(cnt, 0)
        self.assertNotIn("outlet-k-hj", [e.get("outlet") for e in rep["error_summary"]])

    def test_tenant_isolation(self):
        oid = self._make_outlet()
        self._sync_outscraper(make_fake_get(), outlet_ids=[oid])
        with self.app.app_context():
            cnt = Review.query.filter_by(tenant_id="tenant-k-2").count()
        self.assertEqual(cnt, 0)

    def test_direct_reply_disabled(self):
        oid = self._make_outlet()
        self._sync_outscraper(make_fake_get(), outlet_ids=[oid])
        with self.app.app_context():
            o = Outlet.query.get(oid)
            self.assertFalse(o.reply_enabled)

    def test_auto_reply_off(self):
        from app.services.feature_flags import is_auto_reply_enabled
        self.assertFalse(is_auto_reply_enabled())

    def test_no_silent_mock_fallback(self):
        os.environ["PUBLIC_REVIEW_PROVIDER"] = "outscraper"
        os.environ.pop("OUTSCRAPER_API_KEY", None)
        try:
            with self.assertRaises(ValueError):
                build_public_review_adapter()
            # Direct sync without adapter must also raise (not fall back to mock)
            from app.services.sync_service import sync_public_reviews
            with self.app.app_context():
                with self.assertRaises(ValueError):
                    sync_public_reviews(tenant_id="tenant-k-1", business_id="biz-k-1")
        finally:
            os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

    def test_unknown_provider_rejected(self):
        os.environ["PUBLIC_REVIEW_PROVIDER"] = "playwright"
        try:
            with self.assertRaises(ValueError):
                build_public_review_adapter()
        finally:
            os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"


# ─── EXPORT METADATA ───────────────────────────────────────
class TestExportMetadata(GateKBase):
    def test_export_csv_has_filter_metadata(self):
        r = self.client.get("/api/public/analytics/export.csv?city_regency=Depok&rating=5")
        self.assertEqual(r.status_code, 200)
        lines = r.data.decode().splitlines()
        self.assertTrue(any(l.startswith("# generated_at:") for l in lines))
        self.assertTrue(any(l.startswith("# kota_kabupaten: Depok") for l in lines))
        self.assertTrue(any(l.startswith("# rating: 5") for l in lines))

    def test_export_xlsx_has_info_sheet(self):
        from openpyxl import load_workbook
        r = self.client.get("/api/public/analytics/export.xlsx?category=rasa/kualitas produk")
        self.assertEqual(r.status_code, 200)
        wb = load_workbook(io.BytesIO(r.data))
        self.assertIn("Export Info", wb.sheetnames)
        ws = wb["Export Info"]
        rows = {str(c.value): str(r.value) for c, r in zip(ws[1], ws[2])}
        # keys are in column A, values in column B
        info = {ws.cell(row=i, column=1).value: ws.cell(row=i, column=2).value for i in range(1, ws.max_row + 1)}
        self.assertIn("generated_at", info)
        self.assertEqual(info["kategori"], "rasa/kualitas produk")


if __name__ == "__main__":
    unittest.main(verbosity=2)
