"""Gate O — Dashboard Simplification & Owner Experience (M2).

Covers: layout render, mobile render, menu role, advisor card, summary card,
dashboard performance. Uses mock provider (deterministic), no live HTTP.
"""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_o.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review


class GateOBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-o-1", tenant_id="tenant-o-1", name="Bubur Fay", brand_name="Bubur Fay")
            admin = User(id="u-o-1", email="admin@buburfay.id",
                         password_hash=generate_password_hash("pw1"), display_name="Owner",
                         business_id="biz-o-1", role="superadmin", is_active=True)
            viewer = User(id="u-o-2", email="viewer@buburfay.id",
                          password_hash=generate_password_hash("pw2"), display_name="Staf",
                          business_id="biz-o-1", role="viewer", is_active=True)
            db.session.add_all([biz, admin, viewer])
            db.session.commit()
            o = Outlet(id="out-o-1", tenant_id="tenant-o-1", business_id="biz-o-1",
                       name="Bubur Fay Bekasi", public_place_id="X1", status="active",
                       monitor_enabled=True, reply_enabled=False, business_rating=4.5,
                       business_review_count=438, city_regency="Bekasi", district="Pondok Gede")
            db.session.add(o)
            db.session.commit()
            for i in range(3):
                db.session.add(Review(tenant_id="tenant-o-1", business_id="biz-o-1", outlet_id="out-o-1",
                                      source="mock", source_review_name=f"o:{i}", star_rating=5,
                                      comment="Enak sekali!", has_text=True))
            db.session.commit()

    def _client(self, email, pw):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": email, "password": pw})
        return c


class TestOwnerDashboard(GateOBase):
    def test_layout_render(self):
        c = self._client("admin@buburfay.id", "pw1")
        r = c.get("/dashboard/")
        self.assertEqual(r.status_code, 200)
        html = r.data.decode()
        for token in ("Ringkasan Hari Ini", "Prioritas Perbaikan", "Review (30 hari)",
                      "Positif", "Negatif", "Bubur Fay Bekasi"):
            self.assertIn(token, html)

    def test_mobile_render(self):
        c = self._client("admin@buburfay.id", "pw1")
        r = c.get("/dashboard/")
        html = r.data.decode()
        self.assertIn("width=device-width", html)  # responsive viewport

    def test_menu_role_admin(self):
        c = self._client("admin@buburfay.id", "pw1")
        html = c.get("/dashboard/").data.decode()
        self.assertIn("Developer Tools", html)
        self.assertIn("AI Advisor", html)

    def test_menu_role_viewer(self):
        c = self._client("viewer@buburfay.id", "pw2")
        html = c.get("/dashboard/").data.decode()
        self.assertNotIn("Developer Tools", html)
        self.assertIn("AI Advisor", html)

    def test_advisor_card(self):
        c = self._client("admin@buburfay.id", "pw1")
        html = c.get("/dashboard/").data.decode()
        # Advisor section renders (with zero issues on positive data → friendly empty)
        self.assertIn("Prioritas Perbaikan", html)

    def test_summary_card(self):
        c = self._client("admin@buburfay.id", "pw1")
        html = c.get("/dashboard/").data.decode()
        self.assertIn("Ringkasan Hari Ini", html)
        self.assertIn("apresiasi", html)

    def test_dashboard_performance(self):
        c = self._client("admin@buburfay.id", "pw1")
        t0 = time.monotonic()
        r = c.get("/dashboard/")
        dt = time.monotonic() - t0
        self.assertEqual(r.status_code, 200)
        self.assertLess(dt, 3.0)  # generous threshold for CI

    def test_outlets_page(self):
        c = self._client("admin@buburfay.id", "pw1")
        r = c.get("/dashboard/outlets")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Bubur Fay Bekasi", r.data.decode())

    def test_reviews_page(self):
        c = self._client("admin@buburfay.id", "pw1")
        r = c.get("/dashboard/reviews")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Positif", r.data.decode())

    def test_settings_page(self):
        c = self._client("admin@buburfay.id", "pw1")
        r = c.get("/dashboard/settings")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Integrasi", r.data.decode())
        self.assertIn("Logout", r.data.decode())

    def test_advisor_page_unchanged_contract(self):
        c = self._client("admin@buburfay.id", "pw1")
        r = c.get("/dashboard/advisor")
        self.assertEqual(r.status_code, 200)
        html = r.data.decode()
        self.assertIn("Prioritas Perbaikan Hari Ini", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
