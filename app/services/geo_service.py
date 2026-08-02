"""Geographic enrichment service.

Resolves latitude/longitude pairs into structured Indonesian administrative
areas (province, city/regency, district) using OpenStreetMap Nominatim.

Contract (GRM_PUBLIC_MONITORING_SKILL §6.1):
- If a region cannot be determined with confidence, store as ``unknown`` and
  flag ``needs_geographic_resolution`` — never invent values.
- ``city_regency`` distinguishes Kota vs Kabupaten; never conflate with
  ``district`` (kecamatan).
"""
import logging

import requests

from app import db

logger = logging.getLogger(__name__)

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
DEFAULT_TIMEOUT = 10
USER_AGENT = "GRM-Public-Monitoring/1.0 (review analytics; contact: ismalzeva@gmail.com)"


def reverse_geocode(lat: float, lon: float, timeout: int = DEFAULT_TIMEOUT):
    """Reverse geocode a coordinate pair via OSM Nominatim.

    Returns a tuple ``(province, city_regency, district)``. Values may be
    ``None`` when Nominatim cannot determine them.
    """
    if lat is None or lon is None:
        return None, None, None
    try:
        resp = requests.get(
            NOMINATIM_REVERSE_URL,
            params={
                "format": "jsonv2",
                "lat": lat,
                "lon": lon,
                "zoom": 16,
                "addressdetails": 1,
                "accept-language": "id",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        addr = resp.json().get("address", {}) or {}
    except Exception as exc:  # network, timeout, parse — fail safely
        logger.warning("Nominatim reverse geocode failed for (%s, %s): %s", lat, lon, exc)
        return None, None, None

    province = addr.get("state")

    city = addr.get("city")
    county = addr.get("county")
    if city and ("Kota" in city or "Kabupaten" in city):
        city_regency = city
    elif county:
        city_regency = county
    else:
        city_regency = city

    district = (
        addr.get("town")
        or addr.get("village")
        or addr.get("suburb")
        or addr.get("municipality")
    )
    return province, city_regency, district


def enrich_location(obj, commit: bool = True) -> bool:
    """Populate geographic fields on an Outlet or LocationCandidate.

    Sets ``province``, ``city_regency``, ``district``, and
    ``needs_geographic_resolution``. Returns True when all three areas were
    resolved; False otherwise (unknown + flag set).
    """
    if not hasattr(obj, "latitude") or not hasattr(obj, "longitude"):
        return False

    province, city_regency, district = reverse_geocode(obj.latitude, obj.longitude)

    # Never overwrite already-resolved values (e.g. provider-supplied city).
    if not obj.province:
        obj.province = province or "unknown"
    if not obj.city_regency:
        obj.city_regency = city_regency or "unknown"
    if not obj.district:
        obj.district = district or "unknown"
    resolved = bool(
        obj.province != "unknown"
        and obj.city_regency != "unknown"
        and obj.district != "unknown"
    )
    obj.needs_geographic_resolution = not resolved
    if commit:
        db.session.commit()
    return resolved
