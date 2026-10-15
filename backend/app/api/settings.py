# -*- coding: utf-8 -*-
"""Compatibility facade for the Settings API.

The SSRF guard and provider-normalisation helpers now live in
`app.api.settings_common`; the route handlers live in
`app.api.settings_routes`. Both the `settings` blueprint name and every
public symbol previously importable from this module are preserved.
"""

import socket  # noqa: F401  (re-exported: tests patch app.api.settings.socket)
from openai import AsyncOpenAI  # noqa: F401  (re-exported for monkeypatching)

from app.api.settings_common import (  # noqa: F401
    _ALLOWED_SCHEMES as _ALLOWED_SCHEMES,
    BASE_URL_REJECTED_MESSAGE,
    CONNECTION_TEST_FAILED_MESSAGE,
    ConnectionTestRequest,
    ConnectionTestResponse,
    LOCAL_PROVIDER_HOSTS,
    LOCAL_PROVIDER_PORTS,
    _BaseUrlRejected,
    _check_ip,
    _safe_host,
    is_local_provider_url,
    normalize_model_for_provider,
    router,
    validate_provider_base_url,
)
from app.api.settings_routes import (  # noqa: F401
    get_current_settings,
    test_connection,
)

__all__ = [
    "router",
    "ConnectionTestRequest",
    "ConnectionTestResponse",
    "test_connection",
    "get_current_settings",
    "validate_provider_base_url",
    "is_local_provider_url",
    "normalize_model_for_provider",
    "CONNECTION_TEST_FAILED_MESSAGE",
    "BASE_URL_REJECTED_MESSAGE",
]
