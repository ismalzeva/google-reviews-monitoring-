"""Gate N — Self-Service Onboarding (RUN_M1).

Covers: discovery success/empty/timeout, choose outlet, verify, sync
success/fail, progress update, incremental, full sync, dashboard redirect.
Uses the mock provider (deterministic) — no live HTTP.
"""
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='gate_n.db')}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_ENV"] = "testing"
os.environ["GRM_PILOT_MODE"] = "false"
os.environ["PUBLIC_REVIEW_PROVIDER"] = "mock"

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models.entities import User, Business, Outlet, Review

T1_EMAIL = "owner@buburfay.id"
T1_PW = "pass1234"


class GateNBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            biz = Business(id="biz-n-1", tenant_id="tenant-n-1", name="Bubur Fay", brand_name="Bubur Fay")
            u = User(id="u-n-1", email=T1_EMAIL, password_hash=generate_password_hash(T1_PW),
                     display_name="Owner", business_id="biz-n-1", role="owner", is_active=True)
            db.session.add_all([biz, u])
            db.session.commit()

    def setUp(self):
        self.client = self.app.test_client()
        self.client.post("/auth/login", data={"email": T1_EMAIL, "password": T1_PW})

    def _discover(self, query="Bubur Fay", url=""):
        return self.client.post("/onboarding/discover", json={"query": query, "url": url})

    def _verify(self, cand):
        return self.client.post("/onboarding/verify", json=cand)

    def _sync(self, outlet_id, mode="incremental"):
        return self.client.post("/onboarding/sync", json={"outlet_id": outlet_id, "mode": mode})

    def _wait_done(self, outlet_id, timeout=25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            r = self.client.get(f"/onboarding/status?outlet_id={outlet_id}")
            prog = r.get_json().get("progress")
            if prog and prog.get("done"):
                return prog
            time.sleep(0.5)
        return None


class TestOnboarding(GateNBase):
    def test_page_renders(self):
        r = self.client.get("/onboarding/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Tambah Outlet", r.data.decode())

    def test_discovery_success(self):
        r = self._discover()
        self.assertEqual(r.status_code, 200)
        cands = r.get_json()["candidates"]
        self.assertGreaterEqual(len(cands), 1)
        self.assertTrue(all(c["display_name"] for c in cands))

    def test_discovery_empty(self):
        r = self._discover(query="zzzztdakada")
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", r.get_json())

    def test_discovery_missing_input(self):
        r = self._discover(query="", url="")
        self.assertEqual(r.status_code, 400)

    def test_discovery_timeout_friendly(self):
        from app.routes import onboarding as ob
        with mock.patch.object(ob, "_discover_locations", side_effect=TimeoutError("boom")):
            r = self._discover(query="Bubur Fay")
        self.assertEqual(r.status_code, 502)
        self.assertNotIn("Traceback", r.get_json()["error"])

    def test_choose_and_verify_outlet(self):
        r = self._discover()
        cand = r.get_json()["candidates"][0]
        r2 = self._verify(cand)
        self.assertEqual(r2.status_code, 200)
        data = r2.get_json()
        self.assertIn("outlets", data)
        outlet = data["outlets"][0]
        self.assertEqual(outlet["place_id"], cand["place_id"])
        with self.app.app_context():
            o = Outlet.query.filter_by(tenant_id="tenant-n-1", public_place_id=cand["place_id"]).first()
            self.assertIsNotNone(o)
            self.assertTrue(o.monitor_enabled)
            self.assertFalse(o.reply_enabled)
        self.assertFalse(outlet["already_synced"])

    def test_verify_multi_select(self):
        r = self._discover()
        cands = r.get_json()["candidates"]
        r2 = self._verify({"candidates": cands[:2]})
        self.assertEqual(r2.status_code, 200)
        self.assertGreaterEqual(len(r2.get_json()["outlets"]), 1)

    def test_verify_already_synced_flag(self):
        r = self._discover()
        cand = r.get_json()["candidates"][0]
        self._verify(cand)
        # second verify → still not synced (no reviews yet); simulate by syncing first
        self._sync_flag_test(cand)

    def _sync_flag_test(self, cand):
        with self.app.app_context():
            o = Outlet.query.filter_by(tenant_id="tenant-n-1", public_place_id=cand["place_id"]).first()
            from app.models.entities import Review
            db.session.add(Review(tenant_id="tenant-n-1", business_id="biz-n-1", outlet_id=o.id,
                                  source="mock", source_review_name="n:1", star_rating=5,
                                  comment="test", has_text=True))
            db.session.commit()
        r = self._verify(cand)
        self.assertTrue(r.get_json()["outlets"][0]["already_synced"])

    def test_sync_success(self):
        r = self._discover()
        cand = r.get_json()["candidates"][0]
        self._verify(cand)
        with self.app.app_context():
            o = Outlet.query.filter_by(tenant_id="tenant-n-1", public_place_id=cand["place_id"]).first()
            oid = o.id
        r = self._sync(oid)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["started"])
        prog = self._wait_done(oid)
        self.assertIsNotNone(prog)
        self.assertTrue(prog["done"])
        self.assertIsNone(prog["error"])
        self.assertGreaterEqual(prog["stats"]["received"], 1)
        with self.app.app_context():
            self.assertGreaterEqual(Review.query.filter_by(outlet_id=oid).count(), 1)

    def test_sync_incremental(self):
        r = self._discover()
        cand = r.get_json()["candidates"][0]
        self._verify(cand)
        with self.app.app_context():
            oid = Outlet.query.filter_by(tenant_id="tenant-n-1", public_place_id=cand["place_id"]).first().id
        self._sync(oid, mode="incremental")
        prog1 = self._wait_done(oid)
        # second incremental sync → no new inserts (idempotent)
        self._sync(oid, mode="incremental")
        prog2 = self._wait_done(oid)
        self.assertIsNotNone(prog2)
        self.assertEqual(prog2["stats"]["inserted"], 0)

    def test_sync_full(self):
        r = self._discover()
        cand = r.get_json()["candidates"][0]
        self._verify(cand)
        with self.app.app_context():
            oid = Outlet.query.filter_by(tenant_id="tenant-n-1", public_place_id=cand["place_id"]).first().id
        self._sync(oid, mode="incremental")
        self._wait_done(oid)
        self._sync(oid, mode="full")
        prog = self._wait_done(oid)
        self.assertIsNotNone(prog)
        self.assertIsNone(prog["error"])
        with self.app.app_context():
            self.assertGreaterEqual(Review.query.filter_by(outlet_id=oid).count(), 1)

    def test_sync_fail_friendly(self):
        from app.services import sync_service as ss
        r = self._discover()
        cand = r.get_json()["candidates"][0]
        self._verify(cand)
        with self.app.app_context():
            oid = Outlet.query.filter_by(tenant_id="tenant-n-1", public_place_id=cand["place_id"]).first().id
        with mock.patch.object(ss, "sync_public_reviews", side_effect=RuntimeError("boom")):
            self._sync(oid)
            prog = self._wait_done(oid)
        self.assertIsNotNone(prog)
        self.assertTrue(prog["done"])
        self.assertIn("Coba lagi", prog["error"])

    def test_progress_update(self):
        r = self._discover()
        cand = r.get_json()["candidates"][0]
        self._verify(cand)
        with self.app.app_context():
            oid = Outlet.query.filter_by(tenant_id="tenant-n-1", public_place_id=cand["place_id"]).first().id
        self._sync(oid)
        time.sleep(1.0)
        r = self.client.get(f"/onboarding/status?outlet_id={oid}")
        prog = r.get_json().get("progress")
        self.assertIsNotNone(prog)
        self.assertIn("stage", prog)

    def test_dashboard_link_in_done(self):
        r = self._discover()
        cand = r.get_json()["candidates"][0]
        self._verify(cand)
        with self.app.app_context():
            oid = Outlet.query.filter_by(tenant_id="tenant-n-1", public_place_id=cand["place_id"]).first().id
        self._sync(oid)
        self._wait_done(oid)
        page = self.client.get("/onboarding/").data.decode()
        self.assertIn("/dashboard/", page)  # Lihat Dashboard link present in JS


if __name__ == "__main__":
    unittest.main(verbosity=2)
