"""Gate Q — Pilot Customer Readiness (M3).

Covers: landing page, guide, help, about, copywriting simplicity, empty states,
loading states, error states (no stack trace), redirect after login.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_q.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business

TECH_TERMS = ["API", "OAuth", "Postman", "endpoint", "JSON", "scraping", "environment", ".env"]


_SEEDED = False


class GateQBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global _SEEDED
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        if _SEEDED:
            return
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-q-1", tenant_id="tenant-q-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-q-1", email="admin@buburfay.id",
                     password_hash=generate_password_hash("pw1"), display_name="Owner",
                     business_id="biz-q-1", role="superadmin", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()
            _SEEDED = True


class TestPublicPages(GateQBase):
    def test_landing_page(self):
        r = self.app.test_client().get("/")
        self.assertEqual(r.status_code, 200)
        html = r.data.decode()
        for token in ("Tahu masalah terbesar pelanggan", "AI Customer Experience Manager",
                      "Cara kerjanya", "Lihat Analisis"):
            self.assertIn(token, html)

    def test_landing_redirect_when_authenticated(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        r = c.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/dashboard/", r.headers.get("Location", ""))

    def test_guide_page(self):
        r = self.app.test_client().get("/guide")
        self.assertEqual(r.status_code, 200)
        html = r.data.decode()
        for token in ("Tambah Outlet", "Sinkronisasi", "Buka AI Advisor", "Lakukan Tindakan"):
            self.assertIn(token, html)

    def test_help_page(self):
        r = self.app.test_client().get("/help")
        self.assertEqual(r.status_code, 200)
        html = r.data.decode()
        for token in ("Sinkronisasi berapa lama", "Incremental Sync", "Prioritas Hari Ini", "PIC"):
            self.assertIn(token, html)

    def test_about_page(self):
        r = self.app.test_client().get("/about")
        self.assertEqual(r.status_code, 200)
        html = r.data.decode()
        for token in ("Versi aplikasi", "Build", "Deployment date", "0.9.0"):
            self.assertIn(token, html)

    def test_copywriting_no_tech_terms(self):
        for path in ("/", "/guide", "/help", "/about"):
            html = self.app.test_client().get(path).data.decode()
            for term in TECH_TERMS:
                self.assertNotIn(term, html, f"istilah teknis '{term}' muncul di {path}")


class TestStates(GateQBase):
    def test_empty_outlets(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        html = c.get("/dashboard/outlets").data.decode()
        self.assertIn("Belum ada outlet aktif", html)

    def test_empty_reviews(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        html = c.get("/dashboard/reviews").data.decode()
        self.assertIn("Memuat", html)  # loading state present

    def test_loading_state_present(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        html = c.get("/dashboard/reviews").data.decode()
        self.assertIn("Memuat…", html)

    def test_onboarding_error_no_stacktrace(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        r = c.post("/onboarding/discover", json={"query": ""})
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("Traceback", r.get_json().get("error", ""))
        r2 = c.post("/onboarding/discover", json={"query": "zzzztdakada"})
        self.assertIn("error", r2.get_json())

    def test_dashboard_empty_issue_state(self):
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        html = c.get("/dashboard/").data.decode()
        self.assertIn("Tidak ada masalah", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
