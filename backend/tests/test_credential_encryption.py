# -*- coding: utf-8 -*-
"""Credential-at-rest encryption behaviour."""
import json
import uuid
from pathlib import Path
import sys

import pytest
from sqlmodel import Session, select

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.crypto import secret_box, is_encrypted
from app.core.db import engine, init_db
from app.models.credential import PlatformAccountCredential
from app.services.credential_service import CredentialService


SECRETS = {"web_session": "SESSION-VALUE", "a1": "A1-VALUE", "token": "TOKEN-VALUE"}


@pytest.fixture(autouse=True)
def master_key(monkeypatch):
    monkeypatch.setenv(secret_box.MASTER_KEY_ENV, "credential-test-master-key")
    secret_box.reset_master_key_cache()
    yield
    secret_box.reset_master_key_cache()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.fixture
def sess():
    with Session(engine) as s:
        yield s


def _uid():
    return uuid.UUID(int=uuid.uuid4().int)


def _make_cred(sess, cookies, identifier=None):
    cred = PlatformAccountCredential(
        user_id=_uid(),
        platform="wechat",
        account_identifier=identifier or f"acct-{uuid.uuid4().hex[:8]}",
        status="active",
        cookies=cookies,
    )
    sess.add(cred)
    sess.commit()
    sess.refresh(cred)
    return cred


def test_manual_cookie_write_is_encrypted_at_rest(sess):
    result = CredentialService.save_manual_cookies(
        platform="wechat",
        account_identifier="enc-1",
        cookies_input="web_session=SESSION-VALUE; a1=A1-VALUE; token=TOKEN-VALUE",
        user_id=_uid(),
        session=sess,
    )
    cred_id = result.id

    row = sess.exec(
        select(PlatformAccountCredential).where(
            PlatformAccountCredential.id == uuid.UUID(cred_id)
        )
    ).one()
    assert is_encrypted(row.cookies)

    blob = json.dumps(row.cookies)
    for needle in ("SESSION-VALUE", "A1-VALUE", "TOKEN-VALUE", "web_session"):
        assert needle not in blob


def test_load_cookies_roundtrips_plaintext(sess):
    result = CredentialService.save_manual_cookies(
        platform="wechat",
        account_identifier="enc-2",
        cookies_input="web_session=SESSION-VALUE; token=TOKEN-VALUE",
        user_id=_uid(),
        session=sess,
    )
    cred = sess.get(PlatformAccountCredential, uuid.UUID(result.id))

    plaintext = CredentialService.load_cookies(cred)
    assert plaintext["web_session"] == "SESSION-VALUE"
    assert plaintext["token"] == "TOKEN-VALUE"


def test_serialize_credential_never_returns_plaintext(sess):
    result = CredentialService.save_manual_cookies(
        platform="wechat",
        account_identifier="enc-3",
        cookies_input="web_session=SESSION-VALUE; token=TOKEN-VALUE",
        user_id=_uid(),
        session=sess,
    )
    cred = sess.get(PlatformAccountCredential, uuid.UUID(result.id))
    payload = CredentialService.serialize_credential(cred).model_dump()

    assert payload["has_cookies"] is True
    assert set(payload["cookie_keys"]) == {"web_session", "token"}
    assert "SESSION-VALUE" not in json.dumps(payload)
    assert "TOKEN-VALUE" not in json.dumps(payload)


def test_legacy_plaintext_row_is_readable(sess):
    cred = _make_cred(sess, dict(SECRETS))
    assert not is_encrypted(cred.cookies)

    plaintext = CredentialService.load_cookies(cred)
    assert plaintext == SECRETS


def test_legacy_plaintext_row_is_lazily_migrated(sess):
    cred = _make_cred(sess, dict(SECRETS))

    plaintext = CredentialService.load_cookies_with_migration(cred, sess)
    assert plaintext == SECRETS

    sess.expire_all()
    refreshed = sess.get(PlatformAccountCredential, cred.id)
    assert is_encrypted(refreshed.cookies)
    assert CredentialService.load_cookies(refreshed) == SECRETS

    blob = json.dumps(refreshed.cookies)
    assert "SESSION-VALUE" not in blob
    # Unrelated columns must survive the targeted UPDATE.
    assert refreshed.platform == "wechat"
    assert refreshed.account_identifier == cred.account_identifier


def test_missing_master_key_fails_closed_on_write(sess, monkeypatch):
    monkeypatch.setenv(secret_box.MASTER_KEY_ENV, "")
    secret_box.reset_master_key_cache()
    try:
        CredentialService._store_cookies({"token": "x"})
    except secret_box.SecretKeyMissingError:
        pass
    else:
        pytest.fail("expected the write to fail closed without a master key")


def test_load_cookies_raises_when_envelope_cannot_be_decrypted(sess):
    cred = _make_cred(sess, {"__secret_envelope__": "v1:not-a-valid-fernet-token"})

    with pytest.raises(secret_box.SecretBoxError):
        CredentialService.load_cookies(cred)


def test_load_cookies_raises_after_master_key_changes(sess, monkeypatch):
    cred = _make_cred(
        sess, CredentialService._store_cookies({"token": "v"})
    )

    monkeypatch.setenv(secret_box.MASTER_KEY_ENV, "a-completely-different-master-key")
    secret_box.reset_master_key_cache()
    with pytest.raises(secret_box.SecretBoxError):
        CredentialService.load_cookies(cred)


