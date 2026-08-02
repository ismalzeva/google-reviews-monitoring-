"""Mock public review adapter for GRM Public Monitoring.

Serves a fixed, realistic dataset of public Google reviews for the Bubur Fay
pilot brand (Depok + Margonda outlets). Used for development and quality-gate
testing. Tagged explicitly as ``mock`` — never presented as official Google
data (GRM_PUBLIC_MONITORING_SKILL §5, §13).
"""
from datetime import datetime, timezone
from typing import Optional

from app.adapters.public_review_source_adapter import PublicReviewSourceAdapter


def _dt(iso: str):
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


# ─── LOCATIONS ──────────────────────────────────────────────
MOCK_LOCATIONS = {
    "ChIJ0-depok-margonda-001": {
        "place_id": "ChIJ0-depok-margonda-001",
        "business_name": "Bubur Fay Depok",
        "full_address": "Jl. Raya Depok No. 21, Pancoran Mas, Kota Depok, Jawa Barat",
        "latitude": -6.4025,
        "longitude": 106.8187,
        "maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJ0-depok-margonda-001",
        "business_rating": 4.5,
        "business_review_count": 312,
        "source": "mock",
    },
    "ChIJ0-depok-margonda-002": {
        "place_id": "ChIJ0-depok-margonda-002",
        "business_name": "Bubur Fay Margonda",
        "full_address": "Jl. Margonda Raya No. 88, Beji, Kota Depok, Jawa Barat",
        "latitude": -6.3783,
        "longitude": 106.8314,
        "maps_url": "https://www.google.com/maps/place/?q=place_id:ChIJ0-depok-margonda-002",
        "business_rating": 4.2,
        "business_review_count": 187,
        "source": "mock",
    },
}

