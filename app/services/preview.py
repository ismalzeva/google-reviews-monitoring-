"""Public Preview Analytics Service — GRM-004.

TAG: mock_data — data statis per place_id untuk MVP.
TAG: mock_cache — in-memory dictionary, TTL 24 jam.

Target production: Apify Google Maps crawler → structured review data.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_cache: dict[str, dict] = {}
_cache_ttl: int = 86400  # 24 jam


def _cache_key(place_id: str, tenant_id: Optional[str] = None) -> str:
    """HF-005: Tenant-scoped real data MUST use tenant-specific cache key.

    Plain key (`preview:{place_id}`) holds ONLY static mock data.
    Tenant key (`preview:{place_id}:tenant:{uuid}`) holds tenant-scoped real
    data — collision across tenants impossible because tenant_id is a UUID.
    """
    if tenant_id:
        return f"preview:{place_id}:tenant:{tenant_id}"
    return f"preview:{place_id}"


def _cache_get(place_id: str, tenant_id: Optional[str] = None) -> Optional[dict]:
    key = _cache_key(place_id, tenant_id)
    entry = _cache.get(key)
    if entry and entry["_expires"] > time.time():
        return entry["_data"]
    if entry:
        del _cache[key]
    return None


def _cache_set(place_id: str, data: dict, tenant_id: Optional[str] = None) -> None:
    key = _cache_key(place_id, tenant_id)
    _cache[key] = {"_data": data, "_expires": time.time() + _cache_ttl}


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------


@dataclass
class MockPreview:
    place_id: str
    display_name: str
    formatted_address: str
    city: str
    rating: float
    review_count: int
    distribution: dict  # {5:150, 4:80, 3:30, 2:15, 1:8}
    top_issues: list[dict]  # [{title, count, category}]
    ai_teaser_visible: list[dict]  # 2 visible
    ai_teaser_locked: dict  # 1 locked
    branch_selector: list[dict]  # [{place_id, name, rating}]


# Per-branch mock data (different distributions for realism)
MOCK_BRANCHES: dict[str, MockPreview] = {
    "ChIJ0_depok-margonda-001": MockPreview(
        place_id="ChIJ0_depok-margonda-001",
        display_name="Bubur Fay Depok",
        formatted_address="Jl. Margonda Raya No. 88, Depok, Jawa Barat",
        city="Depok",
        rating=4.5,
        review_count=1280,
        distribution={5: 720, 4: 350, 3: 120, 2: 55, 1: 35},
        top_issues=[
            {"title": "Penyajian terlalu lama", "count": 89, "category": "kecepatan"},
            {"title": "Parkir sulit & sempit", "count": 64, "category": "fasilitas"},
            {"title": "Kebersihan meja kurang", "count": 41, "category": "kebersihan"},
        ],
        ai_teaser_visible=[
            {"title": "Tim kitchen perlu tambahan jam sibuk", "count": 89},
            {"title": "Area parkir perlu koordinasi security", "count": 64},
        ],
        ai_teaser_locked={"title": "Stok bahan baku harian perlu audit", "count": 23},
        branch_selector=[
            {"place_id": "ChIJ0_depok-margonda-001", "name": "Depok (Margonda)", "rating": 4.5},
            {"place_id": "ChIJ0_depok-cimanggis-002", "name": "Depok (Cimanggis)", "rating": 3.8},
            {"place_id": "ChIJ0_bekasi-gm-003", "name": "Bekasi (Grand Mall)", "rating": 4.3},
        ],
    ),
    "ChIJ0_depok-cimanggis-002": MockPreview(
        place_id="ChIJ0_depok-cimanggis-002",
        display_name="Bubur Fay Harjamukti",
        formatted_address="Jl. Harjamukti No. 15, Cimanggis, Depok",
        city="Depok",
        rating=3.8,
        review_count=120,
        distribution={5: 18, 4: 42, 3: 30, 2: 18, 1: 12},
        top_issues=[
            {"title": "Rasa tidak konsisten antar hari", "count": 28, "category": "kualitas"},
            {"title": "Porsi mengecil bertahap", "count": 19, "category": "harga"},
            {"title": "Karyawan kurang ramah", "count": 14, "category": "pelayanan"},
        ],
        ai_teaser_visible=[
            {"title": "Perlu SOP standarisasi resep per shift", "count": 28},
            {"title": "Porsi perlu ditimbang ulang & diseragamkan", "count": 19},
        ],
        ai_teaser_locked={"title": "Jadwal evaluasi performa karyawan", "count": 14},
        branch_selector=[
            {"place_id": "ChIJ0_depok-margonda-001", "name": "Depok (Margonda)", "rating": 4.5},
            {"place_id": "ChIJ0_depok-cimanggis-002", "name": "Depok (Cimanggis)", "rating": 3.8},
            {"place_id": "ChIJ0_bekasi-gm-003", "name": "Bekasi (Grand Mall)", "rating": 4.3},
        ],
    ),
    "ChIJ0_bekasi-gm-003": MockPreview(
        place_id="ChIJ0_bekasi-gm-003",
        display_name="Bubur Fay Bekasi",
        formatted_address="Grand Mall Bekasi, Lt. 1, Jl. Ahmad Yani No. 1, Bekasi",
        city="Bekasi",
        rating=4.3,
        review_count=980,
        distribution={5: 450, 4: 310, 3: 130, 2: 55, 1: 35},
        top_issues=[
            {"title": "Pelayanan lambat saat weekend", "count": 72, "category": "kecepatan"},
            {"title": "Harga naik tanpa pemberitahuan", "count": 48, "category": "harga"},
            {"title": "Kualitas bubur turun malam hari", "count": 36, "category": "kualitas"},
        ],
        ai_teaser_visible=[
            {"title": "Tim tambahan weekend perlu disiapkan", "count": 72},
            {"title": "Transparansi harga perlu di-publish di menu", "count": 48},
        ],
        ai_teaser_locked={"title": "Jadwal shift cook malam + SOP quality check", "count": 36},
        branch_selector=[
            {"place_id": "ChIJ0_bekasi-gm-003", "name": "Bekasi (Grand Mall)", "rating": 4.3},
            {"place_id": "ChIJ0_depok-margonda-001", "name": "Depok (Margonda)", "rating": 4.5},
            {"place_id": "ChIJ0_depok-cimanggis-002", "name": "Depok (Cimanggis)", "rating": 3.8},
        ],
    ),
    "ChIJ0_jakarta-thamrin-004": MockPreview(
        place_id="ChIJ0_jakarta-thamrin-004",
        display_name="Bubur Fay Jakarta Pusat",
        formatted_address="Jl. MH Thamrin No. 10, Jakarta Pusat, DKI Jakarta",
        city="Jakarta Pusat",
        rating=4.4,
        review_count=2150,
        distribution={5: 1200, 4: 580, 3: 220, 2: 90, 1: 60},
        top_issues=[
            {"title": "Antrian panjang jam makan siang", "count": 145, "category": "kecepatan"},
            {"title": "AC kurang dingin di lantai 2", "count": 78, "category": "fasilitas"},
            {"title": "Kasir error saat pembayaran QRIS", "count": 42, "category": "teknis"},
        ],
        ai_teaser_visible=[
            {"title": "Sistem antrian digital perlu dipertimbangkan", "count": 145},
            {"title": "Maintenance AC perlu jadwal rutin bulanan", "count": 78},
        ],
        ai_teaser_locked={"title": "Integrasi POS + payment gateway audit", "count": 42},
        branch_selector=[
            {"place_id": "ChIJ0_jakarta-thamrin-004", "name": "Jakarta Pusat (Thamrin)", "rating": 4.4},
            {"place_id": "ChIJ0_tangerang-alsut-005", "name": "Tangerang (Alam Sutera)", "rating": 4.6},
            {"place_id": "ChIJ0_bekasi-gm-003", "name": "Bekasi (Grand Mall)", "rating": 4.3},
        ],
    ),
    "ChIJ0_tangerang-alsut-005": MockPreview(
        place_id="ChIJ0_tangerang-alsut-005",
        display_name="Bubur Fay Tangerang",
        formatted_address="Alam Sutera Town Center, Jl. Alam Sutera Boulevard, Tangerang",
        city="Tangerang",
        rating=4.6,
        review_count=1540,
        distribution={5: 920, 4: 400, 3: 140, 2: 50, 1: 30},
        top_issues=[
            {"title": "Parkir bayar mahal di mall", "count": 56, "category": "fasilitas"},
            {"title": "Kursi terbatas saat event", "count": 38, "category": "kapasitas"},
            {"title": "Toilet jauh dari tenant", "count": 22, "category": "fasilitas"},
        ],
        ai_teaser_visible=[
            {"title": "Kerjasama validasi parkir dengan mall", "count": 56},
            {"title": "Sewa space tambahan saat high season", "count": 38},
        ],
        ai_teaser_locked={"title": "Relokasi tenant yang lebih strategis", "count": 22},
        branch_selector=[
            {"place_id": "ChIJ0_tangerang-alsut-005", "name": "Tangerang (Alam Sutera)", "rating": 4.6},
            {"place_id": "ChIJ0_jakarta-thamrin-004", "name": "Jakarta Pusat (Thamrin)", "rating": 4.4},
            {"place_id": "ChIJ0_bekasi-gm-003", "name": "Bekasi (Grand Mall)", "rating": 4.3},
        ],
    ),
    "ChIJ0_bogor-botani-004": MockPreview(
        place_id="ChIJ0_bogor-botani-004",
        display_name="Bubur Fay Bogor",
        formatted_address="Botani Square, Lt. 2, Jl. Pajajaran, Bogor",
        city="Bogor",
        rating=4.2,
        review_count=670,
        distribution={5: 280, 4: 220, 3: 100, 2: 45, 1: 25},
        top_issues=[
            {"title": "Suhu bubur kurang panas saat disajikan", "count": 52, "category": "kualitas"},
            {"title": "Harga lebih mahal dari cabang lain", "count": 41, "category": "harga"},
            {"title": "Antar makanan ke meja lambat", "count": 33, "category": "kecepatan"},
        ],
        ai_teaser_visible=[
            {"title": "Food warmer perlu di-check setiap 30 menit", "count": 52},
            {"title": "Harga perlu disesuaikan dengan area Bogor", "count": 41},
        ],
        ai_teaser_locked={"title": "Standar antar-meja: SLA 5 menit", "count": 33},
        branch_selector=[
            {"place_id": "ChIJ0_bogor-botani-004", "name": "Bogor (Botani Square)", "rating": 4.2},
            {"place_id": "ChIJ0_depok-margonda-001", "name": "Depok (Margonda)", "rating": 4.5},
            {"place_id": "ChIJ0_tangerang-alsut-005", "name": "Tangerang (Alam Sutera)", "rating": 4.6},
        ],
    ),
    "ChIJ0_official-depok-001": MockPreview(
        place_id="ChIJ0_official-depok-001",
        display_name="Bubur Fay Official Store Depok",
        formatted_address="Jl. Margonda Raya No. 88, Depok, Jawa Barat",
        city="Depok",
        rating=4.5,
        review_count=1280,
        distribution={5: 720, 4: 350, 3: 120, 2: 55, 1: 35},
        top_issues=[
            {"title": "Penyajian terlalu lama", "count": 89, "category": "kecepatan"},
            {"title": "Parkir sulit & sempit", "count": 64, "category": "fasilitas"},
            {"title": "Kebersihan meja kurang", "count": 41, "category": "kebersihan"},
        ],
        ai_teaser_visible=[
            {"title": "Tim kitchen perlu tambahan jam sibuk", "count": 89},
            {"title": "Area parkir perlu koordinasi security", "count": 64},
        ],
        ai_teaser_locked={"title": "Stok bahan baku harian perlu audit", "count": 23},
        branch_selector=[
            {"place_id": "ChIJ0_official-depok-001", "name": "Depok Official Store", "rating": 4.5},
            {"place_id": "ChIJ0_depok-cimanggis-002", "name": "Depok (Cimanggis)", "rating": 3.8},
            {"place_id": "ChIJ0_bekasi-gm-003", "name": "Bekasi (Grand Mall)", "rating": 4.3},
        ],
    ),
    # Kopi Ketjil Pondok Indah — real Google Maps listing
    "ChIJUWmProXY8Z4RcggGriWJTKY": MockPreview(
        place_id="ChIJUWmProXY8Z4RcggGriWJTKY",
        display_name="Kopi Ketjil Pondok Indah",
        formatted_address="Jl. Metro Pondok Indah, Jakarta Selatan, DKI Jakarta",
        city="Jakarta Selatan",
        rating=4.4,
        review_count=245,
        distribution={5: 120, 4: 72, 3: 28, 2: 15, 1: 10},
        top_issues=[
            {"title": "Antrian terlalu lama saat weekend", "count": 34, "category": "kecepatan"},
            {"title": "Parkir terbatas di area ruko", "count": 28, "category": "fasilitas"},
            {"title": "Harga menu terlalu premium untuk porsi", "count": 22, "category": "harga"},
        ],
        ai_teaser_visible=[
            {"title": "Perlu tambahan barista saat peak weekend", "count": 34},
            {"title": "Sistem antrian digital bisa kurangi wait time", "count": 28},
        ],
        ai_teaser_locked={"title": "Kopi single origin batch consistency", "count": 19},
        branch_selector=[
            {"place_id": "ChIJUWmProXY8Z4RcggGriWJTKY", "name": "Pondok Indah (Utama)", "rating": 4.4},
            {"place_id": "ChIJUWmProXY8Z4RcggGriWJTKY", "name": "Kemang (Cabang)", "rating": 4.2},
        ],
    ),
}


def normalize_place_id(place_id: str) -> str:
    """Normalize a Google Place ID for consistent internal use.

    DISC-002: Strips whitespace. Real Google Place IDs are opaque;
    no semantic transform applied.
    """
    return (place_id or "").strip()


def _try_alternate_format(place_id: str) -> Optional[str]:
    """Try alternate underscore/hyphen variant if exact lookup fails.

    Google Place IDs use underscores naturally (ChIJ0_xxx_yyy),
    but mock entries use mixed format (ChIJ0_xxx-yyy-NNN).
    Try multiple variants: prefix swap, all-underscore, all-hyphen.
    """
    # 1. Swap ChIJ prefix format (ChIJ0- ↔ ChIJ0_)
    if place_id.startswith("ChIJ0-"):
        alt = "ChIJ0_" + place_id[6:]
        if alt in MOCK_BRANCHES:
            return alt
    elif place_id.startswith("ChIJ0_"):
        alt = "ChIJ0-" + place_id[6:]
        if alt in MOCK_BRANCHES:
            return alt

    # 2. All-underscore variant
    alt_us = place_id.replace("-", "_")
    if alt_us != place_id and alt_us in MOCK_BRANCHES:
        return alt_us

    # 3. All-hyphen variant
    alt_hyp = place_id.replace("_", "-")
    if alt_hyp != place_id and alt_hyp in MOCK_BRANCHES:
        return alt_hyp

    return None


def get_preview_data(place_id: str, tenant_id: Optional[str] = None) -> Optional[MockPreview]:
    """Retrieve preview data for a place_id (cache-first).

    HF-005 FAIL-CLOSED contract:
    - tenant_id provided → real data ONLY from that tenant (tenant-scoped
      query + tenant-scoped cache key). Mock fallback allowed.
    - tenant_id=None → NO real-data query at all. Mock/static data only.
      Never picks an outlet from any tenant, never returns another
      tenant's branch selector.

    Callers that need real data MUST pass tenant_id.
    """
    place_id = normalize_place_id(place_id)
    if not place_id:
        return None

    # 1. Tenant-scoped real data (only when caller proves tenant)
    real = None
    if tenant_id:
        # Cache lookup scoped to this tenant only — cannot collide with
        # other tenants or with the anonymous mock cache namespace.
        cached = _cache_get(place_id, tenant_id)
        if cached:
            logger.info("preview cache hit for %s (tenant)", place_id)
            return MockPreview(**cached)

        real = _from_real_outlet(place_id, tenant_id=tenant_id)
        if real:
            _cache_set(place_id, {
                "place_id": real.place_id,
                "display_name": real.display_name,
                "formatted_address": real.formatted_address,
                "city": real.city,
                "rating": real.rating,
                "review_count": real.review_count,
                "distribution": real.distribution,
                "top_issues": real.top_issues,
                "ai_teaser_visible": real.ai_teaser_visible,
                "ai_teaser_locked": real.ai_teaser_locked,
                "branch_selector": real.branch_selector,
            }, tenant_id=tenant_id)
            logger.info("preview REAL hit for %s (%s, %d reviews)",
                        place_id, real.display_name, real.review_count)
            return real

    # 2. Anonymous / no-real-data path: static mock data ONLY.
    #    Cache key has NO tenant component → holds only static content.
    cached = _cache_get(place_id, None)
    if cached:
        logger.info("preview cache hit for %s", place_id)
        return MockPreview(**cached)

    mock = MOCK_BRANCHES.get(place_id)
    if not mock:
        alt_id = _try_alternate_format(place_id)
        if alt_id:
            mock = MOCK_BRANCHES.get(alt_id)
            if mock:
                logger.info("preview alt-format match: %s → %s", place_id, alt_id)
    if mock:
        _cache_set(place_id, {
            "place_id": mock.place_id,
            "display_name": mock.display_name,
            "formatted_address": mock.formatted_address,
            "city": mock.city,
            "rating": mock.rating,
            "review_count": mock.review_count,
            "distribution": mock.distribution,
            "top_issues": mock.top_issues,
            "ai_teaser_visible": mock.ai_teaser_visible,
            "ai_teaser_locked": mock.ai_teaser_locked,
            "branch_selector": mock.branch_selector,
        }, tenant_id=None)
        logger.info("preview mock hit for %s (%s)", place_id, mock.display_name)
        return mock

    logger.warning("preview miss for %s", place_id)

    # 3. Check dynamic previews (resolved from Google Maps short links)
    dynamic = _DYNAMIC_PREVIEWS.get(place_id)
    if dynamic:
        preview = _build_dynamic_mock_preview(place_id, dynamic)
        _cache_set(place_id, {
            "place_id": preview.place_id,
            "display_name": preview.display_name,
            "formatted_address": preview.formatted_address,
            "city": preview.city,
            "rating": preview.rating,
            "review_count": preview.review_count,
            "distribution": preview.distribution,
            "top_issues": preview.top_issues,
            "ai_teaser_visible": preview.ai_teaser_visible,
            "ai_teaser_locked": preview.ai_teaser_locked,
            "branch_selector": preview.branch_selector,
        })
        logger.info("preview dynamic hit for %s (%s)", place_id, dynamic.get("display_name"))
        return preview

    return None


# ─── Dynamic Preview Registration ─────────────────────
# Populated from Google Maps short link resolution.
# Format: {place_id: {display_name, google_maps_uri, city, rating, review_count}}
_DYNAMIC_PREVIEWS: dict[str, dict] = {}


def register_dynamic_preview(place_id: str, display_name: str,
                              google_maps_uri: str = "",
                              city: str = "Indonesia",
                              rating: float = 4.0,
                              review_count: int = 100) -> None:
    """Register a place for dynamic preview — used for short-link resolution."""
    _DYNAMIC_PREVIEWS[place_id] = {
        "display_name": display_name,
        "google_maps_uri": google_maps_uri,
        "city": city,
        "rating": rating,
        "review_count": review_count,
    }
    # Clear any existing cache for this place_id
    key = f"preview:{place_id}"
    if key in _cache:
        del _cache[key]
    logger.info("Dynamic preview registered: %s (%s)", place_id, display_name)


def _build_dynamic_mock_preview(place_id: str, info: dict) -> MockPreview:
    """Build a basic MockPreview for a dynamically resolved place."""
    rating = info.get("rating", 4.0)
    review_count = info.get("review_count", 100)
    # Estimate distribution from rating
    dist = _estimate_distribution(rating, review_count)
    display_name = info.get("display_name", "Unknown Business")
    city = info.get("city", "Indonesia")

    return MockPreview(
        place_id=place_id,
        display_name=display_name,
        formatted_address=info.get("google_maps_uri", ""),
        city=city,
        rating=rating,
        review_count=review_count,
        distribution=dist,
        top_issues=[
            {"title": "Data review sedang dikumpulkan", "count": review_count, "category": "info"},
        ],
        ai_teaser_visible=[
            {"title": "Review asli dari Google Maps akan muncul di sini", "count": 0},
        ],
        ai_teaser_locked={"title": "Analisis AI menunggu data review", "count": 0},
        branch_selector=[
            {"place_id": place_id, "name": display_name, "rating": rating},
        ],
    )


def _estimate_distribution(rating: float, total: int) -> dict:
    """Estimate a realistic star distribution from an average rating."""
    if rating >= 4.5:
        p5, p4, p3, p2, p1 = 50, 30, 12, 5, 3
    elif rating >= 4.0:
        p5, p4, p3, p2, p1 = 35, 35, 18, 8, 4
    elif rating >= 3.5:
        p5, p4, p3, p2, p1 = 20, 30, 30, 12, 8
    elif rating >= 3.0:
        p5, p4, p3, p2, p1 = 10, 25, 30, 20, 15
    else:
        p5, p4, p3, p2, p1 = 5, 15, 25, 30, 25
    return {
        5: round(total * p5 / 100),
        4: round(total * p4 / 100),
        3: round(total * p3 / 100),
        2: round(total * p2 / 100),
        1: round(total * p1 / 100),
    }


def _group_issues(neg_reviews: list, total: int) -> list[dict]:
    """Group negative/neutral reviews into thematic issues by keyword matching."""
    if not neg_reviews:
        return []

    KEYWORD_MAP = {
        "pelayanan": ["pelayan", "pegawai", "staff", "karyawan", "kasir", "pramusaji", "waiters",
                      "ga ramah", "tidak ramah", "cuek", "judes", "kasar", "lambat", "lemot",
                      "ngobrol", "main hp", "senyum", "sopan", "ramah"],
        "rasa": ["rasa", "enak", "lezat", "hambar", "asin", "manis", "pedas", "gurih",
                 "tidak enak", "ga enak", "basi", "berubah", "tidak konsisten", "konsisten"],
        "harga": ["harga", "mahal", "murah", "naik", "overprice", "worth it", "sepadan",
                  "kemahalan", "ngga worth"],
        "porsi": ["porsi", "dikit", "sedikit", "banyak", "mengecil", "berkurang", "nambah"],
        "tempat": ["tempat", "bersih", "kotor", "bau", "sempit", "parkir", "toilet",
                   "wc", "mushola", "ac", "panas", "gerah", "nyaman", "ambience", "suasana"],
        "kecepatan": ["lama", "nunggu", "antri", "waiting", "cepat", "lambat", "telat",
                      "menunggu", "ngantri"],
        "packaging": ["bungkus", "packaging", "kemasan", "tumpah", "bocor", "take away",
                      "takeaway", "bungkusan", "plastik"],
    }

    CATEGORY_LABELS = {
        "pelayanan": "Pelayanan",
        "rasa": "Kualitas Rasa",
        "harga": "Harga",
        "porsi": "Porsi",
        "tempat": "Tempat & Suasana",
        "kecepatan": "Kecepatan",
        "packaging": "Kemasan",
        "lainnya": "Masukan Lainnya",
    }

    groups = {}
    unmatched = []

    for r in neg_reviews:
        text = (r.comment or '').lower()
        matched = False
        for category, keywords in KEYWORD_MAP.items():
            if any(kw in text for kw in keywords):
                groups.setdefault(category, []).append(r)
                matched = True
                break
        if not matched:
            unmatched.append(r)
    
    if unmatched:
        groups["lainnya"] = unmatched

    # Build top issues
    issues = []
    for category, revs in sorted(groups.items(), key=lambda x: -len(x[1])):
        # Get best representative text
        sample_texts = [(r.comment or '').strip() for r in revs if (r.comment or '').strip()]
        title = sample_texts[0][:80] if sample_texts else "Masukan tanpa teks"
        
        issues.append({
            "title": title,
            "count": len(revs),
            "category": CATEGORY_LABELS.get(category, category),
        })

    return issues[:5] if issues else [
        {"title": "Perlu analisis lebih lanjut", "count": len(neg_reviews), "category": "Umum"}
    ]


def _from_real_outlet(place_id: str, tenant_id: Optional[str] = None) -> Optional[MockPreview]:
    """Build MockPreview from real database outlet + reviews.

    Only used when an outlet with matching public_place_id exists and has reviews.

    HF-005: When tenant_id is provided, scope query to that tenant only.
    Prevents cross-tenant data leakage in preview.
    """
    try:
        from app import create_app
        from flask import current_app

        # HF-005: Use existing app context if available (for testing)
        try:
            ctx_app = current_app._get_current_object()
        except RuntimeError:
            ctx_app = None

        if ctx_app:
            return _query_real_outlet(ctx_app, place_id, tenant_id)

        app = create_app()
        with app.app_context():
            return _query_real_outlet(app, place_id, tenant_id)
    except Exception as e:
        logger.warning("_from_real_outlet failed for %s: %s", place_id, e)
        return None


def _query_real_outlet(app, place_id: str, tenant_id: Optional[str] = None) -> Optional[MockPreview]:
    """Internal: query DB for real outlet data. Must be called within app context.

    HF-005 FAIL-CLOSED: tenant_id is REQUIRED. Without it, this function
    refuses to query any real outlet — returns None immediately.
    """
    # HF-005: FAIL-CLOSED — no tenant proof → no real data
    if not tenant_id:
        logger.warning(
            "_query_real_outlet called without tenant_id for %s — refused "
            "(fail-closed)", place_id)
        return None

    from app.models.entities import Outlet, Review
    from collections import Counter

    # HF-005: Tenant-scoped query
    query = Outlet.query.filter_by(public_place_id=place_id)
    if tenant_id is not None:
        query = query.filter_by(tenant_id=tenant_id)
    outlet = query.first()

    if not outlet:
        return None

    reviews = Review.query.filter_by(outlet_id=outlet.id).all()
    if not reviews:
        return None

    # Rating distribution
    dist_counter = Counter()
    for r in reviews:
        dist_counter[r.star_rating] += 1
    distribution = {
        5: dist_counter.get(5, 0),
        4: dist_counter.get(4, 0),
        3: dist_counter.get(3, 0),
        2: dist_counter.get(2, 0),
        1: dist_counter.get(1, 0),
    }

    total = len(reviews)

    # Negative reviews for top issues — group by keyword
    neg_reviews = [r for r in reviews if r.star_rating <= 3]
    top_issues = _group_issues(neg_reviews, total)

    avg_rating = round(sum(r.star_rating for r in reviews) / total, 1) if total > 0 else 0

    # HF-005: Build branch selector scoped to tenant
    outlet_query = Outlet.query.filter(Outlet.public_place_id.isnot(None))
    if tenant_id is not None:
        outlet_query = outlet_query.filter_by(tenant_id=tenant_id)
    all_outlets = outlet_query.all()
    branch_selector = []
    for o in all_outlets[:10]:
        branch_selector.append({
            "place_id": o.public_place_id,
            "name": o.name,
            "rating": o.business_rating or 0,
        })

    return MockPreview(
        place_id=place_id,
        display_name=outlet.name,
        formatted_address=outlet.address or '',
        city=outlet.city_regency or '',
        rating=avg_rating,
        review_count=total,
        distribution=distribution,
        top_issues=top_issues,
        ai_teaser_visible=top_issues[:2],
        ai_teaser_locked=top_issues[2] if len(top_issues) > 2 else {"title": "Butuh lebih banyak data review", "count": 0},
        branch_selector=branch_selector,
    )


def get_all_branches() -> list[MockPreview]:
    """Return semua cabang: real DB outlets + mock data."""
    branches = list(MOCK_BRANCHES.values())
    
    # Also include real outlets from database
    try:
        from app.models.entities import Outlet
        from app import create_app
        
        app = create_app()
        with app.app_context():
            real_outlets = Outlet.query.filter(
                Outlet.public_place_id.isnot(None),
                Outlet.public_place_id.notin_([b.place_id for b in branches])
            ).all()
            for o in real_outlets:
                branches.append(MockPreview(
                    place_id=o.public_place_id,
                    display_name=o.name,
                    formatted_address=o.address or '',
                    city=o.city_regency or '',
                    rating=o.business_rating or 0,
                    review_count=o.business_review_count or 0,
                    distribution={},
                    top_issues=[],
                    ai_teaser_visible=[],
                    ai_teaser_locked={"title": "", "count": 0},
                    branch_selector=[],
                ))
    except Exception:
        pass
    
    return branches
