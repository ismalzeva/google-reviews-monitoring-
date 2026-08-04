"""Public Business Search — GRM-003.

POST /search — visitor mencari bisnis publik (Google Maps) tanpa login.
Menggunakan mock data dari app.services.discovery (TAG: mock_adapter).
"""

from flask import Blueprint, request, render_template, redirect, url_for
from app.services.discovery import search_places
import time

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
    # Clean old entries
    if ip in _RATE_LIMIT:
        _RATE_LIMIT[ip] = [t for t in _RATE_LIMIT[ip] if t > window_start]
    else:
        _RATE_LIMIT[ip] = []
    if len(_RATE_LIMIT[ip]) >= _RATE_MAX:
        return False
    _RATE_LIMIT[ip].append(now)
    return True


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
            query = request.form.get("q", "").strip()
            city = request.form.get("city", "").strip() or None

            if not query or len(query) < 2:
                error = "Masukkan minimal 2 karakter untuk mencari."
                searched = True
            else:
                searched = True
                results = search_places(query, city)

                # Single result → redirect to public preview
                if len(results) == 1:
                    r = results[0]
                    return redirect(
                        url_for("public_preview.preview_page",
                                q=r["display_name"],
                                place_id=r["place_id"])
                    )

                if len(results) == 0:
                    error = f"Tidak ditemukan hasil untuk \"{query}\". Coba:"
                    # Provide suggestions
                    suggestions = _get_suggestions(query)
                    if suggestions:
                        error += " " + ", ".join(suggestions)

    # GET: show search page with optional ?q=
    if request.method == "GET":
        query = request.args.get("q", "").strip()
        if query and len(query) >= 2:
            results = search_places(query)
            searched = True
            if len(results) == 1:
                r = results[0]
                return redirect(
                    url_for("public_preview.preview_page",
                            q=r["display_name"],
                            place_id=r["place_id"])
                )
            if len(results) == 0:
                error = f"Tidak ditemukan hasil untuk \"{query}\"."
                suggestions = _get_suggestions(query)
                if suggestions:
                    error += " Coba: " + ", ".join(suggestions)

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


def _get_suggestions(query: str) -> list[str]:
    """Give fallback suggestions for empty results."""
    q = query.lower()
    suggestions = []
    if "bubur" in q:
        suggestions.append('"Bubur Fay"')
    if any(w in q for w in ["bubur", "makanan", "restoran"]):
        suggestions.append('"Bubur Fay Bekasi"')
    if not suggestions:
        suggestions = ['"Bubur Fay"', '"Bubur Fay Bekasi"']
    return suggestions
