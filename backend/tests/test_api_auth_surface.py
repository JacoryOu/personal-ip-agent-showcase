# -*- coding: utf-8 -*-
"""Runtime regression tests for the API authentication boundary.

The router-level default (``create_private_router``) is the primary guarantee.
These tests pin the endpoints that were previously reachable anonymously, so a
regression shows up as a failing HTTP status rather than as a silent policy gap.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

#: Endpoints that must answer 401 without a credential.
PRIVATE_ENDPOINTS = [
    ("POST", "/api/images/generate"),
    ("GET", "/api/images/proxy"),
    ("POST", "/api/images/test-connection"),
    ("GET", "/api/dna/skills"),
    ("POST", "/api/drafts/distribute"),
]

#: The single intentionally anonymous endpoint.
PUBLIC_ENDPOINTS = [
    ("GET", "/api/private-domain/templates"),
]


@pytest.fixture
def strict_auth_client():
    """Disable the local-dev fallback so missing credentials really are 401."""
    old_keys = settings.API_KEYS
    old_local = settings.AUTH_LOCAL_DEV_MODE
    old_required = settings.AUTH_REQUIRED
    settings.API_KEYS = ""
    settings.AUTH_LOCAL_DEV_MODE = False
    settings.AUTH_REQUIRED = True
    try:
        with TestClient(app) as client:
            yield client
    finally:
        settings.API_KEYS = old_keys
        settings.AUTH_LOCAL_DEV_MODE = old_local
        settings.AUTH_REQUIRED = old_required


@pytest.mark.parametrize("method,path", PRIVATE_ENDPOINTS)
def test_private_endpoint_requires_auth(strict_auth_client, method, path):
    response = strict_auth_client.request(method, path, json={})
    assert response.status_code == 401, f"{method} {path} returned {response.status_code}"


@pytest.mark.parametrize("method,path", PUBLIC_ENDPOINTS)
def test_public_endpoint_stays_anonymous(strict_auth_client, method, path):
    response = strict_auth_client.request(method, path)
    assert response.status_code == 200, f"{method} {path} returned {response.status_code}"


def test_public_endpoint_registry_matches_application(strict_auth_client):
    """The declared public list and the exposed surface must not drift apart."""
    from scripts.check_api_auth import check

    assert check() == []


def test_public_endpoints_list_stays_short():
    """Adding an anonymous endpoint must be a deliberate, visible decision."""
    from app.api.auth_boundary import PUBLIC_ENDPOINTS

    assert len(PUBLIC_ENDPOINTS) <= 3, (
        "the anonymous surface grew unexpectedly; justify each entry in "
        "app/api/auth_boundary.py and update the architecture docs"
    )
