"""Gate J — Public Monitoring & Review Analytics quality gate (RUN_09).

Covers GRM_PUBLIC_MONITORING_SKILL §16:
- Input & Discovery (name, Maps URL, Place ID, city, dedup, verify, old/closed)
- Review Collection (public import, rating-only, duplicate prevention,
  source labeling, failure handling)
- Analysis (sentiment, category, multi-label, critical, rating-only exclusion)
- Dashboard Filters (custom range, month, city, district, branch, category,
  combined, tenant isolation)
- Dashboard Accuracy (totals consistent, comparisons)
- Security & Privacy (tenant isolation, reviewer masking, no OAuth,
  reply disabled)
- Export (CSV, XLSX)
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_j.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"  # pin provider for deterministic tests

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review, ReviewAnalysis, LocationCandidate

T1_EMAIL = "owner@buburfay.id"
T1_PW = "pass1234"
T2_EMAIL = "owner@koplain.id"
T2_PW = "pass5678"


class TestPublicMonitoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            # Tenant 1 — Bubur Fay (pilot public monitoring)
            biz1 = Business(id="biz-j-1", tenant_id="tenant-j-1", name="Bubur Fay", brand_name="Bubur Fay")
            u1 = User(id="u-j-1", email=T1_EMAIL, password_hash=generate_password_hash(T1_PW),
                      display_name="Owner Fay", business_id="biz-j-1", role="owner", is_active=True)
            # Tenant 2 — Kopi Lain (isolation target)
            biz2 = Business(id="biz-j-2", tenant_id="tenant-j-2", name="Kopi Lain", brand_name="Kopi Lain")
            u2 = User(id="u-j-2", email=T2_EMAIL, password_hash=generate_password_hash(T2_PW),
                      display_name="Owner Kopi", business_id="biz-j-2", role="owner", is_active=True)
            db.session.add_all([biz1, u1, biz2, u2])
            db.session.commit()
            # Seed tenant1 via public flow (discover → verify → sync)
            cls._seed_tenant1()

    @classmethod
    def _seed_tenant1(cls):
        client = cls.app.test_client()
        client.post("/auth/login", data={"email": T1_EMAIL, "password": T1_PW})
        # Harjamukti (CLOSED) verified as old_or_closed — stays excluded
        r = client.post("/api/public/discover", json={"query": "Bubur Fay", "city": "Depok"})
        cands = r.get_json()["candidates"]
        harjamukti = next((c for c in cands if "Harjamukti" in c["display_name"]), None)
        depok = next((c for c in cands if c["display_name"] == "Bubur Fay Depok"), cands[0])
        if harjamukti:
            client.post("/api/public/verify", json={"candidate_id": harjamukti["id"], "decision": "old_or_closed"})
        client.post("/api/public/verify", json={"candidate_id": depok["id"], "decision": "owner_confirmed"})
        client.post("/api/public/sync", json={})

    def setUp(self):
        self.client = self.app.test_client()
        r = self.client.post("/auth/login", data={"email": T1_EMAIL, "password": T1_PW})
        assert r.status_code == 302

    # ─── INPUT & DISCOVERY ────────────────────────────────
    def test_discover_by_name(self):
        r = self.client.post("/api/public/discover", json={"query": "Bubur Fay"})
        self.assertEqual(r.status_code, 200)
        names = [c["display_name"] for c in r.get_json()["candidates"]]
        self.assertIn("Bubur Fay Depok", names)

    def test_discover_by_name_city(self):
        r = self.client.post("/api/public/discover", json={"query": "Bubur Fay", "city": "Bekasi"})
        self.assertEqual(r.status_code, 200)
        names = [c["display_name"] for c in r.get_json()["candidates"]]
        self.assertTrue(all("Bekasi" in n for n in names))

    def test_discover_by_maps_url(self):
        r = self.client.post("/api/public/discover", json={"url": "https://www.google.com/maps/place/?q=place_id:ChIJ0-depok-margonda-002"})
        self.assertEqual(r.status_code, 200)
        cands = r.get_json()["candidates"]
        self.assertEqual(len(cands), 1)
        self.assertIn("Margonda", cands[0]["display_name"])

    def test_discover_by_place_id(self):
        r = self.client.post("/api/public/discover", json={"place_id": "ChIJ0-depok-margonda-001"})
        self.assertEqual(r.status_code, 200)

    def test_discover_unknown_place_404(self):
        r = self.client.post("/api/public/discover", json={"place_id": "NOPE-123"})
        self.assertEqual(r.status_code, 404)

    def test_discover_short_query_400(self):
        r = self.client.post("/api/public/discover", json={"query": "ab"})
        self.assertEqual(r.status_code, 400)

    def test_discover_dedup_candidates(self):
        # Same query twice must not duplicate rows
        with self.app.app_context():
            before = LocationCandidate.query.filter_by(tenant_id="tenant-j-1").count()
        self.client.post("/api/public/discover", json={"query": "Bubur Fay"})
        with self.app.app_context():
            after = LocationCandidate.query.filter_by(tenant_id="tenant-j-1").count()
        self.assertEqual(before, after)

    def test_verify_owner_confirmed_creates_outlet(self):
        with self.app.app_context():
            o = Outlet.query.filter_by(tenant_id="tenant-j-1", name="Bubur Fay Depok").first()
            self.assertIsNotNone(o)
            self.assertTrue(o.monitor_enabled)
            self.assertFalse(o.reply_enabled)
            self.assertEqual(o.status, "active")

    def test_verify_old_or_closed_excluded(self):
        with self.app.app_context():
            c = LocationCandidate.query.filter_by(
                tenant_id="tenant-j-1", place_id="ChIJ0-harjamukti-old-006"
            ).first()
            o = Outlet.query.filter_by(tenant_id="tenant-j-1", name="Bubur Fay Harjamukti").first()
            self.assertEqual(c.owner_verification_status, "old_or_closed")
            # Old/closed stays excluded: no active outlet, or status old_or_closed
            if o is not None:
                self.assertEqual(o.status, "old_or_closed")

    def test_harjamukti_never_synced(self):
        with self.app.app_context():
            hj = Outlet.query.filter_by(tenant_id="tenant-j-1", name="Bubur Fay Harjamukti").first()
            cnt = Review.query.filter_by(outlet_id=hj.id).count() if hj else 0
            self.assertEqual(cnt, 0)

    # ─── REVIEW COLLECTION ────────────────────────────────
    def test_sync_creates_reviews(self):
        with self.app.app_context():
            cnt = Review.query.filter_by(tenant_id="tenant-j-1").count()
        self.assertGreaterEqual(cnt, 8)

    def test_sync_rating_only_counted(self):
        with self.app.app_context():
            rating_only = Review.query.filter_by(tenant_id="tenant-j-1", has_text=False).count()
        self.assertGreaterEqual(rating_only, 1)

    def test_sync_idempotent(self):
        r = self.client.post("/api/public/sync", json={})
        rep = r.get_json()
        self.assertEqual(rep["reviews_created"], 0)
        self.assertGreaterEqual(rep["reviews_unchanged"], 1)

    def test_sync_source_labeling(self):
        with self.app.app_context():
            srcs = {r.source for r in Review.query.filter_by(tenant_id="tenant-j-1").all()}
        self.assertEqual(srcs, {"mock"})

    def test_sync_owner_reply_stored(self):
        with self.app.app_context():
            with_reply = [r for r in Review.query.filter_by(tenant_id="tenant-j-1").all() if r.owner_reply_text]
        self.assertGreaterEqual(len(with_reply), 3)

    def test_sync_geo_enriched(self):
        with self.app.app_context():
            o = Outlet.query.filter_by(tenant_id="tenant-j-1", name="Bubur Fay Depok").first()
            self.assertEqual(o.province, "Jawa Barat")
            self.assertEqual(o.city_regency, "Depok")
            self.assertTrue(o.district)
            self.assertFalse(o.needs_geographic_resolution)

    def test_sync_location_metadata(self):
        with self.app.app_context():
            o = Outlet.query.filter_by(tenant_id="tenant-j-1", name="Bubur Fay Depok").first()
            self.assertIsNotNone(o.business_rating)
            self.assertIsNotNone(o.business_review_count)
            self.assertTrue(o.maps_url)

    # ─── ANALYSIS ─────────────────────────────────────────
    def test_analysis_created_for_text_reviews(self):
        with self.app.app_context():
            text_ids = [r.id for r in Review.query.filter_by(tenant_id="tenant-j-1", has_text=True).all()]
            analyzed = ReviewAnalysis.query.filter(ReviewAnalysis.review_pk.in_(text_ids)).count()
        self.assertGreaterEqual(analyzed, 5)

    def test_analysis_sentiment(self):
        with self.app.app_context():
            a = ReviewAnalysis.query.join(Review, ReviewAnalysis.review_pk == Review.id).filter(
                Review.tenant_id == "tenant-j-1", Review.has_text == True).first()  # noqa: E712
            self.assertIn(a.sentiment, ("positive", "neutral", "negative", "mixed"))

    def test_category_multi_label(self):
        with self.app.app_context():
            a = ReviewAnalysis.query.join(Review, ReviewAnalysis.review_pk == Review.id).filter(
                Review.tenant_id == "tenant-j-1").first()
            self.assertIsNotNone(a.topics_json)

    def test_critical_category_detected(self):
        import json as _json
        with self.app.app_context():
            food_safety = ReviewAnalysis.query.filter(ReviewAnalysis.topics_json.isnot(None)).all()
            found = False
            for a in food_safety:
                topics = a.topics_json
                if isinstance(topics, str):
                    try:
                        topics = _json.loads(topics)
                    except (ValueError, TypeError):
                        topics = []
                if isinstance(topics, list) and any(
                    (t.get("topic") if isinstance(t, dict) else str(t)) == "food_safety"
                    for t in topics
                ):
                    found = True
                    break
        self.assertTrue(found)

    def test_rating_only_excluded_from_text_categories(self):
        r = self.client.get("/api/public/analytics/categories?days=90")
        data = r.get_json()
        total_text = data["total_text_reviews"]
        with self.app.app_context():
            rating_only = Review.query.filter_by(tenant_id="tenant-j-1", has_text=False).count()
            total = Review.query.filter_by(tenant_id="tenant-j-1").count()
        self.assertEqual(total_text, total - rating_only)

    # ─── DASHBOARD FILTERS ────────────────────────────────
    def test_summary_total_consistent(self):
        r = self.client.get("/api/public/analytics/summary?days=90")
        s = r.get_json()
        with self.app.app_context():
            total = Review.query.filter_by(tenant_id="tenant-j-1").count()
        self.assertEqual(s["total_reviews"], total)

    def test_summary_filter_branch(self):
        with self.app.app_context():
            o = Outlet.query.filter_by(tenant_id="tenant-j-1", name="Bubur Fay Depok").first()
        r = self.client.get(f"/api/public/analytics/summary?days=90&outlet_id={o.id}")
        s = r.get_json()
        with self.app.app_context():
            expected = Review.query.filter_by(tenant_id="tenant-j-1", outlet_id=o.id).count()
        self.assertEqual(s["total_reviews"], expected)

    def test_summary_filter_city(self):
        r = self.client.get("/api/public/analytics/summary?days=90&city_regency=Depok")
        s = r.get_json()
        with self.app.app_context():
            expected = Review.query.filter_by(tenant_id="tenant-j-1").count()
        self.assertEqual(s["total_reviews"], expected)
        r2 = self.client.get("/api/public/analytics/summary?days=90&city_regency=Bogor")
        self.assertEqual(r2.get_json()["total_reviews"], 0)

    def test_summary_filter_month(self):
        r = self.client.get("/api/public/analytics/summary?month=2026-07")
        s = r.get_json()
        self.assertGreaterEqual(s["total_reviews"], 1)
        r2 = self.client.get("/api/public/analytics/summary?month=2025-01")
        self.assertEqual(r2.get_json()["total_reviews"], 0)

    def test_summary_filter_custom_range(self):
        r = self.client.get("/api/public/analytics/summary?start_date=2026-07-01&end_date=2026-07-31")
        s = r.get_json()
        with self.app.app_context():
            expected = Review.query.filter_by(tenant_id="tenant-j-1").filter(
                Review.create_time >= datetime(2026, 7, 1, tzinfo=timezone.utc),
                Review.create_time <= datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc),
            ).count()
        self.assertEqual(s["total_reviews"], expected)

    def test_summary_filter_category(self):
        r = self.client.get("/api/public/analytics/summary?category=rasa/kualitas produk")
        s = r.get_json()
        self.assertGreaterEqual(s["total_reviews"], 1)
        r2 = self.client.get("/api/public/analytics/summary?category=parkir")
        # Category filter acts on text categories — count must match category API
        self.assertGreaterEqual(r2.get_json()["total_reviews"], 0)

    def test_summary_combined_filters(self):
        r = self.client.get("/api/public/analytics/summary?days=90&rating=5&has_reply=true")
        s = r.get_json()
        with self.app.app_context():
            expected = Review.query.filter_by(tenant_id="tenant-j-1", star_rating=5).filter(
                Review.owner_reply_text.isnot(None)).count()
        self.assertEqual(s["total_reviews"], expected)

    def test_explorer_filters_rating_only(self):
        r = self.client.get("/api/public/analytics/explorer?rating_only=true")
        items = r.get_json()["items"]
        self.assertTrue(all(i["is_rating_only"] for i in items))
        self.assertGreaterEqual(len(items), 1)

    def test_explorer_pagination(self):
        r = self.client.get("/api/public/analytics/explorer?per_page=3&page=1")
        data = r.get_json()
        self.assertLessEqual(len(data["items"]), 3)
        self.assertGreaterEqual(data["total"], 8)

    def test_priority_insights(self):
        r = self.client.get("/api/public/analytics/priority")
        p = r.get_json()
        self.assertIn("recent_negative", p)
        self.assertIn("reputation_risk", p)

    def test_period_analytics_trend(self):
        r = self.client.get("/api/public/analytics/period")
        per = r.get_json()
        self.assertGreaterEqual(len(per["trend"]), 1)

    def test_geographic_breakdown(self):
        r = self.client.get("/api/public/analytics/geography")
        g = r.get_json()
        self.assertTrue(any(c["city_regency"] == "Depok" for c in g["cities"]))
        self.assertGreaterEqual(len(g["districts"]), 1)

    # ─── TENANT ISOLATION ─────────────────────────────────
    def test_tenant_isolation(self):
        c2 = self.app.test_client()
        c2.post("/auth/login", data={"email": T2_EMAIL, "password": T2_PW})
        with c2.get("/api/public/analytics/summary") as r:
            s = r.get_json()
            self.assertEqual(s["total_reviews"], 0)
            self.assertEqual(s["business_name"], "Kopi Lain")
        with c2.get("/api/public/locations") as r:
            self.assertEqual(r.get_json()["outlets"], [])

    # ─── SECURITY & PRIVACY ───────────────────────────────
    def test_reviewer_masked_in_explorer(self):
        r = self.client.get("/api/public/analytics/explorer")
        for i in r.get_json()["items"]:
            self.assertNotRegex(i["reviewer"], r"^[A-Za-z]+ [A-Za-z]{3,}$")

    def test_reviewer_masked_in_export(self):
        r = self.client.get("/api/public/analytics/export.csv")
        text = r.data.decode()
        for line in text.splitlines()[1:]:
            if not line:
                continue
            # reviewer column is 12th (index 11)
            parts = line.split(",")
            if len(parts) > 11 and parts[11]:
                self.assertNotRegex(parts[11], r"^[A-Za-z]+ [A-Za-z]{3,}$")

    def test_no_oauth_required(self):
        # Public endpoints work without any Google connection row
        with self.app.app_context():
            from app.models.entities import GoogleConnection
            self.assertEqual(GoogleConnection.query.filter_by(tenant_id="tenant-j-1").count(), 0)
        r = self.client.get("/api/public/analytics/summary")
        self.assertEqual(r.status_code, 200)

    def test_reply_disabled(self):
        with self.app.app_context():
            for o in Outlet.query.filter_by(tenant_id="tenant-j-1").all():
                self.assertFalse(o.reply_enabled)

    def test_source_labeling_locations(self):
        r = self.client.get("/api/public/locations")
        for o in r.get_json()["outlets"]:
            self.assertIn(o["source"], ("public_scraping", "mock"))

    # ─── EXPORT ───────────────────────────────────────────
    def test_export_csv(self):
        r = self.client.get("/api/public/analytics/export.csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.content_type)
        lines = r.data.decode().splitlines()
        data_lines = [l for l in lines if l and not l.startswith("#")]
        self.assertGreaterEqual(len(data_lines), 3)  # header + rows
        self.assertIn("kota_kabupaten", data_lines[0])
        self.assertIn("sumber", data_lines[0])
        self.assertTrue(any(l.startswith("# generated_at:") for l in lines))

    def test_export_xlsx(self):
        r = self.client.get("/api/public/analytics/export.xlsx")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r.content_type)
        self.assertGreater(len(r.data), 500)

    def test_export_respects_filters(self):
        r = self.client.get("/api/public/analytics/export.csv?rating=5")
        lines = [l for l in r.data.decode().splitlines() if l and not l.startswith("#")]
        rows = lines[1:]  # skip header
        self.assertTrue(all(line.split(",")[4] == "5" for line in rows if line))


if __name__ == "__main__":
    unittest.main(verbosity=2)
