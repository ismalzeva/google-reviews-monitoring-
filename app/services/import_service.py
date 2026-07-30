"""Import service — CSV/XLSX Outscraper file import with validation, mapping, and batch processing."""

import csv
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from app import db
from app.models.entities import ImportBatch, ReviewRawPayload

logger = logging.getLogger(__name__)


# ─── KNOWN OUTSCRAPER COLUMN VARIANTS ──────────────────────────
# Maps target field → list of possible labels in Outscraper exports.
# Used by detect_column_mapping() for fuzzy matching.
_OUTSCRAPER_COLUMN_MAP = {
    'reviewer_display_name': [
        'name', 'reviewer_name', 'reviewer', 'author_name', 'author',
        'reviewer_display_name', 'user_name', 'user',
    ],
    'comment': [
        'review_text', 'text', 'review', 'content', 'review_content',
        'comment', 'review_comment', 'text_content',
    ],
    'star_rating': [
        'review_rating', 'rating', 'star_rating', 'stars', 'score',
        'review_score', 'rate', 'review_star',
    ],
    'create_time': [
        'review_datetime_utc', 'review_datetime', 'review_date',
        'datetime', 'date', 'datetime_utc', 'created_time', 'create_time',
        'review_time', 'time', 'published_at', 'published', 'review_date_time',
    ],
    'owner_answer': [
        'owner_answer', 'owner_reply', 'owner_response', 'reply',
        'business_reply', 'business_response', 'response',
    ],
    'place_id': [
        'place_id', 'google_place_id', 'location_id', 'placeid',
        'place id', 'google place id',
    ],
    'food': [
        'food', 'food_rating', 'food_score',
    ],
    'service': [
        'service', 'service_rating', 'service_score',
    ],
    'atmosphere': [
        'atmosphere', 'atmosphere_rating', 'atmosphere_score',
        'ambiance', 'ambience',
    ],
    'wait_time': [
        'wait_time', 'waiting_time', 'wait', 'queue_time',
        'wait_time_rating',
    ],
    'parking': [
        'parking', 'parking_rating', 'parking_score',
    ],
    'price': [
        'price', 'price_level', 'pricing', 'price_rating',
        'price_category', 'cost',
    ],
    'outlet_name': [
        'outlet', 'outlet_name', 'location_name', 'business_name',
        'store_name', 'store', 'branch', 'branch_name', 'title',
        'google_name', 'business_name',
    ],
}


# ─── PUBLIC API ───────────────────────────────────────────────

def parse_import_file(file_path: str, file_type: str) -> tuple[list[dict], list[str]]:
    """Parse a CSV or XLSX file and return (rows, errors).

    Args:
        file_path: Absolute or relative path to the file.
        file_type: ``'csv'`` or ``'xlsx'``.

    Returns:
        Tuple of (list of dict rows keyed by original header, list of error mesages).
    """
    errors: list[str] = []

    if not os.path.isfile(file_path):
        return [], [f"File not found: {file_path}"]

    if file_type == 'csv':
        return _parse_csv(file_path, errors)
    elif file_type == 'xlsx':
        return _parse_xlsx(file_path, errors)
    else:
        return [], [f"Unsupported file type: {file_type!r} — expected 'csv' or 'xlsx'"]


def detect_column_mapping(headers: list[str]) -> dict:
    """Auto-detect Outscraper export columns from a list of header strings.

    Matching is case-insensitive with substring / prefix matching so typical
    Outscraper variant labels are recognised even when they differ slightly.

    Args:
        headers: Original column header strings from the file.

    Returns:
        Dict mapping ``{target_column: source_column}``.  Only fields that
        matched at least one header appear in the result.
    """
    mapping: dict[str, str] = {}

    for target_field, candidates in _OUTSCRAPER_COLUMN_MAP.items():
        matched = _find_header(headers, candidates)
        if matched:
            mapping[target_field] = matched

    return mapping


