"""Regression tests for CORS hardening and the /uploads static-mount toggle.

Covers:
- production drops the localhost origin regex and localhost origins
- allow_methods / allow_headers are explicit lists, never "*"
- /uploads is not mounted when EXPOSE_UPLOADS is false
- /uploads is mounted when EXPOSE_UPLOADS is true
"""

import importlib

import pytest

from app.core.config import settings


def _reload_main():
    """Import a fresh app.main module with the current settings values."""
    import app.main as main_module

    return importlib.reload(main_module)


def _cors_middleware_options(main_module):
    for middleware in main_module.app.user_middleware:
        if middleware.cls is not None and middleware.cls.__name__ == "CORSMiddleware":
            return middleware.kwargs
    raise AssertionError("CORSMiddleware is not installed on the app")


def _mounted_paths(main_module):
    return [route.path for route in main_module.app.routes if getattr(route, "name", None) == "uploads"]


def test_production_drops_localhost_origin_regex():
    old_env = settings.ENVIRONMENT
    old_regex = settings.CORS_ALLOW_LOCALHOST_REGEX
    settings.ENVIRONMENT = "production"
    settings.CORS_ALLOW_LOCALHOST_REGEX = True
    try:
        main_module = _reload_main()
    finally:
        settings.ENVIRONMENT = old_env
        settings.CORS_ALLOW_LOCALHOST_REGEX = old_regex

    options = _cors_middleware_options(main_module)
    assert options.get("allow_origin_regex") is None
    for origin in options.get("allow_origins", []):
        assert "localhost" not in origin
        assert "127.0.0.1" not in origin


def test_development_keeps_localhost_origin_regex():
    old_env = settings.ENVIRONMENT
    settings.ENVIRONMENT = "development"
    try:
        main_module = _reload_main()
    finally:
        settings.ENVIRONMENT = old_env

    options = _cors_middleware_options(main_module)
    assert options.get("allow_origin_regex") is not None


def test_methods_and_headers_are_explicit_allowlists():
    main_module = _reload_main()
    options = _cors_middleware_options(main_module)

    methods = options.get("allow_methods")
    headers = options.get("allow_headers")

    assert methods and "*" not in methods
    assert {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"} <= set(methods)

    assert headers and "*" not in headers
    assert {"Content-Type", "Authorization"} <= set(headers)


def test_origins_never_contains_wildcard_with_credentials():
    main_module = _reload_main()
    options = _cors_middleware_options(main_module)

    assert options.get("allow_credentials") is True
    assert "*" not in options.get("allow_origins", [])


def test_uploads_not_mounted_when_disabled():
    old = settings.EXPOSE_UPLOADS
    settings.EXPOSE_UPLOADS = False
    try:
        main_module = _reload_main()
    finally:
        settings.EXPOSE_UPLOADS = old

    assert _mounted_paths(main_module) == []


def test_uploads_mounted_when_enabled():
    old = settings.EXPOSE_UPLOADS
    settings.EXPOSE_UPLOADS = True
    try:
        main_module = _reload_main()
    finally:
        settings.EXPOSE_UPLOADS = old

    assert _mounted_paths(main_module) == ["/uploads"]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
