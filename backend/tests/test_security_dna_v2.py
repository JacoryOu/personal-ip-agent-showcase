"""Security regression tests for the DNA v2 API surface.

Covers: credential-only identity, persona/product ownership, filesystem error
containment, and the unified error contract (error.code + matching request_id).
"""

import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.config import settings
from app.core.db import get_session
from app.main import app

LOCAL_USER_ID = "00000000-0000-0000-0000-000000000001"
FOREIGN_USER_ID = "00000000-0000-0000-0000-0000000000ff"

SECRETS = (
    r"C:\Users\admin\vault\private\secrets.json",
    "https://internal-host-01.corp.internal/v1/chat",
    "sk-live-SUPERSECRET-1234",
    "Traceback (most recent call last)",
    "sqlite:////srv/app/data/private.db",
)


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    import app.models  # noqa: F401  (populate SQLModel metadata)

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as sess:
        yield sess


def _patch_settings():
    return settings


@pytest.fixture(name="local_client")
def local_client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture(name="strict_client")
def strict_client_fixture(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session():
        yield session

    old_local = settings.AUTH_LOCAL_DEV_MODE
    old_required = settings.AUTH_REQUIRED
    old_keys = settings.API_KEYS
    settings.AUTH_LOCAL_DEV_MODE = False
    settings.AUTH_REQUIRED = True
    settings.API_KEYS = "some-other-user=some-other-key"

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
        settings.AUTH_LOCAL_DEV_MODE = old_local
        settings.AUTH_REQUIRED = old_required
        settings.API_KEYS = old_keys


def assert_error_contract(response, status_code: int, code: str) -> dict:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["error"]["code"] == code, body
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    header_request_id = response.headers.get("X-Request-ID")
    assert header_request_id
    assert body["error"]["request_id"] == header_request_id
    return body


def assert_no_internal_text(response) -> None:
    raw = response.text
    for needle in SECRETS:
        assert needle not in raw, f"internal text leaked: {needle!r} in {raw[:400]!r}"
    assert "Traceback" not in raw


def _persona(owner: str, name: str = "p"):
    from app.models.persona import IPPersona

    return IPPersona(id=uuid.uuid4(), user_id=uuid.UUID(owner), name=name)


def _product(owner: str, name: str = "prod"):
    from app.models.product import ProductVault

    return ProductVault(id=uuid.uuid4(), user_id=uuid.UUID(owner), product_name=name)


# --------------------------------------------------------------------------- #
# 1. Authentication required
# --------------------------------------------------------------------------- #

PRIVATE_ROUTES = [
    ("get", "/api/dna/v2/personas"),
    ("get", "/api/dna/v2/products"),
    ("get", "/api/dna/v2/stories"),
    ("get", "/api/dna/v2/timeline"),
]


@pytest.mark.parametrize("method,path", PRIVATE_ROUTES)
def test_private_dna_v2_routes_require_credentials(
    strict_client: TestClient, method, path
):
    if method == "get":
        resp = strict_client.get(path)
    else:
        resp = strict_client.post(path, json={})
    assert_error_contract(resp, 401, "AUTH_REQUIRED")


# --------------------------------------------------------------------------- #
# 2. Foreign user_id is refused, in body and in query
# --------------------------------------------------------------------------- #

def test_foreign_user_id_in_persona_body_is_forbidden(local_client: TestClient):
    resp = local_client.post(
        "/api/dna/v2/personas",
        json={"name": "p", "user_id": FOREIGN_USER_ID},
    )
    assert_error_contract(resp, 403, "FORBIDDEN")


def test_foreign_user_id_in_persona_query_is_forbidden(local_client: TestClient):
    resp = local_client.get(f"/api/dna/v2/personas?user_id={FOREIGN_USER_ID}")
    assert_error_contract(resp, 403, "FORBIDDEN")


def test_foreign_user_id_in_product_body_is_forbidden(local_client: TestClient):
    resp = local_client.post(
        "/api/dna/v2/products",
        json={"product_name": "p", "user_id": FOREIGN_USER_ID},
    )
    assert_error_contract(resp, 403, "FORBIDDEN")


def test_foreign_user_id_in_supersede_body_is_forbidden(local_client: TestClient):
    resp = local_client.post(
        "/api/dna/v2/supersede",
        json={
            "old_trait_id": "x",
            "new_content": "y",
            "evolution_reason": "z",
            "user_id": FOREIGN_USER_ID,
        },
    )
    assert_error_contract(resp, 403, "FORBIDDEN")


# --------------------------------------------------------------------------- #
# 3. Resource ownership
# --------------------------------------------------------------------------- #

def test_patch_persona_owned_by_someone_else_is_forbidden(
    local_client: TestClient, session: Session
):
    persona = _persona(FOREIGN_USER_ID)
    session.add(persona)
    session.commit()

    resp = local_client.patch(
        f"/api/dna/v2/personas/{persona.id}", json={"name": "hijacked"}
    )
    assert_error_contract(resp, 403, "FORBIDDEN")


def test_unknown_persona_is_reported_as_not_found(local_client: TestClient):
    resp = local_client.patch(f"/api/dna/v2/personas/{uuid.uuid4()}", json={"name": "x"})
    assert_error_contract(resp, 404, "NOT_FOUND")


def test_get_product_owned_by_someone_else_is_forbidden(
    local_client: TestClient, session: Session
):
    product = _product(FOREIGN_USER_ID)
    session.add(product)
    session.commit()

    resp = local_client.get(f"/api/dna/v2/products/{product.id}")
    assert_error_contract(resp, 403, "FORBIDDEN")


def test_unknown_product_is_reported_as_not_found(local_client: TestClient):
    resp = local_client.get(f"/api/dna/v2/products/{uuid.uuid4()}")
    assert_error_contract(resp, 404, "NOT_FOUND")


def test_delete_product_owned_by_someone_else_is_forbidden(
    local_client: TestClient, session: Session
):
    product = _product(FOREIGN_USER_ID)
    session.add(product)
    session.commit()

    resp = local_client.delete(f"/api/dna/v2/products/{product.id}")
    assert_error_contract(resp, 403, "FORBIDDEN")


# --------------------------------------------------------------------------- #
# 4. Internal errors are collapsed, not echoed
# --------------------------------------------------------------------------- #

LEAKING = RuntimeError(
    "upstream failed: https://internal-host-01.corp.internal/v1/chat "
    "key=sk-live-SUPERSECRET-1234 file=C:\\Users\\admin\\vault\\private\\secrets.json"
)


def test_persona_extraction_degrades_without_echoing_engine_errors(
    local_client: TestClient, monkeypatch
):
    """The upstream failure is a *degradation*, not an error report.

    The route intentionally falls back to a heuristic persona so the caller
    still gets a usable payload. The guarantee under test is therefore that the
    SDK/transport text never reaches the client, not that a 5xx is raised.
    """

    class BoomGateway:
        def __getattr__(self, name):
            def boom(*args, **kwargs):
                raise LEAKING

            return boom

    monkeypatch.setattr(
        "app.api.dna_v2.get_model_gateway", lambda *a, **k: BoomGateway()
    )

    resp = local_client.post(
        "/api/dna/v2/personas/extract-from-text", json={"text": "some long text"}
    )

    assert resp.status_code == 200, resp.text
    assert_no_internal_text(resp)


def test_product_extraction_does_not_echo_engine_errors(
    local_client: TestClient, monkeypatch
):
    class BoomGateway:
        def __getattr__(self, name):
            def boom(*args, **kwargs):
                raise LEAKING

            return boom

    monkeypatch.setattr(
        "app.api.dna_v2.get_model_gateway", lambda *a, **k: BoomGateway()
    )

    resp = local_client.post(
        "/api/dna/v2/products/extract-from-text", json={"text": "some long text"}
    )

    assert_error_contract(resp, 500, "INTERNAL_ERROR")
    assert_no_internal_text(resp)


def test_product_upload_does_not_echo_filesystem_paths(
    local_client: TestClient, monkeypatch
):
    from app.api import dna_v2

    def boom(*args, **kwargs):
        raise OSError(
            "cannot write C:\\Users\\admin\\vault\\private\\uploads\\products\\x.png"
        )

    monkeypatch.setattr(dna_v2.PRODUCT_UPLOAD_DIR.__class__, "mkdir", boom)

    resp = local_client.post(
        "/api/dna/v2/products/upload-image",
        files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")},
    )

    assert_error_contract(resp, 500, "INTERNAL_ERROR")
    assert_no_internal_text(resp)
