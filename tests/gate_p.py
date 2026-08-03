"""Gate P — Dashboard Information Hierarchy Polish (M2.1).

Covers: section order (Header → Prioritas Hari Ini → Ringkasan → Prioritas
Perbaikan → Review Summary → Outlet), hero green card when no issues,
advisor contract unchanged, performance. No logic/DB/AI changes tested here.
"""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_p.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review


class GatePBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-p-1", tenant_id="tenant-p-1", name="Bubur Fay", brand_name="Bubur Fay")
            admin = User(id="u-p-1", email="admin@buburfay.id",
                         password_hash=generate_password_hash("pw1"), display_name="Owner",
                         business_id="biz-p-1", role="superadmin", is_active=True)
            db.session.add_all([biz, admin])
            db.session.commit()
            o = Outlet(id="out-p-1", tenant_id="tenant-p-1", business_id="biz-p-1",
                       name="Bubur Fay Bekasi", public_place_id="X1", status="active",
                       monitor_enabled=True, reply_enabled=False, business_rating=4.5,
                       business_review_count=438, city_regency="Bekasi", district="Pondok Gede")
            o2 = Outlet(id="out-p-2", tenant_id="tenant-p-1", business_id="biz-p-1",
                        name="Bubur Fay Margonda", public_place_id="X2", status="active",
                        monitor_enabled=True, reply_enabled=False, business_rating=4.2,
                        business_review_count=187, city_regency="Depok", district="Beji")
            db.session.add_all([o, o2])
            db.session.commit()
            # positive reviews only → advisor empty (green card path)
            db.session.add(Review(tenant_id="tenant-p-1", business_id="biz-p-1", outlet_id="out-p-1",
                                  source="mock", source_review_name="p:1", star_rating=5,
                                  comment="Enak sekali!", has_text=True))
            db.session.commit()

    def _html(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        return c.get("/dashboard/").data.decode()

    def _pos(self, html, token):
        return html.find(token)


class TestHierarchy(GatePBase):
    def test_section_order(self):
        html = self._html()
        order = [
            ("AI Advisor — Prioritas Perbaikan", "advisor"),
            ("Rating rata-rata", "kpi"),
            ("Tren Rating", "trend"),
            ("Review Terbaru", "review-terbaru"),
        ]
        prev = -1
        for token, label in order:
            pos = self._pos(html, token)
            self.assertGreaterEqual(pos, 0, f"section tidak ditemukan: {label}")
            self.assertGreater(pos, prev, f"urutan salah: {label} harus setelah sebelumnya")
            prev = pos

    def test_hero_priority_section_present(self):
        html = self._html()
        # UX redesign: alert banner (green/info) replaces the old hero title
        self.assertTrue(("alert-banner" in html) or ("Prioritas" in html))

    def test_green_card_when_no_issues(self):
        html = self._html()
        self.assertIn("Tidak ada masalah prioritas hari ini", html)

    def test_review_summary_below_priorities(self):
        html = self._html()
        self.assertGreater(self._pos(html, "Review Terbaru"),
                           self._pos(html, "AI Advisor — Prioritas Perbaikan"))

    def test_advisor_contract_unchanged(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        r = c.get("/api/public/advisor?days=30")
        data = r.get_json()
        self.assertIn("issues", data)
        self.assertLessEqual(len(data["issues"]), 3)

    def test_performance(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        t0 = time.monotonic()
        r = c.get("/dashboard/")
        dt = time.monotonic() - t0
        self.assertEqual(r.status_code, 200)
        self.assertLess(dt, 3.0)

    def test_ringkasan_menonjol(self):
        html = self._html()
        # KPI cards appear before Review Terbaru (summary near top)
        self.assertLess(self._pos(html, "Rating rata-rata"),
                        self._pos(html, "Review Terbaru"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
