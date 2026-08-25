"""Public Preview Page — GRM-004.

GET /preview?place_id=xxx — preview analisis publik (no auth).
Menggunakan mock data dari app.services.preview (TAG: mock_data).

HF-005: When user is authenticated and owns an outlet with matching place_id,
show tenant-scoped real data instead of generic mock data.
"""

from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user

from app.services.preview import get_preview_data, normalize_place_id
from app.services.discovery import search_places

bp = Blueprint("public_preview", __name__, url_prefix="/preview")


@bp.route("", methods=["GET"])
def preview_page():
    """Render public preview analysis page.

    HF-005: If user is authenticated and has a business with tenant_id,
    pass tenant_id to get_preview_data for tenant-scoped results.
    """
    place_id = normalize_place_id(request.args.get("place_id", ""))
    query = request.args.get("q", "").strip()

    if not place_id:
        # If called without place_id, redirect to search
        return _no_place_id(query)

    # HF-005: Extract tenant_id from authenticated user
    tenant_id = None
    if current_user.is_authenticated and current_user.business:
        tenant_id = current_user.business.tenant_id

    preview = get_preview_data(place_id, tenant_id=tenant_id)
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