def validate_import_row(row: dict, mapping: dict, outlet_map: dict) -> dict:
    """Validate a single parsed row against expected constraints.

    Args:
        row: Raw row dict keyed by original file headers.
        mapping: Column mapping from ``detect_column_mapping()``.
        outlet_map: Dict of ``{place_id: outlet_id}`` (or fallback name lookup).

    Returns:
        Dict with keys:
            - ``valid`` (bool)
            - ``errors`` (list of str)
            - ``warnings`` (list of str)
            - ``normalized`` (dict of validated/normalised values)
    """
    errors: list[str] = []
    warnings: list[str] = []
    normalized: dict = {}

    # --- Helper to read a mapped field ---
    def _val(target_field: str, default=None):
        src = mapping.get(target_field)
        if src and src in row:
            return row[src].strip() if isinstance(row[src], str) else row[src]
        return default

    # --- Place ID & outlet ---
    place_id = str(_val('place_id', '') or '')
    outlet_id = None
    if place_id:
        outlet_id = outlet_map.get(place_id)
    if not outlet_id:
        # Fallback: try outlet name
        name_val = str(_val('outlet_name', '') or '').strip()
        if name_val and name_val in outlet_map:
            outlet_id = outlet_map[name_val]
        elif not place_id:
            errors.append("Missing place_id — cannot determine outlet")

    normalized['place_id'] = place_id if place_id else None
    normalized['outlet_id'] = outlet_id

    # --- Reviewer display name ---
    reviewer = str(_val('reviewer_display_name', '') or '').strip()
    if not reviewer:
        warnings.append("Reviewer name is empty — using 'Anonymous'")
        reviewer = 'Anonymous'
    normalized['reviewer_display_name'] = reviewer

    # --- Star rating (1-5, required) ---
    raw_rating = _val('star_rating')
    if raw_rating is not None:
        try:
            rating = int(float(str(raw_rating)))
            if rating < 1 or rating > 5:
                errors.append(f"Rating {rating} is out of range (must be 1-5)")
                rating = None
        except (ValueError, TypeError):
            errors.append(f"Invalid rating value: {raw_rating!r}")
            rating = None
    else:
        errors.append("Missing rating field")
        rating = None
    normalized['star_rating'] = rating

    # --- Review text ---
    text = str(_val('comment', '') or '').strip()
    normalized['comment'] = text
    normalized['has_text'] = bool(text)

    # --- Creation / review date ---
    raw_date = str(_val('create_time', '') or '').strip()
    parsed_dt = _parse_datetime(raw_date)
    if raw_date and parsed_dt is None:
        warnings.append(f"Could not parse date {raw_date!r} — using current time")
        parsed_dt = datetime.now(timezone.utc)
    elif not raw_date:
        parsed_dt = datetime.now(timezone.utc)
    normalized['create_time'] = parsed_dt

    # --- Owner answer (optional) ---
    owner_answer = str(_val('owner_answer', '') or '').strip()
    normalized['owner_answer'] = owner_answer if owner_answer else None

    # --- Attribute dimensions (optional) ---
    for attr in ('food', 'service', 'atmosphere', 'wait_time', 'parking', 'price'):
        val = _val(attr)
        if val is not None:
            try:
                normalized[attr] = int(float(str(val)))
            except (ValueError, TypeError):
                pass  # silently skip unparseable attribute

    # --- Source review name (dedup key) ---
    ts_hash = _short_hash(f"{parsed_dt.isoformat() if parsed_dt else ''}{text[:80]}")
    normalized['source'] = 'outscraper_import'
    normalized['source_review_name'] = f"outscraper/{place_id or 'unknown'}/{reviewer[:50]}/{ts_hash}"

    # --- Raw payload (everything from the row) ---
    normalized['raw_payload'] = dict(row)

    valid = len(errors) == 0
    return {
        'valid': valid,
        'errors': errors,
        'warnings': warnings,
        'normalized': normalized if valid else None,
    }


