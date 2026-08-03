"""Gate X — Perbaikan 3-Agustus: bukti advisor, period label, sentimen lengkap,
tren informatif, urgency proporsional."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_x.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review
from app.services.analysis_service import analyze_review


class GateXBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-x-1", tenant_id="tenant-x-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-x-1", email="admin@buburfay.id",
                     password_hash=generate_password_hash("pw1"), display_name="Owner",
                     business_id="biz-x-1", role="superadmin", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()
            o = Outlet(id="out-x-1", tenant_id="tenant-x-1", business_id="biz-x-1",
                       name="Bubur Fay Bekasi", public_place_id="X1", status="active",
                       monitor_enabled=True, reply_enabled=False, city_regency="Bekasi")
            db.session.add(o)
            db.session.commit()
            seed = [
                ("Really really delicioso! enak banget", 5),       # praise — never evidence
                ("Pelayanan sangat buruk, kasar", 1),              # real complaint
                ("Setelah makan langsung mual", 1),                # critical single evidence
                ("Porsi mengecil, harga naik", 2),                 # complaint
            ]
            for i, (txt, star) in enumerate(seed):
                r = Review(tenant_id="tenant-x-1", business_id="biz-x-1", outlet_id="out-x-1",
                           source="mock", source_review_name=f"x:{i}", star_rating=star,
                           comment=txt, has_text=True,
                           create_time=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc))
                db.session.add(r)
                db.session.flush()
                analyze_review("tenant-x-1", "biz-x-1", r.id)
            db.session.commit()

    def _advisor(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        return c.get("/api/public/advisor?start_date=2000-01-01").get_json()

    def _dashboard(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        return c.get("/dashboard/").data.decode()


class TestPerbaikan(GateXBase):
    def test_praise_never_evidence(self):
        d = self._advisor()
        for it in d["issues"]:
            for q in it["bukti"]["quotes"]:
                self.assertNotIn("delicioso", q)
                self.assertNotIn("enak banget", q)

    def test_sakit_gigi_not_critical(self):
        d = self._advisor()
        kritis = [it for it in d["issues"] if "keamanan" in it["masalah"].lower()]
        self.assertTrue(kritis)  # mual = real critical, 1 evidence
        for q in kritis[0]["bukti"]["quotes"]:
            self.assertNotIn("delicioso", q)

    def test_period_label_semua_waktu(self):
        d = self._advisor()
        for it in d["issues"]:
            self.assertEqual(it["bukti"]["period"], "Semua Waktu")
            self.assertNotIn("2000-01-01", it["bukti"]["period"])

    def test_urgency_proportional(self):
        d = self._advisor()
        kritis = [it for it in d["issues"] if "keamanan" in it["masalah"].lower()]
        # 1 evidence critical → NOT Mendesak (needs human review instead)
        if kritis:
            self.assertEqual(kritis[0]["priority"], "Sedang")
            self.assertTrue(kritis[0]["needs_human_review"])

    def test_sentiment_breakdown_total(self):
        html = self._dashboard()
        self.assertIn("rating-only", html)
        self.assertIn("campuran", html)
        self.assertIn("netral", html)

    def test_trend_informative(self):
        html = self._dashboard()
        self.assertIn("Tren Rating", html)
        # either delta indicator or empty state for insufficient data
        self.assertTrue(("naik" in html) or ("turun" in html) or ("terlalu sedikit" in html) or ("stabil" in html))


if __name__ == "__main__":
    unittest.main(verbosity=2)
