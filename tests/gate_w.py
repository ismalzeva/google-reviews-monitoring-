"""Gate W — Top Masalah Spesifik (granular sub-issue breakdown)."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_w.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review
from app.services.analysis_service import analyze_review


class GateWBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-w-1", tenant_id="tenant-w-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-w-1", email="admin@buburfay.id",
                     password_hash=generate_password_hash("pw1"), display_name="Owner",
                     business_id="biz-w-1", role="superadmin", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()
            o = Outlet(id="out-w-1", tenant_id="tenant-w-1", business_id="biz-w-1",
                       name="Bubur Fay Bekasi", public_place_id="X1", status="active",
                       monitor_enabled=True, reply_enabled=False, city_regency="Bekasi")
            db.session.add(o)
            db.session.commit()
            seed = [
                "Pelayanannya tidak ramah, kasir cuek.",
                "Waiternya judes dan kasar.",
                "Dilayani lama, kayak diabaikan.",
                "Porsi mengecil sekali, makin sedikit.",
                "Buburnya basi dan tidak enak.",
            ]
            for i, txt in enumerate(seed):
                r = Review(tenant_id="tenant-w-1", business_id="biz-w-1", outlet_id="out-w-1",
                           source="mock", source_review_name=f"w:{i}", star_rating=1,
                           comment=txt, has_text=True,
                           create_time=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc))
                db.session.add(r)
                db.session.flush()
                analyze_review("tenant-w-1", "biz-w-1", r.id)
            db.session.commit()

    def _advisor(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        return c.get("/api/public/advisor?start_date=2000-01-01").get_json()


class TestSpecificIssues(GateWBase):
    def test_sub_issues_present(self):
        d = self._advisor()
        self.assertGreaterEqual(len(d["issues"]), 1)
        for it in d["issues"]:
            self.assertIn("sub_issues", it)

    def test_sub_issue_counting(self):
        d = self._advisor()
        pelayanan = next((it for it in d["issues"] if "pelayanan" in it["masalah"].lower()), None)
        self.assertIsNotNone(pelayanan)
        subs = {s["masalah"]: s["count"] for s in pelayanan["sub_issues"]}
        self.assertGreaterEqual(subs.get("tidak ramah / cuek", 0), 2)  # 2 review
        self.assertGreaterEqual(subs.get("tidak responsif / diabaikan", 0), 1)

    def test_sub_issue_ordered(self):
        d = self._advisor()
        for it in d["issues"]:
            counts = [s["count"] for s in it["sub_issues"]]
            self.assertEqual(counts, sorted(counts, reverse=True))

    def test_max_five_sub_issues(self):
        d = self._advisor()
        for it in d["issues"]:
            self.assertLessEqual(len(it["sub_issues"]), 5)

    def test_ui_renders_specific_issues(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        html = c.get("/dashboard/").data.decode()
        self.assertIn("Masalah spesifik", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
