# -*- coding: utf-8 -*-
"""Compatibility facade for the Platforms API.

Ownership helpers and shared imports live in `app.api.platforms_common`; the
route handlers live in `app.api.platforms_routes`. The `platforms` blueprint
name, every route path and every previously importable public symbol are preserved.
"""

from app.api.platforms_common import *  # noqa: F401,F403
from app.api.platforms_common import (  # noqa: F401
    AccountFeedResponse,
    AppError,
    BatchIngestRequest,
    BatchIngestResponse,
    BenchmarkAccountCreateRequest,
    BenchmarkAccountResponse,
    BenchmarkAccountUpdateRequest,
    CredentialResponse,
    ManualCookieRequest,
    NOT_FOUND,
    QRLoginSimulateConfirmRequest,
    QRLoginStartRequest,
    QRLoginStartResponse,
    QRLoginStatusResponse,
    VALIDATION_ERROR,
    _get_owned_account,
    _get_owned_credential,
    _resolve_account,
)

from app.api.platforms_routes import (  # noqa: F401
    batch_ingest_posts,
    check_credential_validity,
    check_qr_status,
    create_account,
    delete_account,
    delete_credential,
    get_account_feed,
    get_credential,
    list_accounts,
    list_credentials,
    save_manual_cookies,
    simulate_confirm_qr,
    start_qr_login,
    sync_account_feed,
)

__all__ = [
    'AccountFeedResponse',
    'AppError',
    'BatchIngestRequest',
    'BatchIngestResponse',
    'BenchmarkAccountCreateRequest',
    'BenchmarkAccountResponse',
    'BenchmarkAccountUpdateRequest',
    'CredentialResponse',
    'ManualCookieRequest',
    'NOT_FOUND',
    'QRLoginSimulateConfirmRequest',
    'QRLoginStartRequest',
    'QRLoginStartResponse',
    'QRLoginStatusResponse',
    'VALIDATION_ERROR',
    '_get_owned_account',
    '_get_owned_credential',
    '_resolve_account',
    'batch_ingest_posts',
    'check_credential_validity',
    'check_qr_status',
    'create_account',
    'delete_account',
    'delete_credential',
    'get_account_feed',
    'get_credential',
    'list_accounts',
    'list_credentials',
    'router',
    'save_manual_cookies',
    'simulate_confirm_qr',
    'start_qr_login',
    'sync_account_feed',
]