def execute_import(
    tenant_id: str,
    business_id: str,
    mapping: dict,
    rows: list[dict],
    outlet_map: dict,
    file_name: str,
    user_id: str,
    upsert_callback=None,
    audit_callback=None,
) -> dict:
    """Execute a full import — parse, validate, upsert, and audit.

    Args:
        tenant_id: Tenant owning this import.
        business_id: Business scope.
        mapping: Column mapping from ``detect_column_mapping()``.
        rows: Parsed rows from ``parse_import_file()``.
        outlet_map: ``{place_id: outlet_id}`` lookup.
        file_name: Original filename (for ImportBatch.file_name).
        user_id: Actor for audit logging.
        upsert_callback: Callable with signature
            ``(tenant_id, business_id, normalized, batch) -> review_obj``.
            When not provided, a stub that returns ``None`` is used (no-op).
        audit_callback: Optional callable with signature
            ``(action, entity_type, entity_id, after, reason, tenant_id, actor_id)``.
            When not provided, audit is skipped.

    Returns:
        Dict with ``batch_id``, ``status``, ``counts``, ``errors``.
    """
    started_at = datetime.now(timezone.utc)
    batch_id = str(uuid.uuid4())

    # Determine source label from file extension
    ext = os.path.splitext(file_name or '')[1].lower().lstrip('.')
    source_label = f"outscraper_{ext}" if ext in ('csv', 'xlsx') else 'outscraper_import'

    # Prepare counts
    rows_total = len(rows)
    rows_valid = 0
    rows_invalid = 0
    duplicates = 0
    all_errors: list[dict] = []

    # Create batch record
    batch = ImportBatch(
        id=batch_id,
        tenant_id=tenant_id,
        business_id=business_id,
        source=source_label,
        file_name=file_name,
        status='processing',
        started_at=started_at,
    )
    db.session.add(batch)
    db.session.flush()  # get batch.id on the model

    # Set up a default no-op callback so callers don't have to guard
    _upsert = upsert_callback or (lambda *a, **kw: None)
    _audit = audit_callback

    # Process rows
    for idx, row in enumerate(rows):
        validation = validate_import_row(row, mapping, outlet_map)

        if not validation['valid']:
            rows_invalid += 1
            all_errors.append({
                'row': idx + 2,  # 1-indexed + header row
                'errors': validation['errors'],
                'warnings': validation.get('warnings', []),
                'raw': _truncate_payload(row),
            })
            continue

        normalized = validation['normalized']

        # Call upsert callback
        try:
            review_obj = _upsert(
                tenant_id=tenant_id,
                business_id=business_id,
                normalized=normalized,
                batch_id=batch_id,
            )
        except Exception as exc:
            logger.exception("Upsert failed at row %d", idx + 2)
            rows_invalid += 1
            all_errors.append({
                'row': idx + 2,
                'errors': [str(exc)],
                'warnings': [],
                'raw': _truncate_payload(row),
            })
            continue

        if review_obj is None:
            # Callback returned None → duplicate / no-op
            duplicates += 1
            continue

        rows_valid += 1

        # Save raw payload
        _save_raw_payload(
            tenant_id=tenant_id,
            business_id=business_id,
            review_obj=review_obj,
            normalized=normalized,
            batch_id=batch_id,
        )

        # Audit
        if _audit:
            try:
                _audit(
                    action='review.imported',
                    entity_type='review',
                    entity_id=review_obj.id,
                    after={'source': 'outscraper_import', 'row': idx + 2},
                    reason=f"Imported via {file_name}",
                    tenant_id=tenant_id,
                    actor_id=user_id,
                )
            except Exception:
                logger.warning("Audit log failed for row %d (non-fatal)", idx + 2)

    # Finalize batch
    completed_at = datetime.now(timezone.utc)
    batch.status = 'completed'
    batch.completed_at = completed_at
    batch.rows_total = rows_total
    batch.rows_valid = rows_valid
    batch.rows_invalid = rows_invalid
    batch.duplicates = duplicates
    batch.error_report_ref = json.dumps(all_errors) if all_errors else None

    db.session.commit()

    return {
        'batch_id': batch_id,
        'status': 'completed',
        'counts': {
            'total': rows_total,
            'valid': rows_valid,
            'invalid': rows_invalid,
            'duplicates': duplicates,
        },
        'errors': all_errors,
    }


def preview_import(file_path: str, file_type: str) -> dict:
    """Parse a file and offer a preview (no database writes).

    Args:
        file_path: Absolute or relative path to the file.
        file_type: ``'csv'`` or ``'xlsx'``.

    Returns:
        Dict with ``headers``, ``sample_rows`` (up to 5), ``detected_mapping``,
        ``total_rows``, and ``errors``.
    """
    rows, errors = parse_import_file(file_path, file_type)
    if errors:
        return {
            'headers': [],
            'sample_rows': [],
            'detected_mapping': {},
            'total_rows': 0,
            'errors': errors,
        }

    headers = list(rows[0].keys()) if rows else []
    mapping = detect_column_mapping(headers)

    return {
        'headers': headers,
        'sample_rows': rows[:5],
        'detected_mapping': mapping,
        'total_rows': len(rows),
        'errors': [],
    }


# ─── INTERNALS ────────────────────────────────────────────────

def _parse_csv(file_path: str, errors: list[str]) -> tuple[list[dict], list[str]]:
    """Parse a UTF-8 CSV file with csv.DictReader."""
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = [row for row in reader]
            if not rows:
                errors.append("CSV file is empty or has no data rows")
            # Strip whitespace from keys and values; skip fully empty rows
            cleaned = []
            for r in rows:
                stripped = {k.strip(): (v.strip() if isinstance(v, str) else v)
                            for k, v in r.items()}
                # Skip rows where every value is empty/None
                if all(v is None or (isinstance(v, str) and v == '')
                       for v in stripped.values()):
                    continue
                cleaned.append(stripped)
            return cleaned, errors
    except Exception as exc:
        errors.append(f"CSV read error: {exc}")
        return [], errors


