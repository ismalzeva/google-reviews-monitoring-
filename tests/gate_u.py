"""Gate U — GRM Design System (identitas visual GRM, bukan clone GMB).

Covers: sidebar+header layout, design.css, visual hierarchy (Prioritas Hari
Ini → AI Advisor fokus → KPI), identity (tidak ada trade dress GMB),
responsive, accessibility basics.
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_u.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review


class GateUBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-u-1", tenant_id="tenant-u-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-u-1", email="admin@buburfay.id",
                     password_hash=generate_password_hash("pw1"), display_name="Owner",
                     business_id="biz-u-1", role="superadmin", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()
            o1 = Outlet(id="out-u-1", tenant_id="tenant-u-1", business_id="biz-u-1",
                        name="Bubur Fay Bekasi", public_place_id="X1", status="active",
                        monitor_enabled=True, reply_enabled=False, business_rating=4.5,
                        city_regency="Bekasi")
            db.session.add(o1)
            db.session.commit()
            db.session.add(Review(tenant_id="tenant-u-1", business_id="biz-u-1", outlet_id="out-u-1",
                                  source="mock", source_review_name="u:1", star_rating=5,
                                  comment="Enak sekali!", has_text=True,
                                  create_time=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc)))
            db.session.commit()

    def _html(self, path="/dashboard/"):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        return c.get(path).data.decode()


class TestDesignSystem(GateUBase):
    def test_layout_sidebar_header(self):
        html = self._html()
        self.assertIn("grm-sidebar", html)
        self.assertIn("grm-header", html)
        self.assertIn("grm-shell", html)

    def test_design_css_loaded(self):
        html = self._html()
        self.assertIn("design.css", html)
        r = self.app.test_client().get("/static/css/design.css")
        self.assertEqual(r.status_code, 200)
        self.assertIn("--grm-primary", r.data.decode())

    def test_visual_hierarchy(self):
        html = self._html()
        # Prioritas Hari Ini → AI Advisor (fokus) → KPI
        self.assertLess(html.find("Prioritas Hari Ini"), html.find("AI Advisor — Prioritas Perbaikan"))
        self.assertLess(html.find("AI Advisor — Prioritas Perbaikan"), html.find("Rating rata-rata"))

    def test_ai_advisor_focus(self):
        html = self._html()
        # Advisor before KPI = focus
        self.assertLess(html.find("AI Advisor — Prioritas Perbaikan"), html.find("Distribusi Rating"))

    def test_identity_not_gmb_clone(self):
        html = self._html()
        # No Google Business Profile trade dress / menu names
        self.assertNotIn("Google Business Profile", html)
        self.assertNotIn("Google My Business", html)
        self.assertNotIn("maps.google.com", html)

    def test_brand_identity(self):
        html = self._html()
        self.assertIn("GRM", html)  # own identity
        self.assertIn("--grm-primary", html)  # orange token present

    def test_responsive(self):
        html = self._html()
        self.assertIn("width=device-width", html)
        self.assertIn("@media (max-width: 860px)", self.app.test_client().get("/static/css/design.css").data.decode())

    def test_pages_render(self):
        for p in ("/dashboard/", "/dashboard/outlets", "/dashboard/advisor", "/dashboard/reviews", "/dashboard/settings"):
            c = self.app.test_client()
            c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
            self.assertEqual(c.get(p).status_code, 200, p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
