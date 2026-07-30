"""Review Source Adapter — unified interface for multiple review sources."""

import hashlib
import json
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _utc_now():
    return datetime.now(timezone.utc)


def _review_name(account_id, location_id, review_id):
    return f"accounts/{account_id}/locations/{location_id}/reviews/{review_id}"


# ─── BASE ADAPTER ──────────────────────────────────────────


class ReviewSourceAdapter(ABC):
    """Interface all review-source adapters must implement."""

    @abstractmethod
    def list_reviews(
        self,
        business_id: str = None,
        location_id: str = None,
        page_token: str = None,
        page_size: int = 10,
        order_by: str = None,
    ) -> dict:
        """Fetch a page of reviews for a location.
        Returns dict: {reviews: [...], next_page_token: str|None, total_count: int}
        """

    @abstractmethod
    def get_review(self, business_id: str, location_id: str, review_name: str) -> Optional[dict]:
        """Fetch a single review by its resource name."""

    @abstractmethod
    def health_check(self) -> dict:
        """Return adapter health status."""


# ─── MOCK ADAPTER — Bubur Fay Dataset ────────────────────


class MockReviewAdapter(ReviewSourceAdapter):
    """Produces mock review data for Bubur Fay outlets."""

    ACCOUNT_ID = "103821598699130971129"
    LOCATION_DEPOK = "locations/123456789001"
    LOCATION_MARGONDA = "locations/123456789002"
    LOCATION_BEKASI = "locations/123456789003"
    LOCATION_FAIL = "locations/999999999999"

    # ── review templates ──────────────────────────────────
    POSITIVE_REVIEWS = [
        {"reviewer": "Budi Santoso", "rating": 5, "text": "Buburnya enak banget, porsinya juga besar. Suka banget sama topping ayamnya yang gurih. Pasti balik lagi!",
         "created_days": 120, "owner_reply": "Terima kasih, Kak Budi! Senang mendengar Anda suka."},
        {"reviewer": "Sari Dewi", "rating": 5, "text": "Pertama kali coba bubur ayam di sini, nagih! Kentalnya pas, bumbunya meresap. Recommended!",
         "created_days": 90, "owner_reply": "Makasih, Kak Sari! Silakan datang lagi ya."},
        {"reviewer": "Ahmad Fauzi", "rating": 4, "text": "Enak, tempatnya bersih, harganya terjangkau. Pelayanan ramah. Cuma agak ramai pas jam makan siang.",
         "created_days": 60, "owner_reply": None},
        {"reviewer": "Rina Marlina", "rating": 5, "text": "Buburnya lembut, kaldunya terasa. Topping melimpah. Anak saya suka banget!",
         "created_days": 45, "owner_reply": "Alhamdulillah, senang mendengarnya! Terima kasih, Kak Rina."},
        {"reviewer": "Dwi Prasetyo", "rating": 5, "text": "Sudah langganan 2 tahun. Rasanya konsisten enak. Bubur ayam kampung favorit saya.",
         "created_days": 30, "owner_reply": "Terima kasih atas kesetiaannya, Kak Dwi! Kami akan terus menjaga kualitas."},
        {"reviewer": "Fitri Handayani", "rating": 4, "text": "Enak banget buburnya! Cuma sayang tempat parkirnya agak sempit. Tapi overall worth it.",
         "created_days": 20, "owner_reply": None},
        {"reviewer": "Hendra Gunawan", "rating": 5, "text": "Pelayanan cepat, bubur hangat, pas untuk sarapan sebelum kerja. Top markotop!",
         "created_days": 15, "owner_reply": "Terima kasih, Kak Hendra! Selamat beraktivitas."},
        {"reviewer": "Lestari Ningsih", "rating": 4, "text": "Rasa enak, pilihan topping banyak. Ada sambal yang pedasnya pas. Recommended buat sarapan.",
         "created_days": 10, "owner_reply": None},
    ]

    NEGATIVE_REVIEWS = [
        {"reviewer": "Tono Wijaya", "rating": 1, "text": "Lama banget nunggunya! 45 menit untuk semangkok bubur? Gak masuk akal. Manajemen antriannya harus diperbaiki.",
         "created_days": 80, "owner_reply": "Mohon maaf atas pengalaman kurang menyenangkannya, Kak Tono. Kami akan evaluasi sistem antrian."},
        {"reviewer": "Maya Anggraini", "rating": 2, "text": "Buburnya dingin pas disajikan, topping ayamnya sedikit. Kayaknya lagi gak mood masaknya hari ini.",
         "created_days": 50, "owner_reply": "Kami mohon maaf, Kak Maya. Akan kami sampaikan ke tim dapur."},
        {"reviewer": "Agus Salim", "rating": 1, "text": "Mahal untuk ukuran bubur. Porsi makin kecil tapi harga naik. Dulu lebih enak.",
         "created_days": 35, "owner_reply": None},
        {"reviewer": "Putri Wulandari", "rating": 2, "text": "Kotornya minta ampun. Meja lengket, lantai banyak tisu bekas. Toilet juga jorok. Gak bakal balik.",
         "created_days": 25, "owner_reply": "Kami mohon maaf sebesar-besarnya, Kak Putri. Akan segera kami benahi kebersihan."},
        {"reviewer": "Rudi Hartono", "rating": 1, "text": "Pesen delivery, salah terus. Udah 2 kali order gak sesuai. Bungkusnya juga bocor.",
         "created_days": 15, "owner_reply": None},
    ]

    MIXED_REVIEWS = [
        {"reviewer": "Indah Permata", "rating": 3, "text": "Buburnya enak sih, tapi pelayanannya lambat banget. Dapurnya kelihatan kotor dari luar.",
         "created_days": 70, "owner_reply": "Terima kasih masukannya, Kak Indah. Akan kami perbaiki."},
        {"reviewer": "Bayu Pratama", "rating": 3, "text": "Rasa standar, harga standar. Gak ada yang spesial tapi juga gak mengecewakan. Biasa aja.",
         "created_days": 40, "owner_reply": None},
    ]

    RATING_ONLY = [
        {"reviewer": "Anonim123", "rating": 1, "created_days": 55},
        {"reviewer": "User789", "rating": 5, "created_days": 28},
    ]

    UPDATED_REVIEW = {
        "reviewer": "Dian Kurniawan",
        "rating": 4,
        "text": "Awalnya kurang puas karena lama, tapi setelah dikasih kesempatan kedua pelayanannya membaik. Buburnya tetap enak.",
        "original_rating": 2,
        "original_text": "Lama banget nunggunya, buburnya juga biasa aja. Kecewa.",
        "created_days": 100,
        "updated_days": 45,
        "owner_reply": "Terima kasih sudah memberi kesempatan kedua, Kak Dian! Kami senang bisa memperbaiki pelayanan."
    }

    NO_REPLY_REVIEWS = [
        {"reviewer": "Nina Zahra", "rating": 4, "text": "Buburnya enak, tempatnya cozy. Cocok buat nongkrong santai sambil sarapan.",
         "created_days": 12},
        {"reviewer": "Fajar Ramadhan", "rating": 5, "text": "Mantap! Porsi jumbo, harga bersahabat. Langganan tiap minggu.",
         "created_days": 5},
    ]

    @property
    def _all_depok_reviews(self):
        """Generate the full list of reviews for Depok location."""
        return self._build_reviews("123456789001", "dep",
            positives=True, negatives=True, mixed=True,
            rating_only=True, updated=True, no_reply=True)

    @property
    def _all_margonda_reviews(self):
        """Generate reviews for Margonda location (fewer, unique names)."""
        return self._build_reviews("123456789002", "mgr",
            positives=False, negatives=False, mixed=False,
            rating_only=False, updated=False, no_reply=False,
            custom_reviews=[
                {"reviewer": "Rina Marlina", "rating": 5, "text": "Buburnya creamy, topping melimpah.", "created_days": 10},
                {"reviewer": "Dimas Arya", "rating": 4, "text": "Cocok sama lidah. Recommended.", "created_days": 20},
                {"reviewer": "Sari Dewi", "rating": 3, "text": "Biasa aja, tapi tempatnya bersih.", "created_days": 30},
                {"reviewer": "Bambang S.", "rating": 1, "text": "Mahal! Porsi dikit.", "created_days": 60},
                {"reviewer": "Fitriani", "rating": 5, "text": "Udah langganan tiap minggu.", "created_days": 5},
                {"reviewer": "Adi Pratama", "rating": 2, "text": "Lama banget pesennya.", "created_days": 25},
                {"reviewer": "Nurul H.", "rating": 4, "text": "Enak dan murah.", "created_days": 15},
                {"reviewer": "Fajar Sidiq", "rating": 1, "text": "Rasanya aneh. Gak layak.", "created_days": 45},
            ])

    def _build_reviews(self, loc_id, prefix, positives=False, negatives=False,
                       mixed=False, rating_only=False, updated=False, no_reply=False,
                       custom_reviews=None):
        """Build review dicts for a location with selected review types."""
        import datetime as dt
        reviews = []
        base = _utc_now()
        idx = [0]

        def _add(rating, text, days, reviewer):
            idx[0] += 1
            ct = base - dt.timedelta(days=days)
            reviews.append({
                "review_name": _review_name(self.ACCOUNT_ID, loc_id, f"{prefix}_{idx[0]:03d}"),
                "reviewer_display_name": reviewer,
                "star_rating": rating,
                "comment": text,
                "create_time": ct.isoformat(),
                "update_time": ct.isoformat(),
            })

        if positives:
            for r in self.POSITIVE_REVIEWS:
                _add(r["rating"], r["text"], r["created_days"], r["reviewer"])

        if negatives:
            for r in self.NEGATIVE_REVIEWS:
                _add(r["rating"], r["text"], r["created_days"], r["reviewer"])

        if mixed:
            for r in self.MIXED_REVIEWS:
                _add(r["rating"], r["text"], r["created_days"], r["reviewer"])

        if rating_only:
            for r in self.RATING_ONLY:
                _add(r["rating"], None, r["created_days"], r["reviewer"])

        if updated:
            r = self.UPDATED_REVIEW
            ct = base - dt.timedelta(days=r["created_days"])
            ut = base - dt.timedelta(days=r["updated_days"])
            idx[0] += 1
            reviews.append({
                "review_name": _review_name(self.ACCOUNT_ID, loc_id, f"{prefix}_{idx[0]:03d}"),
                "reviewer_display_name": r["reviewer"],
                "star_rating": r["rating"],
                "comment": r["text"],
                "create_time": ct.isoformat(),
                "update_time": ut.isoformat(),
                "_original_rating": r["original_rating"],
                "_original_comment": r["original_text"],
            })

        if no_reply:
            for r in self.NO_REPLY_REVIEWS:
                _add(r["rating"], r["text"], r["created_days"], r["reviewer"])

        if custom_reviews:
            for r in custom_reviews:
                _add(r["rating"], r["text"], r["created_days"], r["reviewer"])

        return reviews

    def _make_reviews(self, location_suffix, review_data_list, all_positives=False):
        """Legacy helper."""
        return []

    @property
    def _all_depok_reviews_old(self):
        return []

    def list_reviews(
        self,
        business_id=None,
        location_id=None,
        page_token=None,
        page_size=10,
        order_by=None,
    ):
        # Detect failed outlet
        if location_id == self.LOCATION_FAIL:
            return {
                "reviews": [],
                "next_page_token": None,
                "total_count": 0,
                "error": "Simulated sync failure for this location"
            }

        if location_id == self.LOCATION_DEPOK:
            all_reviews = self._all_depok_reviews
        elif location_id == self.LOCATION_MARGONDA:
            all_reviews = self._all_margonda_reviews
        else:
            all_reviews = []

        # Pagination
        start_idx = int(page_token) if page_token else 0
        end_idx = start_idx + page_size
        page = all_reviews[start_idx:end_idx]
        next_token = str(end_idx) if end_idx < len(all_reviews) else None

        # Clean internal fields
        result = []
        for r in page:
            clean = {k: v for k, v in r.items() if not k.startswith("_")}
            result.append(clean)

        return {
            "reviews": result,
            "next_page_token": next_token,
            "total_count": len(all_reviews),
        }

    def get_review(self, business_id=None, location_id=None, review_name=None):
        """Find a single review by review_name."""
        all_reviews = self._all_depok_reviews
        for r in all_reviews:
            if r["review_name"] == review_name:
                return {k: v for k, v in r.items() if not k.startswith("_")}
        return None

    def health_check(self):
        return {
            "adapter_name": "MockReviewAdapter",
            "status": "ok",
            "mode": "mock",
            "production_api_connected": False,
            "reply_enabled": False,
            "blocking_reason": "Mock adapter — no real Google API connection",
            "review_count": len(self._all_depok_reviews),
        }


