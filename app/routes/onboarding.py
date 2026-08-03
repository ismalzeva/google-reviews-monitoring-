"""Self-service onboarding routes (RUN_M1).

Flow: Tambah Outlet (nama/URL) → Cari (discovery) → Pilih → Konfirmasi →
Sync (progress) → Selesai → Lihat Dashboard. No SSH/env/API needed by owner.

Constraints (RUN_M1):
- onboarding only; no new analytics/advisor/provider/dashboard features
- discovery failure → clear friendly error, no infinite spinner, no stack trace
- if outlet already synced → offer Incremental or Full Sync
"""
import logging
import threading
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user

from app import db
from app.models.entities import Outlet, Review, Business
from app.services.discovery import search_places, normalize_candidate, save_candidates

logger = logging.getLogger(__name__)

bp = Blueprint("onboarding", __name__, url_prefix="/onboarding")

# In-memory sync progress store (single-pilot scale; not durable)
_SYNC_PROGRESS = {}


def _now():
    return datetime.now(timezone.utc)


def _friendly_error(exc) -> str:
    """Map exceptions to a clear owner-facing message (no stack trace)."""
    msg = str(exc)
    if "APIFY_API_TOKEN" in msg:
        return "Provider review belum dikonfigurasi. Hubungi admin."
    if "OUTSCRAPER_API_KEY" in msg:
        return "Provider review belum dikonfigurasi. Hubungi admin."
    if "placeholder" in msg.lower():
        return "Lokasi tidak valid. Gunakan hasil pencarian di atas."
    if "timeout" in msg.lower() or "TIMED_OUT" in msg:
        return "Pencarian terlalu lama. Coba lagi sebentar."
    if "not found" in msg.lower() or "tidak ditemukan" in msg.lower():
        return "Lokasi tidak ditemukan. Coba nama atau alamat lain."
    return "Terjadi kesalahan. Coba lagi."


def _get_business() -> Business:
    return current_user.business if current_user.is_authenticated else None


DEFAULT_SEARCH_CITIES = ["Depok", "Bekasi", "Jakarta", "Bogor", "Tangerang", "Bandung"]


def _discover_locations(query: str, city: str = None):
    """Discovery via provider adapter when available, else mock search.

    The crawler actor returns ~1 place per search term, so when no city is
    given we loop several Indonesian cities to surface ALL branches.
    """
    from app.services.public_provider import build_public_review_adapter
    try:
        adapter = build_public_review_adapter()
    except Exception:
        adapter = None
    if adapter is not None and hasattr(adapter, "discover"):
        try:
            cities = None if city else DEFAULT_SEARCH_CITIES
            return adapter.discover(query, city=city, cities=cities), "apify"
        except Exception:
            # fall through to mock search only for dev/test; production error surfaces
            raise
    raw = search_places(query, city=city)
    return [
        {
            "place_id": c.get("place_id"),
            "display_name": c.get("display_name"),
            "formatted_address": c.get("formatted_address"),
            "latitude": c.get("latitude"),
            "longitude": c.get("longitude"),
            "business_status": c.get("business_status", "OPERATIONAL"),
            "google_maps_uri": c.get("google_maps_uri"),
            "rating": c.get("rating"),
            "review_count": c.get("review_count"),
            "province": None,
            "city_regency": c.get("search_region"),
            "district": None,
            "source": "mock",
        }
        for c in raw
    ], "mock"


def _extract_place_id(url: str):
    import re
    m = re.search(r"place_id[:=]([A-Za-z0-9_:\-]+)", url or "")
    if m:
        return m.group(1)
    m = re.search(r"!3m5!1s([0-9a-fA-Fx:]+)", url or "")
    return m.group(1) if m else None


# ─── PAGE ──────────────────────────────────────────────────
@bp.route("/")
@login_required
def page():
    business = _get_business()
    return render_template("onboarding/onboard.html", business=business)


# ─── STEP 1+2: SEARCH / DISCOVER ───────────────────────────
@bp.route("/discover", methods=["POST"])
@login_required
def discover():
    business = _get_business()
    if not business:
        return jsonify({"error": "Belum ada bisnis terhubung."}), 400
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    url = (data.get("url") or "").strip()

    if not query and not url:
        return jsonify({"error": "Masukkan nama bisnis atau tautan Google Maps."}), 400
    if len(query) < 3 and not url:
        return jsonify({"error": "Nama bisnis minimal 3 karakter."}), 400

    place_id = _extract_place_id(url) or (data.get("place_id") or "").strip()
    try:
        if place_id:
            from app.services.public_provider import build_public_review_adapter
            adapter = build_public_review_adapter()
            loc = adapter.fetch_location(place_id)
            candidates = [{
                "place_id": loc.get("place_id"),
                "display_name": loc.get("business_name"),
                "formatted_address": loc.get("full_address"),
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
                "business_status": "OPERATIONAL",
                "google_maps_uri": loc.get("maps_url"),
                "rating": loc.get("business_rating"),
                "review_count": loc.get("business_review_count"),
                "province": loc.get("province"),
                "city_regency": loc.get("city_regency"),
                "district": loc.get("district"),
                "source": getattr(adapter, "source_name", "provider"),
            }]
        else:
            candidates, _src = _discover_locations(query)
    except Exception as exc:
        logger.warning("onboarding discover failed: %s", exc)
        return jsonify({"error": _friendly_error(exc)}), 502

    if not candidates:
        return jsonify({"error": "Tidak ada lokasi ditemukan. Coba nama lain.", "candidates": []}), 404
    return jsonify({"candidates": candidates})


