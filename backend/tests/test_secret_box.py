# -*- coding: utf-8 -*-
"""Tests for the Fernet credential secret box."""
from pathlib import Path
import sys

import pytest

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.crypto import (
    ENVELOPE_KEY,
    SecretBoxError,
    SecretKeyMissingError,
    decrypt_mapping,
    encrypt_mapping,
    is_encrypted,
)
from app.core.crypto import secret_box

KEY_A = "unit-test-master-key-a"
KEY_B = "unit-test-master-key-b"


@pytest.fixture(autouse=True)
def clean_key(monkeypatch):
    monkeypatch.setenv(secret_box.MASTER_KEY_ENV, KEY_A)
    secret_box.reset_master_key_cache()
    yield
    secret_box.reset_master_key_cache()


def test_round_trip():
    payload = {"web_session": "abc123", "a1": "zzz", "unicode": "值"}
    sealed = encrypt_mapping(payload)

    assert is_encrypted(sealed)
    assert list(sealed.keys()) == [ENVELOPE_KEY]
    assert sealed[ENVELOPE_KEY].startswith("v1:")
    # Ciphertext must not leak any plaintext value.
    blob = repr(sealed)
    for secret in payload.values():
        assert secret not in blob

    assert decrypt_mapping(sealed) == payload


def test_ciphertext_is_nondeterministic():
    payload = {"token": "same-value"}
    assert encrypt_mapping(payload)[ENVELOPE_KEY] != encrypt_mapping(payload)[ENVELOPE_KEY]


def test_empty_and_none():
    assert encrypt_mapping({}) == {}
    assert encrypt_mapping(None) == {}
    assert decrypt_mapping(None) == {}
    assert decrypt_mapping({}) == {}


def test_legacy_plaintext_is_returned_unchanged():
    legacy = {"web_session": "plain", "legacy": True}
    assert is_encrypted(legacy) is False
    assert decrypt_mapping(legacy) == legacy


def test_missing_key_fails_closed(monkeypatch):
    monkeypatch.delenv(secret_box.MASTER_KEY_ENV, raising=False)
    secret_box.reset_master_key_cache()
    monkeypatch.setattr("app.core.config.settings.PLATFORM_CREDENTIAL_MASTER_KEY", None, raising=False)

    with pytest.raises(SecretKeyMissingError):
        encrypt_mapping({"token": "value"})


def test_tampered_ciphertext_fails():
    sealed = encrypt_mapping({"token": "value"})
    tampered = {ENVELOPE_KEY: sealed[ENVELOPE_KEY][:-6] + "AAAAAA"}
    with pytest.raises(SecretBoxError):
        decrypt_mapping(tampered)


def test_unknown_version_is_rejected():
    sealed = encrypt_mapping({"token": "value"})
    with pytest.raises(SecretBoxError):
        decrypt_mapping({ENVELOPE_KEY: "v99:" + sealed[ENVELOPE_KEY].split(":", 1)[1]})


def test_other_key_cannot_decrypt(monkeypatch):
    sealed = encrypt_mapping({"token": "value"})
    monkeypatch.setenv(secret_box.MASTER_KEY_ENV, KEY_B)
    secret_box.reset_master_key_cache()
    with pytest.raises(SecretBoxError):
        decrypt_mapping(sealed)


def test_raw_fernet_key_is_accepted(monkeypatch):
    import base64 as _b64

    raw = _b64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef")
    monkeypatch.setenv(secret_box.MASTER_KEY_ENV, raw.decode())
    secret_box.reset_master_key_cache()
    sealed = encrypt_mapping({"token": "value"})
    assert decrypt_mapping(sealed) == {"token": "value"}


def test_encrypt_is_idempotent_on_envelope():
    sealed = encrypt_mapping({"token": "value"})
    assert encrypt_mapping(sealed) == sealed


def test_non_dict_payload_rejected():
    with pytest.raises(SecretBoxError):
        decrypt_mapping(["not", "a", "dict"])
