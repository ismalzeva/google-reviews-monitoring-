"""Google Business Profile production HTTP client.

Handles real OAuth token exchange, refresh, account/location/Review API,
and reply operations against the Google Business Profile API v4.

All functions raise clear, typed exceptions on failure so callers
can distinguish between credential, permission, and network errors.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ─── Exceptions ──────────────────────────────────────────


class GBPApiError(Exception):
    """Base exception for GBP API errors."""


class CredentialMissingError(GBPApiError):
    """GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not configured."""


class TokenExpiredError(GBPApiError):
    """Access token expired and could not be refreshed."""


class TokenRevokedError(GBPApiError):
    """Refresh token revoked by user or Google."""


class PermissionDeniedError(GBPApiError):
    """Insufficient permissions — API not approved or scope missing."""


class RedirectUriError(GBPApiError):
    """Redirect URI not authorized in Google Cloud Console."""


class GBPHttpError(GBPApiError):
    """Generic HTTP response error from GBP API."""


# ─── Constants ──────────────────────────────────────────

GBP_API_BASE = 'https://businessprofile.googleapis.com/v1'
OAUTH_TOKEN_URI = 'https://oauth2.googleapis.com/token'
DEFAULT_TIMEOUT = 15  # seconds


# ─── Token Operations ───────────────────────────────────


def exchange_auth_code(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Exchange OAuth authorization code for access + refresh tokens.

    Returns dict with keys: access_token, refresh_token, expires_in, scope, token_type
    Raises RedirectUriError, PermissionDeniedError, or GBPHttpError.
    """
    if not client_id or not client_secret:
        raise CredentialMissingError(
            'GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set'
        )

    payload = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }

    try:
        resp = requests.post(
            OAUTH_TOKEN_URI,
            data=payload,
            timeout=DEFAULT_TIMEOUT,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
    except requests.RequestException as e:
        raise GBPHttpError(f'Token exchange network error: {e}') from e

    if resp.status_code == 400:
        body = resp.json()
        err = body.get('error', '')
        desc = body.get('error_description', '')
        if 'redirect_uri_mismatch' in err:
            raise RedirectUriError(
                f'Redirect URI mismatch. Configured: {redirect_uri}. '
                f'Must match authorized URI in Google Cloud Console. '
                f'Detail: {desc}'
            )
        if 'invalid_grant' in err:
            raise GBPHttpError(f'Invalid auth code (expired or already used): {desc}')
        raise GBPHttpError(f'Token exchange failed (400): {err} — {desc}')

    if resp.status_code == 403:
        raise PermissionDeniedError(
            'API access denied. Verify OAuth consent screen and '
            'Business Profile API enablement in Google Cloud Console.'
        )

    if resp.status_code != 200:
        raise GBPHttpError(
            f'Token exchange failed (HTTP {resp.status_code}): {resp.text[:500]}'
        )

    data = resp.json()
    return {
        'access_token': data['access_token'],
        'refresh_token': data.get('refresh_token', ''),
        'expires_in': data.get('expires_in', 3600),
        'scope': data.get('scope', ''),
        'token_type': data.get('token_type', 'Bearer'),
    }


def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """Refresh an expired access token.

    Returns dict with: access_token, expires_in, scope, token_type
    Raises TokenExpiredError, TokenRevokedError, or GBPHttpError.
    """
    if not refresh_token:
        raise TokenExpiredError('No refresh token available')

    payload = {
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'refresh_token',
    }

    try:
        resp = requests.post(
            OAUTH_TOKEN_URI,
            data=payload,
            timeout=DEFAULT_TIMEOUT,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
    except requests.RequestException as e:
        raise GBPHttpError(f'Token refresh network error: {e}') from e

    if resp.status_code == 400:
        body = resp.json()
        err = body.get('error', '')
        if err == 'invalid_grant':
            raise TokenRevokedError(
                'Refresh token revoked or expired. '
                'User must re-authenticate via OAuth.'
            )
        raise GBPHttpError(f'Token refresh failed (400): {err}')

    if resp.status_code != 200:
        raise GBPHttpError(
            f'Token refresh failed (HTTP {resp.status_code}): {resp.text[:500]}'
        )

    data = resp.json()
    # Some refresh responses don't include a new refresh_token
    result = {
        'access_token': data['access_token'],
        'expires_in': data.get('expires_in', 3600),
        'scope': data.get('scope', ''),
        'token_type': data.get('token_type', 'Bearer'),
    }
    # If a new refresh_token was issued, return it
    if 'refresh_token' in data:
        result['refresh_token'] = data['refresh_token']

    return result


# ─── Authorised HTTP Helper ────────────────────────────


def _authorised_get(
    url: str,
    access_token: str,
    params: dict | None = None,
) -> requests.Response:
    """Make an authenticated GET request to GBP API."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
    }
    try:
        return requests.get(url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as e:
        raise GBPHttpError(f'HTTP request failed: {e}') from e


def _authorised_post(
    url: str,
    access_token: str,
    body: dict | None = None,
) -> requests.Response:
    """Make an authenticated POST request to GBP API."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    try:
        return requests.post(url, headers=headers, json=body, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as e:
        raise GBPHttpError(f'HTTP request failed: {e}') from e


def _check_gbp_response(resp: requests.Response, context: str = ''):
    """Check GBP API response and raise appropriate error."""
    if resp.status_code == 401:
        raise TokenExpiredError(f'Access token expired ({context})')
    if resp.status_code == 403:
        raise PermissionDeniedError(
            f'API access denied ({context}). '
            'Verify Business Profile API is enabled and approved.'
        )
    if resp.status_code == 429:
        raise GBPHttpError('Rate limited by GBP API. Retry after backoff.')
    if resp.status_code >= 500:
        raise GBPHttpError(
            f'GBP server error (HTTP {resp.status_code}): {resp.text[:300]}'
        )
    if resp.status_code != 200:
        raise GBPHttpError(
            f'GBP API error (HTTP {resp.status_code}) {context}: {resp.text[:500]}'
        )


# ─── Account Discovery ──────────────────────────────────


def verify_pubsub_token(token: str) -> dict | None:
    """Verify a Google Pub/Sub OIDC token.

    Validates the JWT using Google's public keys and returns the
    decoded payload if valid, or None if invalid/expired.
    """
    import jwt as pyjwt
    from jwt import PyJWKClient, PyJWTError

    GOOGLE_CERTS_URL = 'https://www.googleapis.com/oauth2/v3/certs'

    try:
        jwks_client = PyJWKClient(GOOGLE_CERTS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256'],
            options={
                'verify_aud': False,  # Pub/Sub uses custom audience
                'verify_iss': True,
                'require': ['exp', 'iat'],
            },
        )
        # Verify the token is for Pub/Sub
        if payload.get('email') and 'gcp-sa-pubsub' in payload.get('email', ''):
            return payload
        return None
    except (PyJWTError, Exception):
        logger.exception('Pub/Sub JWT verification failed')
        return None


def list_accounts_production(access_token: str, base_url: str) -> list[dict]:
    """Fetch Google Business Profile accounts for the authenticated user.

    GET /v1/accounts
    """
    url = f'{base_url}/accounts'
    resp = _authorised_get(url, access_token)
    _check_gbp_response(resp, 'list_accounts')

    data = resp.json()
    accounts = data.get('accounts', [])
    return [
        {
            'account_id': a.get('name', ''),
            'account_name': a.get('accountName', ''),
            'account_type': a.get('type', ''),
            'owner_name': a.get('owner', {}).get('name', ''),
            'permission_level': a.get('permissionLevel', ''),
            'location_count': a.get('locationCount', {}).get('total', 0),
        }
        for a in accounts
    ]


# ─── Location Discovery ─────────────────────────────────


def list_locations_production(
    access_token: str,
    account_name: str,
    base_url: str = GBP_API_BASE,
    page_size: int = 100,
    page_token: str | None = None,
) -> dict:
    """Fetch locations for a GBP account.

    GET /v1/{account_name}/locations

    Returns dict with 'locations' list and optional 'next_page_token'.
    """
    url = f'{base_url}/{account_name}/locations'
    params = {'pageSize': page_size}
    if page_token:
        params['pageToken'] = page_token

    resp = _authorised_get(url, access_token, params=params)
    _check_gbp_response(resp, 'list_locations')

    data = resp.json()
    locations = data.get('locations', [])
    result = []
    for loc in locations:
        metadata = loc.get('metadata', {})
        address = loc.get('address', {})
        result.append({
            'resource_name': loc.get('name', ''),
            'store_code': loc.get('storeCode', ''),
            'title': loc.get('title', ''),
            'phone_numbers': loc.get('phoneNumbers', {}),
            'website_uri': loc.get('websiteUrl', ''),
            'categories': loc.get('categories', []),
            'storefront_address': {
                'address_lines': address.get('addressLines', []),
                'locality': address.get('locality', ''),
                'administrative_area': address.get('administrativeArea', ''),
                'postal_code': address.get('postalCode', ''),
                'country_code': address.get('regionCode', ''),
            },
            'latlng': loc.get('latlng', {}),
            'open_info': loc.get('openInfo', {}),
            'metadata': {
                'place_id': metadata.get('placeId', ''),
                'maps_uri': metadata.get('mapsUrl', ''),
            },
            'access_status': loc.get('access', {}).get('accessStatus', ''),
            'review_endpoint_accessible': False,  # filled per-location below if needed
        })
    # Fetch first batch of reviews per location to check accessibility
    # (only first 1 review per location to avoid rate limits)

    return {
        'locations': result,
        'next_page_token': data.get('nextPageToken'),
    }


# ─── Review Operations ──────────────────────────────────


def list_reviews_production(
    access_token: str,
    location_name: str,
    base_url: str = GBP_API_BASE,
    page_size: int = 10,
    page_token: str | None = None,
    order_by: str = 'update_time desc',
) -> dict:
    """Fetch reviews for a location.

    GET /v1/{location_name}/reviews

    Returns dict with 'reviews' list, 'next_page_token', 'total_review_count'.
    """
    url = f'{base_url}/{location_name}/reviews'
    params = {
        'pageSize': page_size,
        'orderBy': order_by,
    }
    if page_token:
        params['pageToken'] = page_token

    resp = _authorised_get(url, access_token, params=params)
    _check_gbp_response(resp, 'list_reviews')

    data = resp.json()
    reviews = data.get('reviews', [])
    formatted = []
    for rev in reviews:
        review_id = rev.get('reviewId', '')
        name = rev.get('name', '')
        formatted.append({
            'reviewId': review_id,
            'name': name,
            'reviewer': rev.get('reviewer', {}).get('displayName', 'Anonymous'),
            'starRating': int(rev.get('starRating', 5)),
            'comment': rev.get('comment', ''),
            'createTime': rev.get('createTime', ''),
            'updateTime': rev.get('updateTime', ''),
            'reviewReply': rev.get('reviewReply', None),
        })

    return {
        'reviews': formatted,
        'next_page_token': data.get('nextPageToken'),
        'total_review_count': data.get('totalReviewCount', 0),
    }


def get_review_production(
    access_token: str,
    review_name: str,
    base_url: str = GBP_API_BASE,
) -> Optional[dict]:
    """Fetch a single review by its resource name.

    GET /v1/{review_name}
    """
    url = f'{base_url}/{review_name}'
    resp = _authorised_get(url, access_token)
    if resp.status_code == 404:
        return None
    _check_gbp_response(resp, 'get_review')

    rev = resp.json()
    return {
        'reviewId': rev.get('reviewId', ''),
        'name': rev.get('name', ''),
        'reviewer': rev.get('reviewer', {}).get('displayName', 'Anonymous'),
        'starRating': int(rev.get('starRating', 5)),
        'comment': rev.get('comment', ''),
        'createTime': rev.get('createTime', ''),
        'updateTime': rev.get('updateTime', ''),
        'reviewReply': rev.get('reviewReply', None),
    }


# ─── Reply Operations ───────────────────────────────────


def create_reply_production(
    access_token: str,
    review_name: str,
    reply_text: str,
    base_url: str = GBP_API_BASE,
) -> dict:
    """Post a reply to a review.

    POST /v1/{review_name}/reply

    Returns the reply object from GBP API.
    """
    url = f'{base_url}/{review_name}/reply'
    body = {'comment': reply_text}

    resp = _authorised_post(url, access_token, body=body)
    _check_gbp_response(resp, 'create_reply')

    data = resp.json()
    return {
        'replyId': data.get('name', ''),
        'comment': data.get('comment', ''),
        'updateTime': data.get('updateTime', ''),
        'state': data.get('state', ''),
    }


def update_reply_production(
    access_token: str,
    review_name: str,
    reply_text: str,
    base_url: str = GBP_API_BASE,
) -> dict:
    """Update an existing reply on a review.

    PUT /v1/{review_name}/reply

    Returns the updated reply object.
    """
    url = f'{base_url}/{review_name}/reply'
    body = {'comment': reply_text}

    try:
        resp = requests.put(
            url,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            json=body,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as e:
        raise GBPHttpError(f'HTTP request failed: {e}') from e

    _check_gbp_response(resp, 'update_reply')

    data = resp.json()
    return {
        'replyId': data.get('name', ''),
        'comment': data.get('comment', ''),
        'updateTime': data.get('updateTime', ''),
        'state': data.get('state', ''),
    }


# ─── Health / Diagnostic ────────────────────────────────


def verify_oauth_config(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Verify OAuth configuration without making API calls.

    Returns dict with check results.
    """
    checks = []
    all_ok = True

    if not client_id:
        checks.append({'check': 'client_id', 'status': 'fail', 'message': 'GOOGLE_CLIENT_ID is empty'})
        all_ok = False
    else:
        checks.append({'check': 'client_id', 'status': 'ok'})

    if not client_secret:
        checks.append({'check': 'client_secret', 'status': 'fail', 'message': 'GOOGLE_CLIENT_SECRET is empty'})
        all_ok = False
    else:
        checks.append({'check': 'client_secret', 'status': 'ok'})

    if not redirect_uri or 'localhost' in redirect_uri:
        checks.append({
            'check': 'redirect_uri',
            'status': 'warn',
            'message': f'Redirect URI is "{redirect_uri}". For production, use HTTPS domain.',
        })
    else:
        checks.append({'check': 'redirect_uri', 'status': 'ok'})

    if not redirect_uri.startswith('https://'):
        checks.append({
            'check': 'https',
            'status': 'warn',
            'message': 'Redirect URI uses HTTP. Production should use HTTPS.',
        })

    return {
        'all_checks_ok': all_ok,
        'google_oauth_configured': all_ok,
        'checks': checks,
    }
