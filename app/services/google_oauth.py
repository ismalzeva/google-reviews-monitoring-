"""Google OAuth service — handles OAuth 2.0 flow, account discovery,
official location retrieval, and candidate reconciliation.

Since Google API production approval may not be available, this module
provides a mock adapter for development/testing with a clean interface
for swapping in the real HTTP implementation later.
"""

import json
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from flask import current_app
from app.models.entities import (
    db, GoogleConnection, OAuthState,
    LocationCandidate, Outlet,
)
from app.services.encryption import encrypt_token, decrypt_token, reset_cache
from app.services.audit import log_audit

# ─── Status Constants ───────────────────────────────────
STATUS_NOT_CONNECTED = 'not_connected'
STATUS_OAUTH_IN_PROGRESS = 'oauth_in_progress'
STATUS_MOCK_CONNECTED = 'mock_connected'
STATUS_CONNECTED = 'connected'
STATUS_TOKEN_EXPIRED = 'token_expired'
STATUS_TOKEN_REVOKED = 'token_revoked'
STATUS_PERMISSION_DENIED = 'permission_denied'
STATUS_API_ACCESS_PENDING = 'api_access_pending'
STATUS_QUOTA_UNAVAILABLE = 'quota_unavailable'
STATUS_PARTIAL_ACCESS = 'partial_access'
STATUS_DISCONNECTED = 'disconnected'

# ─── Mock Data ──────────────────────────────────────────

_MOCK_ACCOUNTS = [
    {
        'account_id': 'accounts/123456789',
        'account_name': 'Bubur Fay Indonesia',
        'account_type': 'LOCATION_GROUP',
        'owner_name': 'Budi Santoso',
        'permission_level': 'OWNER_LEVEL',
        'location_count': 6,
    },
]

