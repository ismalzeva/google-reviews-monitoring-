"""Gate S — Dashboard Period Selection (all-time default + filters).

Covers: all-time default (total since first review), 7/30/90 days, month,
custom range, period label, selector UI present. No backend/API changes.
"""
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_s.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review


class GateSBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-s-1", tenant_id="tenant-s-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-s-1", email="admin@buburfay.id",
                     password_hash=generate_password_hash("pw1"), display_name="Owner",
                     business_id="biz-s-1", role="superadmin", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()
            o = Outlet(id="out-s-1", tenant_id="tenant-s-1", business_id="biz-s-1",
                       name="Bubur Fay Bekasi", public_place_id="X1", status="active",
                       monitor_enabled=True, reply_enabled=False, business_rating=4.5)
            db.session.add(o)
            db.session.commit()
            # 3 reviews: June, July 10, July 25
            for i, (dt, star) in enumerate([
                (datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc), 5),
                (datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc), 4),
                (datetime(2026, 7, 25, 8, 0, tzinfo=timezone.utc), 3),
            ]):
                db.session.add(Review(tenant_id="tenant-s-1", business_id="biz-s-1", outlet_id="out-s-1",
                                      source="mock", source_review_name=f"s:{i}", star_rating=star,
                                      comment=f"review {i}", has_text=True, create_time=dt))
            db.session.commit()

    def _kpi(self, url):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        html = c.get(url).data.decode()
        m = re.search(r'<div class="label">Review</div><div class="value">([^<]+)</div>', html)
        return html, (m.group(1) if m else "?")


class TestPeriodSelection(GateSBase):
    def test_default_all_time(self):
        html, kpi = self._kpi("/dashboard/")
        self.assertEqual(kpi, "3")  # total since first review
        self.assertIn("Semua Waktu", html)

    def test_days_30(self):
        _, kpi = self._kpi("/dashboard/?days=30")
        self.assertEqual(kpi, "2")  # July 10 + July 25

    def test_days_90(self):
        _, kpi = self._kpi("/dashboard/?days=90")
        self.assertEqual(kpi, "3")

    def test_month_filter(self):
        html, kpi = self._kpi("/dashboard/?month=2026-06")
        self.assertEqual(kpi, "1")  # only June review
        self.assertIn("Bulan 2026-06", html)

    def test_custom_range(self):
        html, kpi = self._kpi("/dashboard/?start=2026-07-01&end=2026-07-20")
        self.assertEqual(kpi, "1")  # only July 10
        self.assertIn("2026-07-01 s/d 2026-07-20", html)

    def test_selector_ui_present(self):
        html, _ = self._kpi("/dashboard/")
        self.assertIn("Periode:", html)
        self.assertIn("Semua Waktu", html)
        self.assertIn("applyPeriod", html)

    def test_period_label_30d(self):
        html, _ = self._kpi("/dashboard/?days=30")
        self.assertIn("30 hari terakhir", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
