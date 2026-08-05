"""Public Business Search — GRM-003.

POST /search — visitor mencari bisnis publik (Google Maps) tanpa login.
Menggunakan mock data dari app.services.discovery (TAG: mock_adapter).
"""

import hashlib
import re
import logging
from typing import Optional
from flask import Blueprint, request, render_template, redirect, url_for
from app.services.discovery import search_places
from app.services.preview import register_dynamic_preview
import time

logger = logging.getLogger(__name__)

# ─── Resolved place cache ─────────────────────────────────
# Maps place_id → {display_name, google_maps_uri} from goo.gl resolution
_RESOLVED_PLACES: dict[str, dict] = {}

bp = Blueprint("public_search", __name__)

# ─── In-memory rate limiter ──────────────────────────────
# Format: {ip: [timestamps...]}
# MAX 10 requests per 60 seconds per IP
_RATE_LIMIT = {}
_RATE_MAX = 10
_RATE_WINDOW = 60


def _check_rate(ip: str) -> bool:
    """Return True if allowed, False if rate limited."""
    now = time.time()
    window_start = now - _RATE_WINDOW
    if ip in _RATE_LIMIT:
        _RATE_LIMIT[ip] = [t for t in _RATE_LIMIT[ip] if t > window_start]
    else:
        _RATE_LIMIT[ip] = []
    if len(_RATE_LIMIT[ip]) >= _RATE_MAX:
        return False
    _RATE_LIMIT[ip].append(now)
    return True


def _dynamic_place_id(query: str) -> str:
    """Generate a deterministic place_id from query text for dynamic previews."""
    return "dynamic:md5:" + hashlib.md5(query.strip().lower().encode()).hexdigest()[:16]


@bp.route("/search", methods=["GET", "POST"])
def search():
    query = ""
    city = ""
    results = []
    error = None
    searched = False

    if request.method == "POST":
        ip = request.remote_addr or "127.0.0.1"
        if not _check_rate(ip):
            error = "⏳ Terlalu banyak pencarian. Silakan tunggu 1 menit, lalu coba lagi."
            searched = True
        else:
            query = _parse_query(request.form.get("q", "").strip())
            city = request.form.get("city", "").strip() or None

            if not query or len(query) < 2:
                error = "Masukkan minimal 2 karakter untuk mencari."
                searched = True
            else:
                searched = True
                # Check if query was resolved from a Google Maps short link first
                resolved = _find_resolved_place(query)
                if resolved:
                    return redirect(
                        url_for("public_preview.preview_page",
                                q=resolved["display_name"],
                                place_id=resolved["place_id"])
                    )

                results = search_places(query, city, live_search=False)

                # Single result → redirect to public preview
                if len(results) == 1:
                    r = results[0]
                    return redirect(
                        url_for("public_preview.preview_page",
                                q=r["display_name"],
                                place_id=r["place_id"])
                    )

                if len(results) == 0:
                    # No results → create dynamic preview for ANY brand name
                    place_id = _dynamic_place_id(query)
                    display_name = query.upper() if query.isascii() else query.title()
                    register_dynamic_preview(place_id, display_name)
                    return redirect(
                        url_for("public_preview.preview_page",
                                q=display_name,
                                place_id=place_id)
                    )

    # GET: show search page with optional ?q=
    if request.method == "GET":
        query = _parse_query(request.args.get("q", "").strip())
        if query and len(query) >= 2:
            # Check if query was resolved from a Google Maps short link first
            resolved = _find_resolved_place(query)
            if resolved:
                return redirect(
                    url_for("public_preview.preview_page",
                            q=resolved["display_name"],
                            place_id=resolved["place_id"])
                )

            results = search_places(query, city, live_search=False)
            searched = True
            if len(results) == 1:
                r = results[0]
                return redirect(
                    url_for("public_preview.preview_page",
                            q=r["display_name"],
                            place_id=r["place_id"])
                )
            if len(results) == 0:
                resolved = _find_resolved_place(query)
                if resolved:
                    return redirect(
                        url_for("public_preview.preview_page",
                                q=resolved["display_name"],
                                place_id=resolved["place_id"])
                    )
                # No results → create dynamic preview for ANY brand name
                place_id = _dynamic_place_id(query)
                display_name = query.upper() if query.isascii() else query.title()
                register_dynamic_preview(place_id, display_name)
                return redirect(
                    url_for("public_preview.preview_page",
                            q=display_name,
                            place_id=place_id)
                )

    return render_template(
        "landing/search.html",
        query=query,
        city=city,
        results=results,
        error=error,
        searched=searched,
        result_count=len(results),
        search_source=results[0].get("source", "") if results else "",
        search_time_ms=results[0].get("response_time_ms", 0) if results else 0,
    )