def _parse_xlsx(file_path: str, errors: list[str]) -> tuple[list[dict], list[str]]:
    """Parse an XLSX file with openpyxl."""
    try:
        import openpyxl
    except ImportError:
        errors.append("openpyxl is not installed — install with 'pip install openpyxl'")
        return [], errors

    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            errors.append("XLSX file has no active sheet")
            return [], errors

        rows_iter = ws.iter_rows(values_only=True)
        try:
            raw_headers = next(rows_iter)
        except StopIteration:
            errors.append("XLSX file is empty (no header row)")
            return [], errors

        if not raw_headers:
            errors.append("Header row is empty")
            return [], errors

        headers = [str(h).strip() if h is not None else f'unnamed_col_{i}'
                    for i, h in enumerate(raw_headers)]

        result: list[dict] = []
        for row_values in rows_iter:
            if all(v is None for v in row_values):
                continue  # skip completely empty rows
            row_dict = {}
            for i, val in enumerate(row_values):
                key = headers[i] if i < len(headers) else f'extra_col_{i}'
                if isinstance(val, str):
                    val = val.strip()
                row_dict[key] = val
            result.append(row_dict)

        wb.close()
        return result, errors
    except Exception as exc:
        errors.append(f"XLSX read error: {exc}")
        return [], errors


def _find_header(headers: list[str], candidates: list[str]) -> str | None:
    """Return the first header that matches any candidate (case-insensitive).

    Priority:
        1. Exact match (after normalising whitespace and underscores).
        2. Candidate is a substring of the header (e.g. ``'wait_time'``
           matches header ``'review_wait_time'``).
        3. Header is a substring of the candidate **only** when the header
           itself is a multi-word phrase (contains a separator), to avoid
           short words like ``'Rating'`` falsely matching candidates like
           ``'wait_time_rating'``.
    """
    for candidate in candidates:
        c_lower = candidate.lower().replace(' ', '_')
        for header in headers:
            h_lower = header.strip().lower().replace(' ', '_')
            if h_lower == c_lower:
                return header
            # Candidate is a substring of header (e.g. 'rating' in 'review_rating')
            if c_lower in h_lower:
                return header
            # Header is a substring of candidate — only if header looks like a
            # multi-word phrase (has underscore), so single tokens like 'Rating'
            # don't match every '*_rating' candidate.
            if '_' in h_lower and h_lower in c_lower:
                return header
    return None


def _parse_datetime(raw: str) -> datetime | None:
    """Try common date/time formats and return a UTC-aware datetime or None."""
    if not raw:
        return None

    # Remove common suffixes (UTC, Z, etc.)
    cleaned = raw.strip().replace('UTC', '').strip()

    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%d',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y',
        '%m/%d/%Y %H:%M:%S',
        '%m/%d/%Y',
        '%d-%m-%Y %H:%M:%S',
        '%d-%m-%Y',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    return None


def _short_hash(value: str) -> str:
    """Return the first 12 hex chars of a SHA-256 hash."""
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]


def _truncate_payload(row: dict, max_len: int = 200) -> dict:
    """Truncate string values in a row to *max_len* chars for error reports."""
    truncated = {}
    for k, v in row.items():
        if isinstance(v, str) and len(v) > max_len:
            truncated[k] = v[:max_len] + '...'
        else:
            truncated[k] = v
    return truncated


def _save_raw_payload(tenant_id: str, business_id: str, review_obj, normalized: dict, batch_id: str):
    """Persist a ``ReviewRawPayload`` row for the imported review."""
    raw_json = normalized.get('raw_payload', {})
    payload_hash = hashlib.sha256(
        json.dumps(raw_json, sort_keys=True, default=str).encode('utf-8')
    ).hexdigest()

    payload = ReviewRawPayload(
        tenant_id=tenant_id,
        business_id=business_id,
        review_pk=review_obj.id,
        source='outscraper_import',
        source_account_id=normalized.get('place_id') or '',
        source_location_id=normalized.get('outlet_id') or '',
        source_review_name=normalized.get('source_review_name', ''),
        raw_payload_hash=payload_hash,
        raw_payload=raw_json,
        import_batch_id=batch_id,
    )
    db.session.add(payload)
