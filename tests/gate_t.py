"""Gate T — Perbaikan #1-4: advisor all-time default, lowest/highest recap,
branch comparison. No backend/engine changes."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_t.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review


class GateTBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-t-1", tenant_id="tenant-t-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-t-1", email="admin@buburfay.id",
                     password_hash=generate_password_hash("pw1"), display_name="Owner",
                     business_id="biz-t-1", role="superadmin", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()
            o1 = Outlet(id="out-t-1", tenant_id="tenant-t-1", business_id="biz-t-1",
                        name="Bubur Fay Bekasi", public_place_id="X1", status="active",
                        monitor_enabled=True, reply_enabled=False, business_rating=4.5,
                        city_regency="Bekasi")
            o2 = Outlet(id="out-t-2", tenant_id="tenant-t-1", business_id="biz-t-1",
                        name="Bubur Fay Depok", public_place_id="X2", status="active",
                        monitor_enabled=True, reply_enabled=False, business_rating=3.2,
                        city_regency="Depok")
            db.session.add_all([o1, o2])
            db.session.commit()
            seed = [
                ("out-t-1", "Enak sekali!", 5, datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc)),
                ("out-t-2", "Pelayanan sangat buruk", 1, datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)),
                ("out-t-2", "Porsi mengecil", 2, datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc)),
                ("out-t-1", "Mantap buburnya", 5, datetime(2026, 7, 5, 8, 0, tzinfo=timezone.utc)),
            ]
            for i, (oid, txt, star, dt) in enumerate(seed):
                db.session.add(Review(tenant_id="tenant-t-1", business_id="biz-t-1", outlet_id=oid,
                                      source="mock", source_review_name=f"t:{i}", star_rating=star,
                                      comment=txt, has_text=True, create_time=dt))
            db.session.commit()

    def _html(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        return c.get("/dashboard/").data.decode()


class TestPerbaikan(GateTBase):
    def test_advisor_default_all_time(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        adv = c.get("/dashboard/advisor").data.decode()
        self.assertIn("Seluruh Waktu", adv)
        self.assertIn("start_date=2000-01-01", adv)  # default fetch = all time

    def test_lowest_recap_panel(self):
        html = self._html()
        self.assertIn("Rekap Rating Terendah", html)
        self.assertIn("Pelayanan sangat buruk", html)  # lowest review from data
        self.assertIn("Bubur Fay Depok", html)  # branch labeled

    def test_highest_recap_panel(self):
        html = self._html()
        self.assertIn("Rekap Rating Tertinggi", html)
        self.assertIn("Enak sekali!", html)  # highest review from data

    def test_branch_comparison_badges(self):
        html = self._html()
        self.assertIn("Performa Outlet", html)
        self.assertIn("Terbaik", html)   # Bekasi 4.5
        self.assertIn("Perlu Perhatian", html)  # Depok 3.2

    def test_add_outlet_cta(self):
        html = self._html()
        self.assertIn("+ Tambah Outlet", html)

    def test_all_time_default_kpi(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        html = c.get("/dashboard/").data.decode()
        self.assertIn("Semua Waktu", html)  # period label default


if __name__ == "__main__":
    unittest.main(verbosity=2)
