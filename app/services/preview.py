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


def _cache_key(place_id: str) -> str:
    return f"preview:{place_id}"


def _cache_get(place_id: str) -> Optional[dict]:
    key = _cache_key(place_id)
    entry = _cache.get(key)
    if entry and entry["_expires"] > time.time():
        return entry["_data"]
    if entry:
        del _cache[key]
    return None


def _cache_set(place_id: str, data: dict) -> None:
    _cache[_cache_key(place_id)] = {"_data": data, "_expires": time.time() + _cache_ttl}


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


def get_preview_data(place_id: str) -> Optional[MockPreview]:
    """Retrieve preview data for a place_id (cache-first).

    DISC-002: Falls back to alternate underscore/hyphen format
    when exact lookup fails.
    """
    place_id = normalize_place_id(place_id)
    if not place_id:
        return None

    cached = _cache_get(place_id)
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
        })
        logger.info("preview mock hit for %s (%s)", place_id, mock.display_name)
        return mock

    logger.warning("preview miss for %s", place_id)
    return None


def get_all_branches() -> list[MockPreview]:
    """Return semua cabang yang tersedia di mock data."""
    return list(MOCK_BRANCHES.values())