_MOCK_LOCATIONS = [
    {
        'resource_name': 'accounts/123456789/locations/1001',
        'store_code': 'DPK-01',
        'title': 'Bubur Fay Depok',
        'phone_numbers': {'primary_phone': '+622****9999'},
        'website_uri': 'https://buburfay.id/depok',
        'categories': [{'category_id': 'restaurant'}],
        'storefront_address': {
            'address_lines': ['Jl. Margonda Raya No. 100'],
            'locality': 'Depok',
            'administrative_area': 'Jawa Barat',
            'postal_code': '16423',
            'country_code': 'ID',
        },
        'latlng': {'latitude': -6.3879, 'longitude': 106.8230},
        'open_info': {'status': 'OPEN'},
        'metadata': {
            'place_id': 'ChIJ0-depok-margonda-001',
            'maps_uri': 'https://maps.google.com/?cid=1001',
        },
        'access_status': 'direct_access',
        'review_endpoint_accessible': True,
    },
    {
        'resource_name': 'accounts/123456789/locations/1002',
        'store_code': 'BKS-01',
        'title': 'Bubur Fay Bekasi',
        'phone_numbers': {'primary_phone': '+622****9999'},
        'website_uri': 'https://buburfay.id/bekasi',
        'categories': [{'category_id': 'restaurant'}],
        'storefront_address': {
            'address_lines': ['Jl. Ahmad Yani No. 50'],
            'locality': 'Bekasi',
            'administrative_area': 'Jawa Barat',
            'postal_code': '17141',
            'country_code': 'ID',
        },
        'latlng': {'latitude': -6.2348, 'longitude': 107.0012},
        'open_info': {'status': 'OPEN'},
        'metadata': {
            'place_id': 'ChIJ0-bekasi-ahmadyani-001',
            'maps_uri': 'https://maps.google.com/?cid=1002',
        },
        'access_status': 'direct_access',
        'review_endpoint_accessible': True,
    },
    {
        'resource_name': 'accounts/123456789/locations/1003',
        'store_code': 'JKP-01',
        'title': 'Bubur Fay Jakarta Pusat',
        'phone_numbers': {'primary_phone': '+622****8888'},
        'website_uri': 'https://buburfay.id/jakpus',
        'categories': [{'category_id': 'restaurant'}],
        'storefront_address': {
            'address_lines': ['Jl. Thamrin No. 10'],
            'locality': 'Jakarta Pusat',
            'administrative_area': 'DKI Jakarta',
            'postal_code': '10230',
            'country_code': 'ID',
        },
        'latlng': {'latitude': -6.1869, 'longitude': 106.8222},
        'open_info': {'status': 'OPEN'},
        'metadata': {
            'place_id': 'ChIJ0-jakpus-thamrin-001',
            'maps_uri': 'https://maps.google.com/?cid=1003',
        },
        'access_status': 'direct_access',
        'review_endpoint_accessible': True,
    },
    {
        'resource_name': 'accounts/123456789/locations/1004',
        'store_code': 'BGR-01',
        'title': 'Bubur Fay Bogor',
        'phone_numbers': {'primary_phone': '+622****6666'},
        'website_uri': 'https://buburfay.id/bogor',
        'categories': [{'category_id': 'restaurant'}],
        'storefront_address': {
            'address_lines': ['Jl. Pajajaran No. 25'],
            'locality': 'Bogor',
            'administrative_area': 'Jawa Barat',
            'postal_code': '16128',
            'country_code': 'ID',
        },
        'latlng': {'latitude': -6.5967, 'longitude': 106.7975},
        'open_info': {'status': 'OPEN'},
        'metadata': {
            'place_id': 'ChIJ0-bogor-pajajaran-001',
            'maps_uri': 'https://maps.google.com/?cid=1004',
        },
        'access_status': 'direct_access',
        'review_endpoint_accessible': True,
    },
    {
        'resource_name': 'accounts/123456789/locations/1005',
        'store_code': 'TNG-01',
        'title': 'Bubur Fay Tangerang',
        'phone_numbers': {'primary_phone': '+622****5555'},
        'website_uri': 'https://buburfay.id/tangerang',
        'categories': [{'category_id': 'restaurant'}],
        'storefront_address': {
            'address_lines': ['Jl. BSD Raya No. 8'],
            'locality': 'Tangerang',
            'administrative_area': 'Banten',
            'postal_code': '15321',
            'country_code': 'ID',
        },
        'latlng': {'latitude': -6.3007, 'longitude': 106.6474},
        'open_info': {'status': 'OPEN'},
        'metadata': {
            'place_id': 'ChIJ0-tangerang-bsd-001',
            'maps_uri': 'https://maps.google.com/?cid=1005',
        },
        'access_status': 'direct_access',
        'review_endpoint_accessible': True,
    },
    {
        'resource_name': 'accounts/123456789/locations/1006',
        'store_code': 'HRM-01',
        'title': 'Bubur Fay Harjamukti',
        'phone_numbers': {'primary_phone': '+622****1111'},
        'website_uri': 'https://buburfay.id/harjamukti',
        'categories': [{'category_id': 'restaurant'}],
        'storefront_address': {
            'address_lines': ['Jl. Harjamukti No. 15'],
            'locality': 'Depok',
            'administrative_area': 'Jawa Barat',
            'postal_code': '16425',
            'country_code': 'ID',
        },
        'latlng': {'latitude': -6.3720, 'longitude': 106.8800},
        'open_info': {'status': 'OPEN'},
        'metadata': {
            'place_id': 'ChIJ0-harjamukti-001',
            'maps_uri': 'https://maps.google.com/?cid=1006',
        },
        'access_status': 'direct_access',
        'review_endpoint_accessible': True,
    },
]


# ─── Helpers ─────────────────────────────────────────────

def _get_connection(business_id: str, tenant_id: str) -> GoogleConnection | None:
    return GoogleConnection.query.filter_by(
        business_id=business_id,
        tenant_id=tenant_id,
    ).first()