# ─── STEP 3: VERIFY → OUTLET (multi-select) ───────────────
@bp.route("/verify", methods=["POST"])
@login_required
def verify():
    business = _get_business()
    if not business:
        return jsonify({"error": "Belum ada bisnis terhubung."}), 400
    data = request.get_json(silent=True) or {}
    # Accept either a single candidate or a list of candidates
    candidates = data.get("candidates")
    if candidates is None:
        candidates = [data]

    created = []
    for cand in candidates:
        place_id = (cand.get("place_id") or "").strip()
        if not place_id:
            continue
        outlet = Outlet.query.filter_by(
            tenant_id=business.tenant_id, public_place_id=place_id
        ).first()
        if outlet is None:
            outlet = Outlet(
                id=str(uuid.uuid4()),
                tenant_id=business.tenant_id,
                business_id=business.id,
                name=cand.get("display_name") or "Outlet",
                address=cand.get("formatted_address"),
                latitude=_num(cand.get("latitude")),
                longitude=_num(cand.get("longitude")),
                public_place_id=place_id,
                maps_url=cand.get("google_maps_uri"),
                business_rating=_num(cand.get("rating")),
                business_review_count=_int(cand.get("review_count")),
                province=cand.get("province"),
                city_regency=cand.get("city_regency"),
                district=cand.get("district"),
                source=(cand.get("source") or "apify"),
                owner_verification_status="owner_confirmed",
                gbp_match_status="unmatched",
                monitor_enabled=True,
                reply_enabled=False,
                status="active",
            )
            db.session.add(outlet)
        else:
            outlet.monitor_enabled = True
            outlet.status = "active"
            outlet.reply_enabled = False
        created.append({
            "id": outlet.id,
            "name": outlet.name,
            "address": outlet.address,
            "rating": outlet.business_rating,
            "review_count": outlet.business_review_count,
            "place_id": outlet.public_place_id,
            "city_regency": outlet.city_regency,
            "district": outlet.district,
            "already_synced": Review.query.filter_by(outlet_id=outlet.id).count() > 0,
        })
    db.session.commit()

    if not created:
        return jsonify({"error": "Tidak ada outlet valid yang dipilih."}), 400
    return jsonify({"outlets": created})


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _int(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ─── STEP 4: SYNC (background + progress) ──────────────────
@bp.route("/sync", methods=["POST"])
@login_required
def sync():
    business = _get_business()
    if not business:
        return jsonify({"error": "Belum ada bisnis terhubung."}), 400
    data = request.get_json(silent=True) or {}
    outlet_ids = data.get("outlet_ids") or ([data.get("outlet_id")] if data.get("outlet_id") else [])
    mode = (data.get("mode") or "incremental").strip()
    outlet_ids = [x for x in outlet_ids if x]

    outlets = Outlet.query.filter(
        Outlet.id.in_(outlet_ids), Outlet.tenant_id == business.tenant_id
    ).all() if outlet_ids else []
    if not outlets:
        return jsonify({"error": "Outlet tidak ditemukan."}), 404
    outlet_id = outlets[0].id

    if _SYNC_PROGRESS.get(outlet_id, {}).get("running"):
        return jsonify({"error": "Sinkronisasi sedang berjalan."}), 409

    progress = {
        "outlet_id": outlet_id,
        "outlet_ids": outlet_ids,
        "running": True,
        "stage": "syncing",
        "done": False,
        "error": None,
        "received": 0,
        "total": 0,
        "stats": {},
        "started_at": _now().isoformat(),
    }
    _SYNC_PROGRESS[outlet_id] = progress

    # Capture primitives + app object for use inside the worker thread
    from flask import current_app
    _app = current_app._get_current_object()
    _tenant_id = business.tenant_id
    _business_id = business.id
    _start = _now()

    def _work():
        try:
            with _app.app_context():
                from app.services.public_provider import build_public_review_adapter
                from app.services.sync_service import sync_public_reviews
                adapter = build_public_review_adapter()
                progress["stage"] = "syncing"
                rep = sync_public_reviews(
                    tenant_id=_tenant_id,
                    business_id=_business_id,
                    outlet_ids=outlet_ids,
                    adapter=adapter,
                    source=getattr(adapter, "source_name", "provider"),
                    full_sync=(mode == "full"),
                    sort=("lowestRanking" if mode == "negatif" else "newest"),
                )
                progress["stage"] = "analyzing"
                progress["received"] = rep.get("reviews_received", 0)
                progress["total"] = rep.get("reviews_received", 0)
                progress["stats"] = {
                    "received": rep.get("reviews_received", 0),
                    "inserted": rep.get("reviews_inserted", 0),
                    "updated": rep.get("reviews_updated", 0),
                    "skipped": rep.get("reviews_skipped", 0),
                    "failed": rep.get("locations_failed", 0),
                    "duration_s": round(
                        (datetime.now(timezone.utc) - _start).total_seconds(), 1
                    ),
                }
                progress["stage"] = "done"
                progress["done"] = True
        except Exception as exc:
            logger.warning("onboarding sync failed: %s", exc)
            progress["error"] = _friendly_error(exc)
            progress["stage"] = "error"
            progress["done"] = True
        finally:
            progress["running"] = False

    threading.Thread(target=_work, daemon=True).start()
    return jsonify({"started": True, "outlet_id": outlet_id})


# ─── STEP 4b: PROGRESS POLL ────────────────────────────────
@bp.route("/status")
@login_required
def status():
    outlet_id = request.args.get("outlet_id", "")
    progress = _SYNC_PROGRESS.get(outlet_id)
    if progress is None:
        return jsonify({"progress": None}), 404
    return jsonify({"progress": progress})
