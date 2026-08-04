"""Public Preview Page — GRM-004.

GET /preview?place_id=xxx — preview analisis publik (no auth).
Menggunakan mock data dari app.services.preview (TAG: mock_data).
"""

from flask import Blueprint, render_template, request, redirect, url_for

from app.services.preview import get_preview_data, normalize_place_id
from app.services.discovery import search_places

bp = Blueprint("public_preview", __name__, url_prefix="/preview")


@bp.route("", methods=["GET"])
def preview_page():
    """Render public preview analysis page."""
    place_id = normalize_place_id(request.args.get("place_id", ""))
    query = request.args.get("q", "").strip()

    if not place_id:
        # If called without place_id, redirect to search
        return _no_place_id(query)

    preview = get_preview_data(place_id)
    if not preview:
        return _not_found(query, place_id)

    return render_template("landing/preview.html", preview=preview, query=query)


def _no_place_id(query: str):
    """Handle missing place_id — redirect to search or show error."""
    if query:
        return redirect(url_for("public_search.search_page", q=query))
    return render_template("landing/preview.html", preview=None, query="",
                           error="Silakan pilih bisnis dari hasil pencarian.")


def _not_found(query: str, place_id: str):
    """Handle unknown place_id."""
    return render_template("landing/preview.html", preview=None, query=query,
                           error=f"Data preview untuk {place_id[:20]}... belum tersedia. "
                                 "Coba cari bisnis lain atau tunggu data kami terkumpul.")