def _is_using_real_api() -> bool:
    cid = current_app.config.get('GOOGLE_CLIENT_ID', '')
    csec = current_app.config.get('GOOGLE_CLIENT_SECRET', '')
    return bool(cid and csec)


def _adapter_mode() -> str:
    return 'production' if _is_using_real_api() else 'mock'


def get_redirect_uri() -> str:
    return current_app.config.get(
        'GOOGLE_REDIRECT_URI',
        'http://localhost:8083/google/callback',
    )


# ─── OAuth State Management ──────────────────────────────

def _constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode('utf-8'), b.encode('utf-8')):
        result |= x ^ y
    return result == 0


def create_oauth_state(user_id: str, tenant_id: str, business_id: str,
                       connection_id: str, intent: str = '/google/accounts') -> str:
    """Create a cryptographically secure OAuth state with server-side storage.

    The state nonce is stored server-side with user/tenant/business bindings,
    an expiry, and single-use consumption guard.
    Returns the state string to include in the OAuth redirect URL.
    """
    # Clean up expired states for this tenant first
    OAuthState.query.filter(
        OAuthState.tenant_id == tenant_id,
        OAuthState.expires_at < datetime.now(timezone.utc),
    ).delete()
    db.session.commit()

    # Generate cryptographically secure nonce
    nonce = secrets.token_urlsafe(48)
    nonce_hash = hashlib.sha256(nonce.encode('utf-8')).hexdigest()

    state = OAuthState(
        nonce_hash=nonce_hash,
        user_id=user_id,
        tenant_id=tenant_id,
        business_id=business_id,
        connection_id=connection_id,
        redirect_intent=intent,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.session.add(state)
    db.session.commit()

    # Return nonce as the state value (the raw nonce, not the hash)
    # The callback receives this and we look it up by hash
    return nonce


def validate_oauth_state(state_nonce: str, user_id: str, tenant_id: str,
                         business_id: str) -> dict:
    """Validate an OAuth state nonce.

    Checks:
    - State exists (non-empty)
    - Not already consumed
    - Not expired
    - Belongs to the same user
    - Belongs to the same tenant
    - Belongs to the same business

    Returns the state record on success.
    Raises ValueError with a specific message on failure.
    """
    if not state_nonce:
        raise ValueError("oauth_state_empty")

    nonce_hash = hashlib.sha256(state_nonce.encode('utf-8')).hexdigest()
    state = OAuthState.query.filter_by(nonce_hash=nonce_hash).first()

    if not state:
        raise ValueError("oauth_state_invalid")

    if state.consumed_at is not None:
        raise ValueError("oauth_state_replayed")

    if state.expires_at < datetime.now(timezone.utc):
        raise ValueError("oauth_state_expired")

    if state.user_id != user_id:
        raise ValueError("oauth_state_user_mismatch")

    if state.tenant_id != tenant_id:
        raise ValueError("oauth_state_tenant_mismatch")

    if state.business_id != business_id:
        raise ValueError("oauth_state_business_mismatch")

    return state


def consume_oauth_state(state: OAuthState):
    """Mark an OAuth state as consumed (single-use enforcement)."""
    state.consumed_at = datetime.now(timezone.utc)
    db.session.commit()


# ─── OAuth Flow ──────────────────────────────────────────

def get_oauth_url(connection_id: str, tenant_id: str) -> str:
    """In mock mode, returns a local URL that immediately simulates success.
    The actual state is created by the route handler before calling this,
    so this function just wraps the redirect URL."""
    if not _is_using_real_api():
        redirect = get_redirect_uri()
        # State must be passed by the caller — this is a fallback
        state = f"{tenant_id}:{connection_id}"
        return f"{redirect}?code=mock_auth_code&state={state}"
    raise NotImplementedError("Real OAuth not yet configured")


def exchange_code_for_token(code: str, connection_id: str, tenant_id: str,
                            adapter_mode_val: str = 'mock') -> GoogleConnection:
    """Exchange an OAuth authorization code for tokens.

    In mock mode, creates synthetic tokens and saves to DB with mock status.
    """
    conn = GoogleConnection.query.get(connection_id)
    if not conn or conn.tenant_id != tenant_id:
        raise PermissionError("Connection not found or tenant mismatch")

    if adapter_mode_val == 'mock':
        access_token = f"mock_access_token_{tenant_id[:8]}_{datetime.now(timezone.utc).timestamp():.0f}"
        refresh_token = f"mock_refresh_token_{tenant_id[:8]}_{secrets.randbits(20):06d}"
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        conn.encrypted_access_token_ref = encrypt_token(access_token)
        conn.encrypted_refresh_token_ref = encrypt_token(refresh_token)
        conn.token_expiry = expiry
        conn.google_subject_id = f"user/{tenant_id[:8]}"
        conn.scopes = 'https://www.googleapis.com/auth/business.manage'
        conn.status = STATUS_MOCK_CONNECTED
        conn.adapter_mode = 'mock'
        conn.connected_at = datetime.now(timezone.utc)
        db.session.commit()
        return conn

    raise NotImplementedError("Real OAuth token exchange not yet configured")


# ─── Account Discovery ──────────────────────────────────

def list_accounts(business_id: str, tenant_id: str) -> list[dict]:
    conn = _get_connection(business_id, tenant_id)
    if not conn:
        raise ValueError("Not connected")
    if conn.status not in (STATUS_CONNECTED, STATUS_MOCK_CONNECTED, STATUS_PARTIAL_ACCESS):
        raise ValueError(f"Connection status is {conn.status}")
    if not _is_using_real_api():
        return _MOCK_ACCOUNTS
    raise NotImplementedError("Real account listing not yet configured")


def select_account(business_id: str, tenant_id: str, account_id: str,
                   user_id: str | None = None):
    conn = _get_connection(business_id, tenant_id)
    if not conn:
        raise ValueError("Not connected")
    conn.selected_account_id = account_id
    db.session.commit()
    log_audit(
        action='google_account_selected',
        entity_type='google_connection',
        entity_id=conn.id,
        tenant_id=tenant_id,
        actor_id=user_id,
        before={},
        after={'selected_account_id': account_id},
    )
    db.session.commit()


# ─── Location Retrieval ─────────────────────────────────

def list_locations(business_id: str, tenant_id: str) -> list[dict]:
    conn = _get_connection(business_id, tenant_id)
    if not conn:
        raise ValueError("Not connected")
    if not conn.selected_account_id:
        raise ValueError("No account selected")
    if not _is_using_real_api():
        return _MOCK_LOCATIONS
    raise NotImplementedError("Real location listing not yet configured")


def _owner_verification_overrides_match(owner_status: str) -> bool:
    """Owner verification status takes priority over GBP match.
    
    Rules:
    - old_or_closed: NEVER activated by GBP match
    - verified/confirmed: can be matched
    - pending: can be matched
    """
    return owner_status == 'old_or_closed'


# ─── Reconciliation ─────────────────────────────────────

def reconcile_candidates(business_id: str, tenant_id: str) -> list[dict]:
    conn = _get_connection(business_id, tenant_id)
    if not conn or not conn.selected_account_id:
        raise ValueError("Not connected or no account selected")

    candidates = LocationCandidate.query.filter_by(
        business_id=business_id,
        tenant_id=tenant_id,
    ).all()

    if not _is_using_real_api():
        official_locs = _MOCK_LOCATIONS
    else:
        official_locs = list_locations(business_id, tenant_id)

    official_by_place = {}
    for loc in official_locs:
        pid = loc.get('metadata', {}).get('place_id')
        if pid:
            official_by_place[pid] = loc

    results = []

    for cand in candidates:
        place_id = cand.place_id or ''
        result = {
            'candidate_id': cand.id,
            'place_id': place_id,
            'display_name': cand.display_name,
            'official_resource_name': None,
            'official_title': None,
            'match_status': 'unmatched_to_gbp',
            'confidence': 0.0,
            'match_method': None,
            'owner_verification_status': cand.owner_verification_status or 'pending',
        }

        # Check owner verification — old_or_closed cannot be overridden
        if _owner_verification_overrides_match(cand.owner_verification_status):
            # Still check if GBP has this location, but flag it
            if place_id and place_id in official_by_place:
                loc = official_by_place[place_id]
                result['official_resource_name'] = loc['resource_name']
                result['official_title'] = loc['title']
                result['match_status'] = 'matched_to_gbp_but_owner_old'
                result['confidence'] = 1.0
                result['match_method'] = 'exact_place_id'
                result['owner_blocked'] = True
                # Do NOT set monitor_enabled or reply_enabled
            # else: unmatched and old — fine
            results.append(result)
            continue

        # Priority 1: Exact Place ID
        if place_id and place_id in official_by_place:
            loc = official_by_place[place_id]
            result['official_resource_name'] = loc['resource_name']
            result['official_title'] = loc['title']
            result['match_status'] = 'matched_to_gbp'
            result['confidence'] = 1.0
            result['match_method'] = 'exact_place_id'
        else:
            # Priority 2: Name + city fuzzy match
            official_matches = []
            cand_name_normalized = (cand.display_name or '').lower().strip()
            cand_city = ''
            if cand.formatted_address:
                for city_word in ['depok', 'bekasi', 'jakarta', 'bogor', 'tangerang']:
                    if city_word in cand.formatted_address.lower():
                        cand_city = city_word
                        break

            for loc in official_locs:
                loc_name = loc.get('title', '').lower().strip()
                loc_addr = loc.get('storefront_address', {})
                loc_city = (loc_addr.get('locality', '') or '').lower()
                loc_phone = loc.get('phone_numbers', {}).get('primary_phone', '')

                name_score = 0
                cand_words = set(cand_name_normalized.split())
                loc_words = set(loc_name.split())
                common = cand_words & loc_words
                if common:
                    name_score = len(common) / max(len(cand_words), len(loc_words))

                city_bonus = 0.2 if cand_city and cand_city in loc_city else 0
                phone_bonus = 0.3 if cand.phone and loc_phone and cand.phone.replace(' ', '') == loc_phone.replace(' ', '') else 0
                total_score = name_score + city_bonus + phone_bonus

                if total_score >= 0.4:
                    official_matches.append((loc, total_score))
                elif 0.2 <= total_score < 0.4:
                    official_matches.append((loc, total_score))

            if official_matches:
                official_matches.sort(key=lambda x: x[1], reverse=True)
                best, best_score = official_matches[0]

                if best_score >= 0.7 and len(official_matches) == 1:
                    result['official_resource_name'] = best['resource_name']
                    result['official_title'] = best['title']
                    result['match_status'] = 'matched_to_gbp'
                    result['confidence'] = best_score
                    result['match_method'] = 'name_geo'
                elif len(official_matches) == 1:
                    result['official_resource_name'] = best['resource_name']
                    result['official_title'] = best['title']
                    result['match_status'] = 'matched_to_gbp'
                    result['confidence'] = best_score
                    result['match_method'] = 'name_geo'
                else:
                    # Multiple candidates — ambiguous
                    result['match_status'] = 'ambiguous_match'
                    result['confidence'] = best_score
                    result['match_method'] = 'human_review'
                    result['ambiguous_options'] = [
                        {'resource_name': loc['resource_name'],
                         'title': loc['title'],
                         'score': round(score, 2)}
                        for loc, score in official_matches
                    ]

        results.append(result)

    return results


def save_reconciliation(business_id: str, tenant_id: str, results: list[dict],
                        resolve_ambiguous: dict | None = None,
                        user_id: str | None = None):
    """Save reconciliation results atomically in one transaction.

    If audit logging fails, the entire reconciliation is rolled back.
    Respects owner_verification_status — old_or_closed outlets are NEVER
    activated by GBP match.
    """
    # Build candidate lookup
    candidate_ids = [r['candidate_id'] for r in results]
    candidates = LocationCandidate.query.filter(
        LocationCandidate.id.in_(candidate_ids),
        LocationCandidate.business_id == business_id,
        LocationCandidate.tenant_id == tenant_id,
    ).all()
    candidate_map = {c.id: c for c in candidates}

    # Collect the outlet operations
    outlet_updates = {}
    audit_entries = []

    for result in results:
        cand = candidate_map.get(result['candidate_id'])
        if not cand:
            continue

        # Skip old_or_closed — never activate
        if _owner_verification_overrides_match(cand.owner_verification_status):
            audit_entries.append({
                'action': 'reconciliation_skipped_owner_old',
                'entity_type': 'location_candidate',
                'entity_id': cand.id,
                'before': {'owner_verification_status': cand.owner_verification_status},
                'after': {'reason': 'Owner verified as old_or_closed. GBP match ignored.'},
                'reason': f'Candidate {cand.display_name} is old_or_closed — not activated',
            })
            continue

        match_status = result['match_status']

        # Handle ambiguous resolutions
        if match_status == 'ambiguous_match' and resolve_ambiguous:
            cand_id = result['candidate_id']
            if cand_id in resolve_ambiguous:
                decision = resolve_ambiguous[cand_id]
                if isinstance(decision, dict) and 'resource_name' in decision:
                    match_status = 'matched_to_gbp'
                    result['official_resource_name'] = decision.get('resource_name', '')
                    result['official_title'] = decision.get('title', '')
                    result['confidence'] = 1.0
                    result['match_method'] = 'human_review'

        if match_status == 'matched_to_gbp':
            # Find or create outlet
            outlet = Outlet.query.filter_by(
                business_id=business_id,
                tenant_id=tenant_id,
                gbp_location_id=result.get('official_resource_name', ''),
            ).first()

            if not outlet:
                # Try to find by candidate association
                outlet = Outlet.query.filter_by(
                    business_id=business_id,
                    tenant_id=tenant_id,
                    public_place_id=result.get('place_id', ''),
                ).first()

            if not outlet:
                # Create new outlet
                outlet = Outlet(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    name=result.get('official_title') or cand.display_name or 'Unknown',
                    address=cand.formatted_address,
                    latitude=cand.latitude,
                    longitude=cand.longitude,
                    public_place_id=result.get('place_id', ''),
                    gbp_location_id=result.get('official_resource_name', ''),
                    owner_verification_status=cand.owner_verification_status,
                    gbp_match_status='matched',
                    status='active',
                    monitor_enabled=False,     # Default off
                    reply_enabled=False,       # Never enabled in mock mode
                )
                db.session.add(outlet)
            else:
                outlet.gbp_match_status = 'matched'
                if result.get('official_resource_name'):
                    outlet.gbp_location_id = result['official_resource_name']
                if cand.owner_verification_status in ('verified', 'owner_confirmed'):
                    outlet.monitor_enabled = True
                    # reply_enabled stays False in mock mode

            outlet_updates[result['candidate_id']] = outlet
            audit_entries.append({
                'action': 'reconciliation_matched',
                'entity_type': 'outlet',
                'entity_id': outlet.id,
                'before': {'gbp_match_status': 'unmatched'},
                'after': {'gbp_match_status': 'matched',
                          'gbp_location_id': result.get('official_resource_name', '')},
            })

        elif match_status == 'ambiguous_match':
            audit_entries.append({
                'action': 'reconciliation_ambiguous',
                'entity_type': 'location_candidate',
                'entity_id': cand.id,
                'before': {},
                'after': {'reason': 'Ambiguous match — needs human review'},
            })

        else:
            audit_entries.append({
                'action': 'reconciliation_unmatched',
                'entity_type': 'location_candidate',
                'entity_id': cand.id,
                'before': {},
                'after': {'reason': 'No GBP match found'},
            })

    # Execute all database operations atomically
    try:
        for entry in audit_entries:
            log_audit(
                action=entry['action'],
                entity_type=entry['entity_type'],
                entity_id=entry['entity_id'],
                before=entry.get('before'),
                after=entry.get('after'),
                reason=entry.get('reason'),
                tenant_id=tenant_id,
                actor_id=user_id,
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


# ─── Connection Health ──────────────────────────────────

def check_connection_health(business_id: str, tenant_id: str) -> dict:
    conn = _get_connection(business_id, tenant_id)
    if not conn:
        raise ValueError("Not connected")

    now = datetime.now(timezone.utc)
    is_mock = conn.adapter_mode == 'mock' or not _is_using_real_api()

    token_valid = False
    if conn.encrypted_access_token_ref:
        if conn.token_expiry and conn.token_expiry > now:
            token_valid = True
        elif is_mock:
            # Mock tokens are always "valid" for UI testing
            token_valid = True

    return {
        'adapter_mode': conn.adapter_mode or 'mock',
        'oauth_token_valid': token_valid,
        'production_api_connected': conn.status == STATUS_CONNECTED,
        'api_access_available': conn.status in (
            STATUS_CONNECTED, STATUS_MOCK_CONNECTED, STATUS_PARTIAL_ACCESS),
        'account_accessible': 'mock_only' if is_mock else (conn.selected_account_id is not None),
        'location_count': 6 if is_mock else 0,
        'review_endpoint_accessible': False,
        'review_endpoint_status': 'mock_only' if is_mock else 'unavailable',
        'reply_capability': 'disabled',
        'reply_enabled': False,
        'reconnect_required': not token_valid,
        'connection_status': conn.status,
        'selected_account': conn.selected_account_id,
        'last_health_check': now.isoformat(),
        'blocking_reason': [
            'Google OAuth credential belum tersedia' if is_mock else None,
            'OAuth consent screen belum dikonfigurasi' if is_mock else None,
            'Google Business Profile API belum approved' if is_mock else None,
            'Mock adapter — bukan koneksi produksi' if is_mock else None,
        ],
        'last_error': conn.last_error,
    }


# ─── Disconnect ─────────────────────────────────────────

def disconnect(business_id: str, tenant_id: str, revoke: bool = False,
               user_id: str | None = None):
    conn = _get_connection(business_id, tenant_id)
    if not conn:
        raise ValueError("Not connected")

    old_status = conn.status
    before = {
        'status': old_status,
        'selected_account_id': conn.selected_account_id,
    }

    # Wipe tokens
    conn.encrypted_access_token_ref = None
    conn.encrypted_refresh_token_ref = None
    conn.token_expiry = None
    conn.selected_account_id = None
    conn.google_subject_id = None
    conn.status = STATUS_DISCONNECTED
    conn.adapter_mode = 'mock'
    db.session.commit()

    # Also disable monitoring and reply for all outlets
    Outlet.query.filter_by(
        business_id=business_id,
        tenant_id=tenant_id,
    ).update({
        Outlet.monitor_enabled: False,
        Outlet.reply_enabled: False,
        Outlet.gbp_match_status: 'unmatched',
    })
    db.session.commit()

    log_audit(
        action='google_disconnected',
        entity_type='google_connection',
        entity_id=conn.id,
        tenant_id=tenant_id,
        actor_id=user_id,
        before=before,
        after={'status': STATUS_DISCONNECTED, 'revoked': revoke},
        reason='User initiated disconnect' + (' with token revoke' if revoke else ''),
    )
    db.session.commit()
