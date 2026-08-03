"""Gate R — Dashboard AI Advisor UX Redesign (presentation layer only).

Covers: 8 widgets render, AI Advisor contract + Evidence/Confidence/Priority/
Status, no fabricated data (empty → placeholder), mobile responsive, performance.
Backend/API unchanged (no new endpoints tested).
"""
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_r.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review
from app.services.analysis_service import analyze_review


_SEEDED = False


class GateRBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global _SEEDED
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        if _SEEDED:
            return
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-r-1", tenant_id="tenant-r-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-r-1", email="admin@buburfay.id",
                     password_hash=generate_password_hash("pw1"), display_name="Owner",
                     business_id="biz-r-1", role="superadmin", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()
            o1 = Outlet(id="out-r-1", tenant_id="tenant-r-1", business_id="biz-r-1",
                        name="Bubur Fay Bekasi", public_place_id="X1", status="active",
                        monitor_enabled=True, reply_enabled=False, business_rating=4.5,
                        business_review_count=438, city_regency="Bekasi", district="Pondok Gede")
            db.session.add(o1)
            db.session.commit()
            # positive + negative reviews (real, analyzed) → advisor produces issues
            seed = [
                ("Enak sekali, kuahnya gurih!", 5),
                ("Pelayanan tidak ramah, kasir cuek.", 2),
                ("Pelayanannya lambat sekali.", 1),
                ("Rasanya berubah, tidak enak.", 2),
            ]
            for i, (txt, star) in enumerate(seed):
                r = Review(tenant_id="tenant-r-1", business_id="biz-r-1", outlet_id="out-r-1",
                           source="mock", source_review_name=f"r:{i}", star_rating=star,
                           comment=txt, has_text=bool(txt),
                           create_time=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc))
                db.session.add(r)
                db.session.flush()
                analyze_review("tenant-r-1", "biz-r-1", r.id)
            db.session.commit()
            _SEEDED = True

    def _html(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        return c.get("/dashboard/").data.decode()


class TestWidgets(GateRBase):
    def test_kpi_cards(self):
        html = self._html()
        for t in ("Rating rata-rata", "Review", "Positif", "Negatif"):
            self.assertIn(t, html)

    def test_trend_rating(self):
        self.assertIn("Tren Rating", self._html())

    def test_distribusi_rating(self):
        html = self._html()
        self.assertIn("Distribusi Rating", html)
        self.assertIn("5★", html)

    def test_review_terbaru(self):
        html = self._html()
        self.assertIn("Review Terbaru", html)
        self.assertIn("Pelayanan tidak ramah", html)  # real data visible

    def test_top_aspek(self):
        self.assertIn("Aspek Teratas", self._html())

    def test_sentiment_over_time(self):
        self.assertIn("Sentimen dari Waktu ke Waktu", self._html())

    def test_performa_outlet(self):
        html = self._html()
        self.assertIn("Performa Outlet", html)
        self.assertIn("Bubur Fay Bekasi", html)

    def test_alert_notification(self):
        html = self._html().lower()
        # alert banner present (info/urgent); no issues → green, else info/urgent
        self.assertTrue(("prioritas perbaikan" in html) or ("masalah" in html))


class TestAdvisorEnriched(GateRBase):
    def test_advisor_contract_present(self):
        html = self._html()
        for t in ("AI Advisor — Prioritas Perbaikan", "PIC:", "Saran tindakan"):
            self.assertIn(t, html)

    def test_advisor_evidence(self):
        html = self._html()
        self.assertIn("Bukti:", html)
        self.assertIn("review", html.lower())

    def test_advisor_confidence(self):
        self.assertIn("Confidence:", self._html())

    def test_advisor_priority(self):
        html = self._html()
        self.assertIn("Priority:", html)
        # any of the three levels present as badge
        self.assertTrue(any(b in html for b in ("Ringan", "Sedang", "Mendesak")))

    def test_advisor_status(self):
        self.assertIn("Status:", self._html())

    def test_advisor_quotes_from_real_data(self):
        html = self._html()
        self.assertIn("Pelayanan tidak ramah", html)  # quote from seeded review


class TestSafety(GateRBase):
    def test_mobile_responsive(self):
        html = self._html()
        self.assertIn("width=device-width", html)
        self.assertIn("grid-template-columns", html)

    def test_no_fabricated_data(self):
        # Real data is displayed (not fabricated placeholders)
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        html = c.get("/dashboard/outlets").data.decode()
        self.assertIn("Bubur Fay Bekasi", html)  # real outlet name from seed
        dhtml = c.get("/dashboard/").data.decode()
        self.assertIn("2.5", dhtml)  # real avg rating of seeded reviews

    def test_performance(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        t0 = time.monotonic()
        r = c.get("/dashboard/")
        dt = time.monotonic() - t0
        self.assertEqual(r.status_code, 200)
        self.assertLess(dt, 3.0)

    def test_backend_api_unchanged(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        r = c.get("/api/public/analytics/summary?days=30")
        self.assertEqual(r.status_code, 200)
        r2 = c.get("/api/public/advisor?days=30")
        self.assertEqual(r2.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
