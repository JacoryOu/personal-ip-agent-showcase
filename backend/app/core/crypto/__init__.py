"""Symmetric encryption helpers for at-rest secrets (platform credentials).

Design constraints
------------------
* No new database columns may be introduced by this module. Ciphertext must be
  stored inside the existing JSON column, so every helper here works on
  ``Dict[str, Any]`` payloads rather than on a schema type.
* Envelope format is versioned so future key rotation / algorithm changes can
  migrate old plaintext or old envelopes without guessing.

Envelope (stored as a JSON object with exactly one reserved key)::

    {"__secret_envelope__": "v1:<fernet-token>"}

Plaintext (legacy, still readable) is any dict that does not carry the reserved
key. Legacy rows are migrated lazily on first successful decrypt-and-write.
"""

from .secret_box import (
    ENVELOPE_KEY,
    SecretBoxError,
    SecretKeyMissingError,
    decrypt_mapping,
    encrypt_mapping,
    is_encrypted,
    is_encrypted_envelope,
    master_key_configured,
)

__all__ = [
    "ENVELOPE_KEY",
    "SecretBoxError",
    "SecretKeyMissingError",
    "decrypt_mapping",
    "encrypt_mapping",
    "is_encrypted",
    "is_encrypted_envelope",
    "master_key_configured",
]