# ─── REVIEWS (Depok) ────────────────────────────────────────
_DEPOK_REVIEWS = [
    {
        "source_review_id": "depok-0001",
        "rating": 5,
        "review_text": "Buburnya enak banget, kuahnya gurih dan ayamnya empuk. Porsinya pas dan harganya bersahabat. Langganan tiap minggu!",
        "review_date": "2026-08-01T07:30:00+07:00",
        "review_datetime_raw": "1 Agustus 2026 07.30",
        "owner_reply_text": "Terima kasih sudah berlangganan, Kak! Senang mendengar Bunda suka.",
        "owner_reply_date": "2026-08-01T10:05:00+07:00",
        "reviewer_name_masked": "Dewi R***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-001", "reviewer_count": 12},
    },
    {
        "source_review_id": "depok-0002",
        "rating": 4,
        "review_text": "Rasa konsisten, pelayanan ramah. Sedikit kurang karena tempatnya panas siang-siang.",
        "review_date": "2026-07-28T11:15:00+07:00",
        "review_datetime_raw": "28 Juli 2026 11.15",
        "owner_reply_text": None,
        "owner_reply_date": None,
        "reviewer_name_masked": "Budi S***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-001"},
    },
    {
        "source_review_id": "depok-0003",
        "rating": 3,
        "review_text": "Buburnya enak tapi antreannya lama banget pas jam makan siang. Nunggu hampir 30 menit.",
        "review_date": "2026-07-25T12:40:00+07:00",
        "review_datetime_raw": "25 Juli 2026 12.40",
        "owner_reply_text": "Maaf atas tunggunya, Kak. Kami sedang menambah tenaga di jam ramai.",
        "owner_reply_date": "2026-07-26T09:00:00+07:00",
        "reviewer_name_masked": "Andi P***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-001"},
    },
    {
        "source_review_id": "depok-0004",
        "rating": 2,
        "review_text": "Harga naik terus tapi porsinya makin kecil. Kemaren dapatnya sedikit banget.",
        "review_date": "2026-07-20T08:10:00+07:00",
        "review_datetime_raw": "20 Juli 2026 08.10",
        "owner_reply_text": "Terima kasih masukannya, Kak. Kami akan evaluasi porsi dan harga.",
        "owner_reply_date": "2026-07-20T13:00:00+07:00",
        "reviewer_name_masked": "Sari W***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-001"},
    },
    {
        "source_review_id": "depok-0005",
        "rating": 1,
        "review_text": "Tadi pagi beli bubur, setelah makan langsung mual dan perut sakit. Semoga bukan karena makanannya tapi tolong perhatikan kebersihan dapur.",
        "review_date": "2026-07-18T06:55:00+07:00",
        "review_datetime_raw": "18 Juli 2026 06.55",
        "owner_reply_text": "Kami sangat menyesal atas pengalaman ini. Mohon hubungi kami langsung agar bisa kami tindaklanjuti.",
        "owner_reply_date": "2026-07-18T09:20:00+07:00",
        "reviewer_name_masked": "Rina T***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-001"},
    },
    {
        "source_review_id": "depok-0006",
        "rating": 5,
        "review_text": "Kebersihan terjaga, tempatnya nyaman buat sarapan sama keluarga. Anak-anak suka.",
        "review_date": "2026-07-15T07:05:00+07:00",
        "review_datetime_raw": "15 Juli 2026 07.05",
        "owner_reply_text": None,
        "owner_reply_date": None,
        "reviewer_name_masked": "Joko N***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-001"},
    },
    {
        "source_review_id": "depok-0007",
        "rating": 4,
        "review_text": "Bisa pesan lewat ojek online, datangnya cepat dan masih hangat. Packing rapi.",
        "review_date": "2026-07-10T13:20:00+07:00",
        "review_datetime_raw": "10 Juli 2026 13.20",
        "owner_reply_text": "Terima kasih, Kak! Senang pesanannya sampai dengan baik.",
        "owner_reply_date": "2026-07-10T15:00:00+07:00",
        "reviewer_name_masked": "Maya L***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-001"},
    },
    {
        "source_review_id": "depok-0008",
        "rating": 5,
        "review_text": "",
        "review_date": "2026-07-05T09:00:00+07:00",
        "review_datetime_raw": "5 Juli 2026 09.00",
        "owner_reply_text": None,
        "owner_reply_date": None,
        "reviewer_name_masked": "Anonim",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-001"},
    },
    {
        "source_review_id": "depok-0009",
        "rating": 4,
        "review_text": "Menu lengkap, kadang topping abon cepat habis pas weekend. Tapi overall oke.",
        "review_date": "2026-06-28T08:30:00+07:00",
        "review_datetime_raw": "28 Juni 2026 08.30",
        "owner_reply_text": None,
        "owner_reply_date": None,
        "reviewer_name_masked": "Putra H***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-001"},
    },
    {
        "source_review_id": "depok-0010",
        "rating": 5,
        "review_text": "Parkir luas, cocok buat yang bawa mobil. Buburnya juga mantap!",
        "review_date": "2026-06-20T07:45:00+07:00",
        "review_datetime_raw": "20 Juni 2026 07.45",
        "owner_reply_text": "Terima kasih, Kak! Sampai jumpa lagi.",
        "owner_reply_date": "2026-06-20T11:00:00+07:00",
        "reviewer_name_masked": "Hendra G***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-001"},
    },
]