def _find_resolved_place(query: str) -> Optional[dict]:
    """Find a place resolved from a Google Maps short link by name match."""
    q = query.lower().strip()
    for place_id, info in _RESOLVED_PLACES.items():
        if info["display_name"].lower() == q or q in info["display_name"].lower():
            return {"place_id": place_id, "display_name": info["display_name"]}
        if info["display_name"].lower().startswith(q):
            return {"place_id": place_id, "display_name": info["display_name"]}
    if query in _RESOLVED_PLACES:
        info = _RESOLVED_PLACES[query]
        return {"place_id": query, "display_name": info["display_name"]}
    return None


def _parse_query(raw: str) -> str:
    """Extract business name from raw input, handling Google Maps URLs.

    For goo.gl short links: resolves the redirect to extract place_name + place_id.
    The resolved place_id is stored for downstream preview use.
    """
    raw = raw.strip()
    if "maps.app.goo.gl" in raw or "goo.gl/maps" in raw:
        resolved = _resolve_google_maps_short_link(raw)
        if resolved:
            return resolved
        return raw
    m = re.search(r'/place/([^/@]+)', raw)
    if m:
        name = m.group(1).replace('+', ' ').strip()
        return name
    m = re.search(r'[?&]q=([^&]+)', raw)
    if m and ('google.com/maps' in raw or 'maps.google' in raw):
        return m.group(1).replace('+', ' ').strip()
    return raw


def _resolve_google_maps_short_link(url: str) -> Optional[str]:
    """Follow a maps.app.goo.gl redirect to extract place name and place_id.

    Returns the business name on success, None on failure.
    Stores resolved place info in _RESOLVED_PLACES for downstream use.
    """
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent",
                       "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
        resp = urllib.request.urlopen(req, timeout=8)
        final_url = resp.geturl()

        # Extract place name: /place/NAME/
        name_m = re.search(r'/place/([^/@]+)', final_url)
        place_name = name_m.group(1).replace('+', ' ').strip() if name_m else None

        # Extract feature ID: ftid=0x... or !1s0x...
        ftid_m = re.search(r'ftid=(0x[0-9a-f]+:0x[0-9a-f]+)', final_url)
        if not ftid_m:
            ftid_m = re.search(r'!1s(0x[0-9a-f]+:0x[0-9a-f]+)', final_url)

        if ftid_m and place_name:
            feature_id = ftid_m.group(1)
            _RESOLVED_PLACES[feature_id] = {
                "display_name": place_name,
                "google_maps_uri": url,
            }
            # Also index by name for lookup
            _RESOLVED_PLACES[place_name.lower()] = {
                "display_name": place_name,
                "google_maps_uri": url,
            }
            logger.info(
                "Short link resolved: %s → name=%s feature_id=%s",
                url, place_name, feature_id,
            )
            # Register dynamic preview now so preview page can render it
            register_dynamic_preview(feature_id, place_name, google_maps_uri=url)
            return place_name

        logger.warning("Short link resolved but no place data extracted: %s", final_url)
        return None
    except urllib.error.URLError as exc:
        logger.warning("Short link resolve failed for %s: %s", url, exc)
        return None
    except Exception as exc:
        logger.error("Unexpected error resolving %s: %s", url, exc)
        return None
