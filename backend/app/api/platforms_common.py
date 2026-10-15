import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session, select

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.auth.ownership import ensure_same_user, ensure_uuid_param, not_found
from app.core.db import get_session
from app.core.errors import (
    NOT_FOUND,
    VALIDATION_ERROR,
    AppError,
)
from app.models.benchmark_account import BenchmarkAccount
from app.models.credential import PlatformAccountCredential
from app.schemas.platform_schemas import (
    AccountFeedResponse,
    BatchIngestRequest,
    BatchIngestResponse,
    BenchmarkAccountCreateRequest,
    BenchmarkAccountResponse,
    BenchmarkAccountUpdateRequest,
    CredentialResponse,
    ManualCookieRequest,
    QRLoginSimulateConfirmRequest,
    QRLoginStartRequest,
    QRLoginStartResponse,
    QRLoginStatusResponse,
)
from app.services.credential_service import CredentialService
from app.services.platform_crawler_service import PlatformCrawlerService

router = APIRouter(tags=["platforms"])


# ==============================================================================
# Ownership helpers (IDOR protection)
# ==============================================================================

def _resolve_account(session: Session, account_id: str) -> Optional[BenchmarkAccount]:
    """Resolve a benchmark account by primary key or by platform account id.

    Mirrors the resolution order used by ``PlatformCrawlerService`` so the
    ownership check sees exactly the row the service would act on.
    """
    try:
        parsed = uuid.UUID(str(account_id))
    except (ValueError, AttributeError, TypeError):
        parsed = None
    if parsed is not None:
        account = session.get(BenchmarkAccount, parsed)
        if account:
            return account
    return session.exec(
        select(BenchmarkAccount).where(
            BenchmarkAccount.account_id == str(account_id).strip()
        )
    ).first()


def _get_owned_account(
    session: Session,
    account_id: str,
    current_user: AuthenticatedUser,
) -> BenchmarkAccount:
    """Load a benchmark account only when the caller owns it.

    A missing account and an account owned by somebody else both raise 404 so
    the API never leaks the existence of another user's resource.
    """
    account = _resolve_account(session, account_id)
    if not account:
        raise not_found(f"Benchmark account '{account_id}' not found.")
    ensure_same_user(
        current_user.id,
        account.user_id,
        f"Benchmark account '{account_id}' not found.",
    )
    return account


def _get_owned_credential(
    session: Session,
    credential_id: str,
    current_user: AuthenticatedUser,
) -> PlatformAccountCredential:
    """Load a credential only when the caller owns it (404 otherwise)."""
    cred = None
    try:
        parsed = uuid.UUID(str(credential_id))
        cred = session.get(PlatformAccountCredential, parsed)
    except (ValueError, AttributeError, TypeError):
        # The service historically also accepted a platform name; keep that
        # resolution but still enforce ownership on whatever it resolves to.
        cred = session.exec(
            select(PlatformAccountCredential).where(
                PlatformAccountCredential.platform == str(credential_id).lower().strip()
            )
        ).first()
    if not cred:
        raise not_found(f"Credential '{credential_id}' not found.")
    ensure_same_user(
        current_user.id,
        cred.user_id,
        f"Credential '{credential_id}' not found.",
    )
    return cred


# ==============================================================================
# Platform Authorization & Credential Management
# ==============================================================================