# ─── OUTSCRAPER IMPORT ADAPTER ──────────────────────────


class OutscraperImportAdapter(ReviewSourceAdapter):
    """Parses Outscraper CSV/XLSX exports. Not a live-fetch adapter."""

    KNOWN_COLUMNS = {
        "name": ["name", "reviewer", "reviewer_name", "author", "user_name", "username"],
        "review_text": ["review_text", "review", "text", "comment", "content", "review_comment", "description", "body"],
        "review_rating": ["review_rating", "rating", "star_rating", "stars", "score", "review_star", "rate"],
        "review_datetime_utc": ["review_datetime_utc", "review_datetime", "datetime_utc",
                                "datetime", "date", "time", "date_time", "review_date", "created_at", "create_time", "date_utc", "timestamp"],
        "owner_answer": ["owner_answer", "owner_reply", "reply", "response", "owner_comment", "store_answer", "manager_reply"],
        "food": ["food", "food_rating"],
        "service": ["service", "service_rating"],
        "atmosphere": ["atmosphere", "ambience", "environment"],
        "wait_time": ["wait_time", "waiting_time"],
        "parking": ["parking", "parking_rating"],
        "price": ["price", "price_level"],
        "place_id": ["place_id", "placeid", "google_place_id", "location_id", "place"],
    }

    def list_reviews(self, **kwargs):
        raise NotImplementedError("OutscraperImportAdapter does not support live listing")

    def get_review(self, **kwargs):
        raise NotImplementedError("OutscraperImportAdapter does not support single fetch")

    def health_check(self):
        return {
            "adapter_name": "OutscraperImportAdapter",
            "status": "ok",
            "mode": "import",
            "production_api_connected": False,
            "reply_enabled": False,
            "blocking_reason": "Import-only adapter — no live API connection",
        }

    def parse_file(self, file_path: str) -> tuple:
        """Parse CSV or XLSX file. Returns (rows: list[dict], errors: list[str])."""
        import csv
        import os

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            return self._parse_csv(file_path)
        elif ext in (".xlsx", ".xls"):
            return self._parse_xlsx(file_path)
        else:
            return [], [f"Unsupported file type: {ext}"]

    def _parse_csv(self, file_path):
        rows = []
        errors = []
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    clean = {k.strip(): v.strip() if v else "" for k, v in row.items()}
                    rows.append(clean)
        except Exception as e:
            errors.append(f"CSV parse error: {str(e)}")
        return rows, errors

    def _parse_xlsx(self, file_path):
        rows = []
        errors = []
        try:
            from openpyxl import load_workbook
            wb = load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            header_row = [cell.value.strip() if cell.value else "" for cell in ws[1]]
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                row_dict = {}
                for col_idx, val in enumerate(row):
                    if col_idx < len(header_row) and header_row[col_idx]:
                        row_dict[header_row[col_idx]] = str(val) if val is not None else ""
                if any(v.strip() for v in row_dict.values()):
                    rows.append(row_dict)
        except Exception as e:
            errors.append(f"XLSX parse error: {str(e)}")
        return rows, errors

    def detect_columns(self, headers: list) -> dict:
        """Auto-detect column mapping from Outscraper export headers."""
        mapping = {}
        for target, aliases in self.KNOWN_COLUMNS.items():
            for header in headers:
                h = header.strip().lower()
                if h in [a.lower() for a in aliases]:
                    mapping[target] = header
                    break
        return mapping

    def validate_row(self, row: dict, mapping: dict, outlet_map: dict = None) -> dict:
        """Validate a single imported row. Returns dict with valid, errors, warnings, normalized."""
        errors = []
        warnings = []
        normalized = {}

        # Rating
        rating_raw = row.get(mapping.get("review_rating", ""), "")
        try:
            rating = int(float(rating_raw))
            if rating < 1 or rating > 5:
                errors.append(f"Invalid rating {rating}: must be 1-5")
                rating = None
        except (ValueError, TypeError):
            errors.append(f"Invalid rating value: '{rating_raw}'")
            rating = None

        normalized["star_rating"] = rating

        # Reviewer
        name = row.get(mapping.get("name", ""), "").strip()
        normalized["reviewer_display_name"] = name or "Unknown"

        # Comment
        comment = row.get(mapping.get("review_text", ""), "").strip()
        normalized["comment"] = comment if comment else None
        normalized["has_text"] = bool(comment)

        # Date
        date_raw = row.get(mapping.get("review_datetime_utc", ""), "").strip()
        if date_raw:
            try:
                from dateutil import parser as dateparser
                parsed = dateparser.parse(date_raw)
                if parsed.tzinfo is None:
                    from datetime import timezone
                    parsed = parsed.replace(tzinfo=timezone.utc)
                normalized["create_time"] = parsed.isoformat()
                normalized["update_time"] = parsed.isoformat()
            except Exception:
                warnings.append(f"Could not parse date '{date_raw}', using current time")
                now = _utc_now()
                normalized["create_time"] = now.isoformat()
                normalized["update_time"] = now.isoformat()
        else:
            now = _utc_now()
            normalized["create_time"] = now.isoformat()
            normalized["update_time"] = now.isoformat()
            warnings.append("No date found, using current time")

        # Owner reply
        owner_answer = row.get(mapping.get("owner_answer", ""), "").strip()
        normalized["owner_reply"] = owner_answer if owner_answer else None

        # Place ID mapping
        place_id = row.get(mapping.get("place_id", ""), "").strip()
        normalized["place_id"] = place_id

        # Outlet mapping
        normalized["outlet_id"] = None
        if outlet_map and place_id:
            if place_id in outlet_map:
                normalized["outlet_id"] = outlet_map[place_id]
            elif name in outlet_map:
                normalized["outlet_id"] = outlet_map[name]

        if normalized["outlet_id"] is None:
            errors.append(f"No outlet mapping for place_id='{place_id}' or reviewer='{name}'")

        # Extra fields
        for field in ("food", "service", "atmosphere", "wait_time", "parking", "price"):
            val = row.get(mapping.get(field, ""), "").strip()
            if val:
                normalized[field] = val

        # Generate source_review_name
        import hashlib
        id_str = f"outscraper/{place_id or 'unknown'}/{name}/{utc_now().isoformat()}"
        source_review_name = f"outscraper_import/{hashlib.md5(id_str.encode()).hexdigest()[:16]}"
        normalized["source_review_name"] = source_review_name
        normalized["source"] = "outscraper_import"

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "normalized": normalized,
        }


