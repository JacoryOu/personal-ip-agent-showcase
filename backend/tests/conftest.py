"""Shared pytest fixtures.

Authentication note
-------------------
The API now derives identity from a credential ("Authorization: Bearer" or
"X-API-Key"). Most existing tests exercise handlers without any credential,
so this fixture *explicitly* enables the local single-user development mode for
the duration of each test. This keeps production code free of an
unconditional fallback while not forcing every unrelated test to thread a
header through.
"""

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _explicit_local_dev_auth_mode():
    """Opt in to the local-dev identity for tests that send no credential."""
    old_local = settings.AUTH_LOCAL_DEV_MODE
    old_required = settings.AUTH_REQUIRED
    old_keys = settings.API_KEYS

    settings.AUTH_LOCAL_DEV_MODE = True
    settings.AUTH_REQUIRED = False
    settings.API_KEYS = ""
    try:
        yield
    finally:
        settings.AUTH_LOCAL_DEV_MODE = old_local
        settings.AUTH_REQUIRED = old_required
        settings.API_KEYS = old_keys


@pytest.fixture(autouse=True)
def _test_only_credential_master_key():
    """Provide a deterministic, test-only credential master key.

    Production code refuses to write secrets without PLATFORM_CREDENTIAL_MASTER_KEY.
    Several API tests legitimately write credentials, so the suite opts in
    explicitly here rather than weakening the production default. Tests that
    assert the fail-closed behaviour override the value via monkeypatch.
    """
    import os

    from app.core.crypto import secret_box

    if os.environ.get(secret_box.MASTER_KEY_ENV):
        yield
        return

    os.environ[secret_box.MASTER_KEY_ENV] = "pytest-only-credential-master-key"
    secret_box.reset_master_key_cache()
    try:
        yield
    finally:
        os.environ.pop(secret_box.MASTER_KEY_ENV, None)
        secret_box.reset_master_key_cache()