# ─── REVIEWS (Margonda) ─────────────────────────────────────
_MARGONDA_REVIEWS = [
    {
        "source_review_id": "mgd-0001",
        "rating": 5,
        "review_text": "Cabang Margonda lebih seger rasanya, porsinya juga lebih banyak. Recommended!",
        "review_date": "2026-08-01T09:10:00+07:00",
        "review_datetime_raw": "1 Agustus 2026 09.10",
        "owner_reply_text": "Terima kasih, Kak! Semoga makin puas ke depannya.",
        "owner_reply_date": "2026-08-01T12:00:00+07:00",
        "reviewer_name_masked": "Fajar A***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-002"},
    },
    {
        "source_review_id": "mgd-0002",
        "rating": 3,
        "review_text": "Rasa oke tapi AC-nya kurang dingin, jadi gerah. Semoga diperbaiki.",
        "review_date": "2026-07-30T14:00:00+07:00",
        "review_datetime_raw": "30 Juli 2026 14.00",
        "owner_reply_text": "Terima kasih masukannya, Kak. Kami sedang service AC cabang Margonda.",
        "owner_reply_date": "2026-07-31T10:00:00+07:00",
        "reviewer_name_masked": "Lia M***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-002"},
    },
    {
        "source_review_id": "mgd-0003",
        "rating": 4,
        "review_text": "Pelayanannya cekatan, bubur datang nggak lama setelah pesan. Enak!",
        "review_date": "2026-07-26T08:20:00+07:00",
        "review_datetime_raw": "26 Juli 2026 08.20",
        "owner_reply_text": None,
        "owner_reply_date": None,
        "reviewer_name_masked": "Rizky D***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-002"},
    },
    {
        "source_review_id": "mgd-0004",
        "rating": 2,
        "review_text": "Dua kali pesan via online selalu kurang lengkap, sambalnya lupa terus.",
        "review_date": "2026-07-22T12:50:00+07:00",
        "review_datetime_raw": "22 Juli 2026 12.50",
        "owner_reply_text": "Mohon maaf, Kak. Kami akan perbaiki pengecekan pesanan sebelum dikirim.",
        "owner_reply_date": "2026-07-22T16:00:00+07:00",
        "reviewer_name_masked": "Nina K***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-002"},
    },
    {
        "source_review_id": "mgd-0005",
        "rating": 5,
        "review_text": "Bubur ayam favorit se-Depok. Kuahnya kental, ayamnya banyak, murah lagi.",
        "review_date": "2026-07-18T07:00:00+07:00",
        "review_datetime_raw": "18 Juli 2026 07.00",
        "owner_reply_text": None,
        "owner_reply_date": None,
        "reviewer_name_masked": "Tono S***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-002"},
    },
    {
        "source_review_id": "mgd-0006",
        "rating": 4,
        "review_text": "",
        "review_date": "2026-07-12T10:30:00+07:00",
        "review_datetime_raw": "12 Juli 2026 10.30",
        "owner_reply_text": None,
        "owner_reply_date": None,
        "reviewer_name_masked": "Anonim",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-002"},
    },
    {
        "source_review_id": "mgd-0007",
        "rating": 1,
        "review_text": "Antre super lama dan pas duduk dapat meja kotor. Manajemennya perlu dievaluasi.",
        "review_date": "2026-07-08T12:15:00+07:00",
        "review_datetime_raw": "8 Juli 2026 12.15",
        "owner_reply_text": "Mohon maaf atas pengalaman yang kurang menyenangkan, Kak.",
        "owner_reply_date": "2026-07-08T14:30:00+07:00",
        "reviewer_name_masked": "Agus W***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-002"},
    },
    {
        "source_review_id": "mgd-0008",
        "rating": 5,
        "review_text": "Sarapan terbaik sebelum kuliah. Cepat, enak, harga mahasiswa banget.",
        "review_date": "2026-06-30T06:50:00+07:00",
        "review_datetime_raw": "30 Juni 2026 06.50",
        "owner_reply_text": "Terima kasih, Kak! Sukses kuliahnya.",
        "owner_reply_date": "2026-06-30T09:00:00+07:00",
        "reviewer_name_masked": "Vina R***",
        "raw_payload": {"place_id": "ChIJ0-depok-margonda-002"},
    },
]

_REVIEWS_BY_PLACE = {
    "ChIJ0-depok-margonda-001": _DEPOK_REVIEWS,
    "ChIJ0-depok-margonda-002": _MARGONDA_REVIEWS,
}


class MockPublicReviewAdapter(PublicReviewSourceAdapter):
    """Deterministic public review fixture adapter (source label: mock)."""

    source_name = "mock"

    def __init__(self, locations: Optional[dict] = None, reviews_by_place: Optional[dict] = None):
        self._locations = locations or MOCK_LOCATIONS
        self._reviews = reviews_by_place or _REVIEWS_BY_PLACE

    def fetch_location(self, place_id: str) -> dict:
        loc = self._locations.get(place_id)
        if loc is None:
            raise ValueError(f"unknown mock place_id: {place_id}")
        return dict(loc)

    def list_reviews_by_place_id(
        self,
        place_id: str,
        since: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> list[dict]:
        if place_id not in self._reviews:
            return []
        items = []
        for r in self._reviews[place_id]:
            review_date = r["review_date"]
            if since and _dt(review_date) < _dt(since):
                continue
            items.append(
                {
                    "source_review_id": r["source_review_id"],
                    "rating": r["rating"],
                    "review_text": r["review_text"],
                    "review_date": review_date,
                    "review_datetime_raw": r["review_datetime_raw"],
                    "owner_reply_text": r.get("owner_reply_text"),
                    "owner_reply_date": r.get("owner_reply_date"),
                    "source": "mock",
                    "source_url": (
                        f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                        f"&review_id={r['source_review_id']}"
                    ),
                    "reviewer_name_masked": r.get("reviewer_name_masked") or "Anonim",
                    "raw_payload": r.get("raw_payload") or {},
                }
            )
        items.sort(key=lambda x: x["review_date"], reverse=True)
        return items[:limit]
