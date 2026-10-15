"""Fernet-backed symmetric encryption for JSON mapping payloads.

The public surface is intentionally small:

``encrypt_mapping(mapping)``
    Encrypt a ``dict`` and return an envelope ``dict`` suitable for storage in
    an existing JSON column.

``decrypt_mapping(envelope)``
    Return the plaintext ``dict``. Legacy plaintext dicts are returned as-is so
    existing rows keep working; use ``is_encrypted`` to distinguish.

Key management
--------------
The master key is read from ``PLATFORM_CREDENTIAL_MASTER_KEY``. Both a raw
32-byte urlsafe-base64 Fernet key and an arbitrary passphrase are accepted; a
passphrase is stretched with PBKDF2-HMAC-SHA256 into a valid Fernet key. When no
key is configured the box *fails closed* on **both** read and write: writes refuse
to store new plaintext, and an envelope that cannot be decrypted raises
`SecretBoxError` rather than being silently treated as an empty payload. Only
legacy plaintext rows (no envelope marker) are read through untouched, so existing
data stays readable until it is lazily migrated.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

#: Reserved key that holds the versioned envelope inside the stored JSON object.
ENVELOPE_KEY = "__secret_envelope__"

#: Envelope versions currently understood by this module.
CURRENT_VERSION = "v1"

#: Environment variable holding the master key.
MASTER_KEY_ENV = "PLATFORM_CREDENTIAL_MASTER_KEY"

_PBKDF2_ITERATIONS = 480_000
_SALT = b"personal-cognitive-ip-engine.credentials.v1"

_lock = threading.Lock()
_cached_key: Optional[bytes] = None
_cached_source: Optional[str] = None


class SecretBoxError(Exception):
    """Raised when a payload cannot be encrypted or decrypted."""


class SecretKeyMissingError(SecretBoxError):
    """Raised when encryption is requested but no master key is configured."""


def _normalize_master_key(raw: str) -> bytes:
    """Turn an arbitrary configured secret into a valid Fernet key."""
    candidate = raw.strip()
    if not candidate:
        raise SecretKeyMissingError("Configured master key is empty.")

    # Already a valid Fernet key (32 urlsafe-base64 bytes).
    try:
        decoded = base64.urlsafe_b64decode(candidate.encode("utf-8"))
        if len(decoded) == 32:
            return candidate.encode("utf-8")
    except Exception:
        pass

    # Otherwise treat it as a passphrase and stretch it deterministically.
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        candidate.encode("utf-8"),
        _SALT,
        _PBKDF2_ITERATIONS,
        dklen=32,
    )
    return base64.urlsafe_b64encode(digest)


def _load_master_key() -> Optional[bytes]:
    """Resolve the master key, caching the derived Fernet key per process."""
    global _cached_key, _cached_source

    raw = os.environ.get(MASTER_KEY_ENV)
    if raw is None:
        try:
            from app.core.config import settings

            raw = getattr(settings, MASTER_KEY_ENV, None)
        except Exception:
            raw = None

    if not raw or not raw.strip():
        _cached_key = None
        _cached_source = None
        return None

    if raw == _cached_source and _cached_key is not None:
        return _cached_key

    key = _normalize_master_key(raw)
    _cached_key = key
    _cached_source = raw
    return key


def _fernet() -> Fernet:
    key = _load_master_key()
    if key is None:
        raise SecretKeyMissingError(
            f"{MASTER_KEY_ENV} is not configured; refusing to write plaintext secrets."
        )
    return Fernet(key)


def master_key_configured() -> bool:
    """Return ``True`` when a usable master key is available."""
    try:
        return _load_master_key() is not None
    except SecretBoxError:
        return False


def reset_master_key_cache() -> None:
    """Clear the cached derived key (used by tests that mutate the env)."""
    global _cached_key, _cached_source
    with _lock:
        _cached_key = None
        _cached_source = None


def is_encrypted_envelope(payload: Any) -> bool:
    """Return ``True`` when ``payload`` looks like a versioned secret envelope."""
    if not isinstance(payload, dict):
        return False
    value = payload.get(ENVELOPE_KEY)
    return isinstance(value, str) and ":" in value


def is_encrypted(payload: Any) -> bool:
    """Alias of :func:`is_encrypted_envelope` for readability at call sites."""
    return is_encrypted_envelope(payload)


def _pack(envelope_value: str) -> Dict[str, Any]:
    return {ENVELOPE_KEY: envelope_value}


def encrypt_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Encrypt ``mapping`` into a versioned envelope dict.

    Raises:
        SecretKeyMissingError: when no master key is configured (fail closed).
        SecretBoxError: when ``mapping`` is not JSON-serialisable.
    """
    if not mapping:
        # An empty mapping carries no secret; store an empty object rather than
        # an envelope so "has_cookies" checks stay truthful.
        return {}
    if is_encrypted_envelope(mapping):
        # Already encrypted; treat as idempotent to avoid double wrapping.
        return dict(mapping)

    try:
        plaintext = json.dumps(mapping, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise SecretBoxError(f"Secret payload is not JSON-serialisable: {exc}") from exc

    token = _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return _pack(f"{CURRENT_VERSION}:{token}")


def _decrypt_envelope_value(value: str) -> Dict[str, Any]:
    version, _, token = value.partition(":")
    if not token:
        raise SecretBoxError("Malformed secret envelope: missing payload.")

    if version != CURRENT_VERSION:
        raise SecretBoxError(f"Unsupported secret envelope version: {version!r}")

    try:
        raw = _fernet().decrypt(token.encode("ascii"))
    except InvalidToken as exc:
        raise SecretBoxError(
            "Secret payload could not be decrypted; the master key may have changed."
        ) from exc

    try:
        decoded = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise SecretBoxError(f"Decrypted secret payload is not valid JSON: {exc}") from exc

    if not isinstance(decoded, dict):
        raise SecretBoxError("Decrypted secret payload is not a JSON object.")
    return decoded


def decrypt_mapping(payload: Any) -> Dict[str, Any]:
    """Return the plaintext mapping for ``payload``.

    Backward compatibility:
        * ``None`` -> ``{}``.
        * Legacy plaintext dicts (no envelope key) are returned unchanged.
        * Known envelopes are decrypted.
    """
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise SecretBoxError(
            f"Secret payload must be a JSON object, got {type(payload).__name__}."
        )
    if not is_encrypted_envelope(payload):
        # Legacy plaintext row: hand back exactly what was stored.
        return dict(payload)
    return _decrypt_envelope_value(payload[ENVELOPE_KEY])

