"""Gate V — Performa Outlet: per-outlet ranking, 1v1 compare, per-city."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_v.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review


class GateVBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-v-1", tenant_id="tenant-v-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-v-1", email="admin@buburfay.id",
                     password_hash=generate_password_hash("pw1"), display_name="Owner",
                     business_id="biz-v-1", role="superadmin", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()
            o1 = Outlet(id="out-v-1", tenant_id="tenant-v-1", business_id="biz-v-1",
                        name="Bubur Fay Bekasi", public_place_id="X1", status="active",
                        monitor_enabled=True, reply_enabled=False, city_regency="Bekasi")
            o2 = Outlet(id="out-v-2", tenant_id="tenant-v-1", business_id="biz-v-1",
                        name="Bubur Fay Depok", public_place_id="X2", status="active",
                        monitor_enabled=True, reply_enabled=False, city_regency="Depok")
            db.session.add_all([o1, o2])
            db.session.commit()
            seed = [
                ("out-v-1", "Enak sekali!", 5), ("out-v-1", "Mantap", 5), ("out-v-1", "Biasa", 3),
                ("out-v-2", "Pelayanan sangat buruk", 1), ("out-v-2", "Porsi mengecil", 2),
            ]
            for i, (oid, txt, star) in enumerate(seed):
                db.session.add(Review(tenant_id="tenant-v-1", business_id="biz-v-1", outlet_id=oid,
                                      source="mock", source_review_name=f"v:{i}", star_rating=star,
                                      comment=txt, has_text=True,
                                      create_time=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc)))
            db.session.commit()

    def _get(self, path):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        return c.get(path)


class TestPerforma(GateVBase):
    def test_outlet_performance_ranking(self):
        r = self._get("/api/public/analytics/outlets?start_date=2000-01-01")
        self.assertEqual(r.status_code, 200)
        outlets = r.get_json()["outlets"]
        self.assertEqual(len(outlets), 2)
        # Bekasi (avg 4.33) ranks above Depok (1.5)
        self.assertEqual(outlets[0]["branch_name"], "Bubur Fay Bekasi")
        self.assertEqual(outlets[0]["rank"], 1)
        self.assertEqual(outlets[1]["rank"], 2)

    def test_city_performance(self):
        r = self._get("/api/public/analytics/cities?start_date=2000-01-01")
        cities = r.get_json()["cities"]
        by_city = {c["city"]: c for c in cities}
        self.assertIn("Bekasi", by_city)
        self.assertIn("Depok", by_city)
        self.assertEqual(by_city["Bekasi"]["branch_count"], 1)
        self.assertGreater(by_city["Bekasi"]["avg_rating"], by_city["Depok"]["avg_rating"])

    def test_compare_1v1(self):
        r = self._get("/api/public/analytics/compare?outlet_a=out-v-1&outlet_b=out-v-2&start_date=2000-01-01")
        d = r.get_json()
        self.assertEqual(d["outlet_a"]["name"], "Bubur Fay Bekasi")
        self.assertEqual(d["outlet_b"]["name"], "Bubur Fay Depok")
        self.assertEqual(d["rating"]["winner"], "Bubur Fay Bekasi")
        self.assertIn("complaints_a", d)
        self.assertIn("praise_b", d)

    def test_compare_missing_outlet(self):
        r = self._get("/api/public/analytics/compare?outlet_a=out-v-1&outlet_b=nope&start_date=2000-01-01")
        self.assertIn("error", r.get_json())

    def test_performa_page(self):
        r = self._get("/dashboard/performa")
        self.assertEqual(r.status_code, 200)
        html = r.data.decode()
        for t in ("Performa per Outlet", "Bandingkan 1 vs 1", "Perbandingan per Kota"):
            self.assertIn(t, html)

    def test_performa_nav(self):
        html = self._get("/dashboard/").data.decode()
        self.assertIn("/dashboard/performa", html)  # sidebar link


if __name__ == "__main__":
    unittest.main(verbosity=2)
