"""Gate Y — RUN_Q1 implementasi: default periode seragam, label metadata,
konsistensi angka all-time."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_y.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review


class GateYBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-y-1", tenant_id="tenant-y-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-y-1", email="admin@buburfay.id",
                     password_hash=generate_password_hash("pw1"), display_name="Owner",
                     business_id="biz-y-1", role="superadmin", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()
            o1 = Outlet(id="out-y-1", tenant_id="tenant-y-1", business_id="biz-y-1",
                        name="Bubur Fay Bekasi", public_place_id="X1", status="active",
                        monitor_enabled=True, reply_enabled=False, city_regency="Bekasi",
                        business_review_count=438, business_rating=4.5)
            o2 = Outlet(id="out-y-2", tenant_id="tenant-y-1", business_id="biz-y-1",
                        name="Bubur Fay RTM", public_place_id="X2", status="active",
                        monitor_enabled=True, reply_enabled=False, city_regency="Depok",
                        business_review_count=71, business_rating=4.8)
            db.session.add_all([o1, o2])
            db.session.commit()
            for i, (oid, star, dt) in enumerate([
                ("out-y-1", 5, datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc)),
                ("out-y-1", 4, datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc)),
                ("out-y-2", 5, datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)),
            ]):
                db.session.add(Review(tenant_id="tenant-y-1", business_id="biz-y-1", outlet_id=oid,
                                      source="mock", source_review_name=f"y:{i}", star_rating=star,
                                      comment="ok", has_text=True, create_time=dt))
            db.session.commit()

    def _client(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        return c


class TestConsistency(GateYBase):
    def test_performa_default_all(self):
        c = self._client()
        html = c.get("/dashboard/performa").data.decode()
        self.assertIn('<option value="all" selected>Seluruh Waktu</option>', html)
        self.assertNotIn('<option value="30" selected>', html)

    def test_performa_period_label(self):
        c = self._client()
        html = c.get("/dashboard/performa").data.decode()
        self.assertIn("currentPeriodLabel", html)
        self.assertIn("Periode:", html)

    def test_metadata_label_dashboard(self):
        c = self._client()
        html = c.get("/dashboard/").data.decode()
        self.assertIn("Review di Google", html)

    def test_metadata_label_outlet(self):
        c = self._client()
        html = c.get("/dashboard/outlets").data.decode()
        self.assertIn("review di Google", html)

    def test_numbers_consistent_alltime(self):
        c = self._client()
        # summary all-time total = sum of DB reviews
        s = c.get("/api/public/analytics/summary?start_date=2000-01-01").get_json()
        self.assertEqual(s["total_reviews"], 3)
        # performance all-time per outlet
        p = c.get("/api/public/analytics/outlets?start_date=2000-01-01").get_json()
        by_name = {b["branch_name"]: b for b in p["outlets"]}
        self.assertEqual(by_name["Bubur Fay Bekasi"]["review_count"], 2)
        self.assertEqual(by_name["Bubur Fay Bekasi"]["avg_rating"], 4.5)
        self.assertEqual(by_name["Bubur Fay RTM"]["review_count"], 1)
        # same period (30d) → both agree
        p30 = c.get("/api/public/analytics/outlets?days=30").get_json()
        b30 = {b["branch_name"]: b for b in p30["outlets"]}
        self.assertEqual(b30["Bubur Fay Bekasi"]["review_count"], 1)

    def test_compare_consistent(self):
        c = self._client()
        cmp_all = c.get("/api/public/analytics/compare?outlet_a=out-y-1&outlet_b=out-y-2&start_date=2000-01-01").get_json()
        self.assertEqual(cmp_all["rating"]["a"], 4.5)
        self.assertEqual(cmp_all["review_count"]["a"], 2)
        cmp30 = c.get("/api/public/analytics/compare?outlet_a=out-y-1&outlet_b=out-y-2&days=30").get_json()
        self.assertEqual(cmp30["rating"]["a"], 5.0)  # only 1 review in 30d


if __name__ == "__main__":
    unittest.main(verbosity=2)
