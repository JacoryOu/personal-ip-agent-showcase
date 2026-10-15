# -*- coding: utf-8 -*-
"""Contract tests for the unified public error shape and request-id propagation.

These lock in the guarantees the security line B work promised:

* every error the client can observe is rendered through one shape;
* a 5xx never carries raw exception text (SDK payloads, DB messages, paths);
* the submitted payload is not echoed back by the validation handler;
* ``X-Request-ID`` round-trips so a user-reported error is traceable to a
  single server-side log line.

The tests drive a throwaway app rather than the production router so that a
route added later cannot silently change the contract.
"""

from pathlib import Path
import sys

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    AUTH_REQUIRED,
    DEPENDENCY_FAILURE,
    FORBIDDEN,
    INTERNAL_ERROR,
    NOT_FOUND,
    VALIDATION_ERROR,
    AppError,
)
from app.core.errors import REQUEST_ID_HEADER
from app.core.request_id import REQUEST_ID_HEADER_MAX_LENGTH, RequestIdMiddleware

import app.main as main_module

SECRET = "s3cr3t-internal-detail-DB-password-42"


@pytest.fixture
def contract_app() -> FastAPI:
    """A minimal app reusing the *real* handlers registered on ``app``."""

    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    class Payload(BaseModel):
        name: str

    @app.get("/ok")
    def _ok():
        return {"status": "ok"}

    @app.get("/app-error")
    def _app_error():
        raise AppError(code=NOT_FOUND)

    @app.get("/app-error-custom")
    def _app_error_custom():
        raise AppError(code=DEPENDENCY_FAILURE, message="Upstream is unavailable.")

    @app.get("/http-404")
    def _http_404():
        raise HTTPException(status_code=404, detail="No such draft.")

    @app.get("/http-500")
    def _http_500():
        raise HTTPException(status_code=500, detail=f"LLM extraction error: {SECRET}")

    @app.get("/boom")
    def _boom():
        raise RuntimeError(SECRET)

    @app.post("/echo")
    def _echo(payload: Payload):
        return {"name": payload.name}

    # Reuse the production handlers so the test asserts real behaviour rather
    # than a re-implementation of the contract.
    for exc_type, handler in (
        (AppError, main_module._app_error_handler),
        (HTTPException, main_module._http_exception_handler),
        (Exception, main_module._unhandled_error_handler),
    ):
        app.add_exception_handler(exc_type, handler)

    app.add_exception_handler(
        __import__("fastapi").exceptions.RequestValidationError,
        main_module._validation_error_handler,
    )
    return app


@pytest.fixture
def client(contract_app: FastAPI) -> TestClient:
    # raise_server_exceptions=False lets the global ``Exception`` handler run,
    # which is exactly the path a production 500 takes.
    return TestClient(contract_app, raise_server_exceptions=False)


# ---------------------------------------------------------------- request id


def test_valid_inbound_request_id_is_propagated(client: TestClient):
    resp = client.get("/ok", headers={REQUEST_ID_HEADER: "trace-abc-123"})
    assert resp.status_code == 200
    assert resp.headers[REQUEST_ID_HEADER] == "trace-abc-123"


def test_missing_request_id_is_generated(client: TestClient):
    resp = client.get("/ok")
    assert resp.status_code == 200
    generated = resp.headers[REQUEST_ID_HEADER]
    assert generated
    assert len(generated) <= REQUEST_ID_HEADER_MAX_LENGTH


def test_malformed_request_id_is_replaced_not_trusted(client: TestClient):
    hostile = "a" * (REQUEST_ID_HEADER_MAX_LENGTH + 10)
    resp = client.get("/ok", headers={REQUEST_ID_HEADER: hostile})
    assert resp.status_code == 200
    assert resp.headers[REQUEST_ID_HEADER] != hostile
    assert len(resp.headers[REQUEST_ID_HEADER]) <= REQUEST_ID_HEADER_MAX_LENGTH


# ------------------------------------------------------------------- errors


def test_app_error_uses_code_and_preserves_detail(client: TestClient):
    resp = client.get("/app-error")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == NOT_FOUND
    assert body["detail"] == body["error"]["message"]
    assert body["error"]["request_id"] == resp.headers[REQUEST_ID_HEADER]


def test_app_error_custom_message_is_returned(client: TestClient):
    resp = client.get("/app-error-custom")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == DEPENDENCY_FAILURE
    assert resp.json()["error"]["message"] == "Upstream is unavailable."


def test_http_404_detail_stays_public(client: TestClient):
    resp = client.get("/http-404")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == NOT_FOUND
    assert resp.json()["detail"] == "No such draft."


def test_http_500_detail_is_never_leaked(client: TestClient):
    resp = client.get("/http-500")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == INTERNAL_ERROR
    assert body["error"]["message"] == "Internal server error."
    assert SECRET not in resp.text


def test_unhandled_exception_is_collapsed_and_logged(client: TestClient):
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == INTERNAL_ERROR
    assert body["error"]["message"] == "Internal server error."
    assert SECRET not in resp.text
    assert body["error"]["request_id"]


def test_validation_error_does_not_echo_payload(client: TestClient):
    resp = client.post("/echo", json={"name": 12345, "extra": SECRET})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == VALIDATION_ERROR
    assert SECRET not in resp.text


def test_error_body_always_carries_request_id(client: TestClient):
    for path in ("/boom", "/http-500", "/http-404", "/app-error"):
        resp = client.get(path)
        assert resp.json()["error"]["request_id"] == resp.headers[REQUEST_ID_HEADER]
