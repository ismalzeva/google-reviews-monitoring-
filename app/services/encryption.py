"""Token encryption service — Fernet symmetric encryption.

Encrypts Google OAuth access/refresh tokens before storage.
Uses APP_SECRET_KEY derived from Flask SECRET_KEY for key derivation.
Never stores plaintext tokens in the database.
"""

import base64
import hashlib
from cryptography.fernet import Fernet

_fernet_cache = None


def _get_fernet(app_secret_key: str | None = None) -> Fernet:
    """Get or create a Fernet instance keyed to the app secret."""
    global _fernet_cache
    if _fernet_cache is not None:
        return _fernet_cache

    if not app_secret_key:
        from flask import current_app
        app_secret_key = current_app.config.get('SECRET_KEY', '')

    # Derive a 32-byte URL-safe key from SECRET_KEY
    key_bytes = hashlib.sha256(app_secret_key.encode('utf-8')).digest()
    key_b64 = base64.urlsafe_b64encode(key_bytes)
    _fernet_cache = Fernet(key_b64)
    return _fernet_cache


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string. Returns URL-safe ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a previously encrypted token string."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')


def reset_cache():
    """Reset the Fernet cache (for testing)."""
    global _fernet_cache
    _fernet_cache = None
