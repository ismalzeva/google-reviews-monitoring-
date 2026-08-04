"""Gate Z — Stage 4 M1: Public Experience Layer (landing + info pages)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_z.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from app import create_app, db
from app.models.entities import User, Business


class GateZBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-z-1", tenant_id="tenant-z-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-z-1", email="admin@buburfay.id",
                     password_hash=generate_password_hash("pw1"), display_name="Owner",
                     business_id="biz-z-1", role="superadmin", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()

    def _get(self, path):
        return self.app.test_client().get(path)


class TestPublicExperience(GateZBase):
    def test_all_pages_render(self):
        for p in ("/", "/features", "/how-it-works", "/demo", "/pricing", "/faq", "/guide", "/help", "/about"):
            self.assertEqual(self._get(p).status_code, 200, p)

    def test_nav_present(self):
        html = self._get("/").data.decode()
        for t in ("Fitur", "Cara Kerja", "Demo", "Harga", "FAQ", "Login", "Coba Gratis"):
            self.assertIn(t, html)

    def test_hero_positioning(self):
        html = self._get("/").data.decode()
        self.assertIn("Tahu masalah terbesar pelanggan", html)
        self.assertIn("AI Customer Experience Manager", html)

    def test_landing_search(self):
        html = self._get("/").data.decode()
        self.assertIn("pub-search", html)
        self.assertIn("Lihat Analisis", html)

    def test_demo_query(self):
        html = self._get("/demo?q=Bubur%20Fay").data.decode()
        self.assertIn("Bubur Fay", html)
        self.assertIn("Prioritas Hari Ini", html)
        self.assertIn("PIC", html)

    def test_pricing_tiers(self):
        html = self._get("/pricing").data.decode()
        for t in ("Pemula", "Pro", "Premium", "Rp99rb", "Rp299rb", "Rp799rb", "tanpa kartu kredit"):
            self.assertIn(t, html)

    def test_faq_answers_objections(self):
        html = self._get("/faq").data.decode()
        for t in ("butuh login Google", "beda dengan Google Business", "AI bisa salah", "satu outlet", "Coba Gratis"):
            self.assertIn(t, html)

    def test_features_benefits(self):
        html = self._get("/features").data.decode()
        self.assertIn("Hasil, bukan sekadar dashboard", html)
        self.assertIn("Prioritas Hari Ini", html)

    def test_how_it_works_3_steps(self):
        html = self._get("/how-it-works").data.decode()
        for t in ("Tambah outlet", "Sinkronkan review", "Bertindak", "3 menit"):
            self.assertIn(t, html)

    def test_core_platform_intact(self):
        # Auth & dashboard routes still work (Core Platform untouched)
        c = self.app.test_client()
        c.post("/auth/login", data={"email": "admin@buburfay.id", "password": "pw1"})
        for p in ("/dashboard/", "/onboarding/", "/dashboard/performa"):
            self.assertEqual(c.get(p).status_code, 200, p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