# ─── GOOGLE BUSINESS PROFILE ADAPTER (SKELETON) ────────


class GoogleBusinessProfileReviewAdapter(ReviewSourceAdapter):
    """Production adapter for Google Business Profile API v4.

    Uses the google_business_profile HTTP client for real API calls.
    Falls back to mock on credential/token errors and provides clear
    error messages for each blocking condition.
    """

    def __init__(self, connection=None, access_token=None, business_id=None, tenant_id=None):
        self._connection = connection
        self._access_token = access_token
        self._business_id = business_id
        self._tenant_id = tenant_id
        self._blocking_reasons = [
            "Google OAuth credentials not configured",
            "Business Profile API not enabled in Google Cloud Console",
            "OAuth consent screen not approved",
            "No Google Business Profile API access token available",
        ]

    def _get_access_token(self):
        if self._access_token:
            return self._access_token
        if not self._connection:
            raise ValueError("No connection and no access token provided")
        from app.services.google_oauth import _get_access_token as _g
        return _g(self._connection)

    def _get_base_url(self):
        from flask import current_app
        return current_app.config.get(
            'GBP_API_BASE_URL',
            'https://businessprofile.googleapis.com/v1',
        )

    def list_reviews(self, business_id=None, location_id=None, page_token=None,
                     page_size=10, order_by=None):
        """Fetch reviews from Google Business Profile API."""
        from app.services.google_business_profile import (
            list_reviews_production,
            TokenExpiredError, PermissionDeniedError, GBPHttpError,
        )

        if not location_id:
            raise ValueError("location_id is required")

        access_token = self._get_access_token()
        base_url = self._get_base_url()

        try:
            result = list_reviews_production(
                access_token, location_id, base_url,
                page_size=page_size, page_token=page_token,
                order_by=order_by or 'update_time desc',
            )
            return result
        except TokenExpiredError:
            logger.warning("Token expired during list_reviews, attempting refresh...")
            # Caller's _get_access_token handles refresh
            raise
        except PermissionDeniedError:
            logger.error("Permission denied for GBP review listing")
            raise
        except GBPHttpError:
            logger.exception("GBP HTTP error during review listing")
            raise

    def get_review(self, business_id=None, location_id=None, review_name=None):
        """Fetch a single review by resource name."""
        from app.services.google_business_profile import (
            get_review_production,
            TokenExpiredError, PermissionDeniedError, GBPHttpError,
        )

        if not review_name:
            raise ValueError("review_name is required")

        access_token = self._get_access_token()
        base_url = self._get_base_url()

        try:
            return get_review_production(access_token, review_name, base_url)
        except TokenExpiredError:
            raise
        except PermissionDeniedError:
            raise
        except GBPHttpError:
            logger.exception("GBP HTTP error during get_review")
            raise

    def create_reply(self, review_name, reply_text):
        """Post a reply to a review on GBP."""
        from app.services.google_business_profile import (
            create_reply_production,
            TokenExpiredError, PermissionDeniedError, GBPHttpError,
        )
        if not review_name:
            raise ValueError("review_name is required")
        access_token = self._get_access_token()
        base_url = self._get_base_url()
        try:
            return create_reply_production(access_token, review_name, reply_text, base_url)
        except TokenExpiredError:
            raise
        except PermissionDeniedError:
            raise
        except GBPHttpError:
            logger.exception("GBP HTTP error during create_reply")
            raise

    def update_reply(self, review_name, reply_text):
        """Update an existing reply on GBP."""
        from app.services.google_business_profile import (
            update_reply_production,
            TokenExpiredError, PermissionDeniedError, GBPHttpError,
        )
        if not review_name:
            raise ValueError("review_name is required")
        access_token = self._get_access_token()
        base_url = self._get_base_url()
        try:
            return update_reply_production(access_token, review_name, reply_text, base_url)
        except TokenExpiredError:
            raise
        except PermissionDeniedError:
            raise
        except GBPHttpError:
            logger.exception("GBP HTTP error during update_reply")
            raise

    def health_check(self):
        """Return adapter health with production status info."""
        from app.services.google_oauth import _is_using_real_api
        from app.services.feature_flags import is_auto_reply_enabled, is_reply_enabled_globally

        is_production = _is_using_real_api()
        token_available = self._access_token is not None
        connected = self._connection is not None

        blocking = list(self._blocking_reasons)
        if is_production:
            blocking = []
            if not token_available and not connected:
                blocking.append("No access token and no connection provided")
            if not is_production:
                blocking.append("OAuth credentials not set in environment")

        return {
            "adapter_name": "GoogleBusinessProfileReviewAdapter",
            "status": "available" if is_production and token_available else "unavailable",
            "mode": "production" if is_production else "mock_fallback",
            "production_api_connected": is_production and token_available,
            "review_endpoint_accessible": is_production and token_available,
            "reply_enabled": is_reply_enabled_globally(),
            "auto_reply_enabled": is_auto_reply_enabled(),
            "blocking_reason": "; ".join(blocking) if blocking else None,
            "credentials_configured": is_production,
        }

    def __repr__(self):
        return f"<GoogleBusinessProfileReviewAdapter production={self._access_token is not None}>"


# ─── ADAPTER RESOLVER ──────────────────────────────────


def get_adapter(source: str, connection=None) -> ReviewSourceAdapter:
    """Resolve adapter by source name and optional connection config."""
    if source == "mock":
        return MockReviewAdapter()
    elif source == "outscraper_import":
        return OutscraperImportAdapter()
    elif source == "google_api" or source == "google_business_profile":
        access_token = None
        business_id = None
        tenant_id = None
        if connection:
            business_id = getattr(connection, 'business_id', None)
            tenant_id = getattr(connection, 'tenant_id', None)
        return GoogleBusinessProfileReviewAdapter(
            connection=connection,
            access_token=access_token,
            business_id=business_id,
            tenant_id=tenant_id,
        )
    else:
        logger.warning("Unknown source '%s', falling back to MockReviewAdapter", source)
        return MockReviewAdapter()
