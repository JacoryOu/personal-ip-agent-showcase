import uuid
from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, Query, status
from sqlmodel import Session, select

from app.api.platforms_common import (
    AccountFeedResponse,
    BatchIngestRequest,
    BatchIngestResponse,
    BenchmarkAccount,
    BenchmarkAccountCreateRequest,
    BenchmarkAccountResponse,
    BenchmarkAccountUpdateRequest,
    CredentialResponse,
    ManualCookieRequest,
    QRLoginSimulateConfirmRequest,
    QRLoginStartRequest,
    QRLoginStartResponse,
    QRLoginStatusResponse,
    _get_owned_account,
    _get_owned_credential,
    _resolve_account,
    router,
)
from app.core.auth import AuthenticatedUser, get_current_user
from app.core.auth.ownership import ensure_same_user, ensure_uuid_param, not_found
from app.core.db import get_session
from app.core.errors import (
    NOT_FOUND,
    VALIDATION_ERROR,
    AppError,
)
from app.models.credential import PlatformAccountCredential
from app.services.credential_service import CredentialService
from app.services.platform_crawler_service import PlatformCrawlerService


@router.post("/credentials/qr/start", response_model=QRLoginStartResponse)
def start_qr_login(
    payload: QRLoginStartRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Starts a QR login session for WeChat Official Platform, Xiaohongshu, or Zhihu."""
    try:
        return CredentialService.start_qr_login(
            platform=payload.platform,
            user_id=current_user.id,
            session=session,
        )
    except ValueError:
        raise AppError(
            code=VALIDATION_ERROR,
            message="The QR login session could not be started for this platform.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.get("/credentials/qr/status", response_model=QRLoginStatusResponse)
def check_qr_status(
    session_key: str = Query(..., description="The session key returned by /qr/start"),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Polls the status of an ongoing QR login session."""
    return CredentialService.check_qr_login_status(session_key=session_key, session=session)


@router.post("/credentials/qr/simulate-confirm", response_model=Dict[str, Any])
def simulate_confirm_qr(
    payload: QRLoginSimulateConfirmRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Simulates mobile QR scanning confirmation for test automation and mock environments."""
    success = CredentialService.simulate_confirm_qr(
        session_key=payload.session_key,
        account_identifier=payload.account_identifier,
    )
    if not success:
        raise AppError(
            code=NOT_FOUND,
            message="Session key not found or expired.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return {"success": True, "message": "Simulated QR code confirmation successfully."}


@router.post("/credentials/manual", response_model=CredentialResponse)
def save_manual_cookies(
    payload: ManualCookieRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CredentialResponse:
    """Manually saves or updates platform session cookies/tokens (e.g. token, a1, web_session, z_c0)."""
    try:
        return CredentialService.save_manual_cookies(
            platform=payload.platform,
            cookies_input=payload.cookies,
            account_identifier=payload.account_identifier,
            user_id=current_user.id,
            session=session,
        )
    except ValueError:
        raise AppError(
            code=VALIDATION_ERROR,
            message="The supplied platform credentials were rejected.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.get("/credentials", response_model=List[CredentialResponse])
def list_credentials(
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[CredentialResponse]:
    """Lists all stored platform authorization credentials for the caller."""
    return CredentialService.list_credentials(user_id=current_user.id, session=session)


@router.get("/credentials/{platform}", response_model=Optional[CredentialResponse])
def get_credential(
    platform: str,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Optional[CredentialResponse]:
    """Retrieves credential for a specific platform."""
    cred = CredentialService.get_credential(platform, user_id=current_user.id, session=session)
    if not cred:
        return None
    return CredentialService.serialize_credential(cred)


@router.post("/credentials/{platform}/check", response_model=Dict[str, Any])
def check_credential_validity(
    platform: str,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Validates session health and freshness for the specified platform."""
    return CredentialService.check_credential_validity(platform, user_id=current_user.id, session=session)


@router.delete("/credentials/{credential_id}")
def delete_credential(
    credential_id: str,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Revokes and removes a platform credential owned by the caller."""
    _get_owned_credential(session, credential_id, current_user)
    success = CredentialService.delete_credential(credential_id, session=session)
    if not success:
        raise not_found(f"Credential '{credential_id}' not found.")
    return {"success": True, "message": "Credential revoked successfully."}


# ==============================================================================
# Benchmark Accounts Monitoring
# ==============================================================================

@router.get("/accounts", response_model=List[BenchmarkAccountResponse])
def list_accounts(
    platform: Optional[str] = Query(default=None, description="Filter by 'wechat', 'xhs', 'zhihu'"),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[BenchmarkAccountResponse]:
    """Lists tracked benchmark accounts with optional platform filtering."""
    return PlatformCrawlerService.list_benchmark_accounts(
        platform=platform,
        user_id=current_user.id,
        session=session,
    )


@router.post("/accounts", response_model=BenchmarkAccountResponse)
def create_account(
    payload: BenchmarkAccountCreateRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> BenchmarkAccountResponse:
    """Adds a new benchmark author/account to monitor."""
    return PlatformCrawlerService.create_benchmark_account(
        platform=payload.platform,
        account_name=payload.account_name,
        account_id=payload.account_id,
        home_url=payload.home_url,
        avatar_url=payload.avatar_url,
        bio=payload.bio,
        user_id=current_user.id,
        session=session,
    )


@router.delete("/accounts/{account_id}")
def delete_account(
    account_id: str,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Stops monitoring and deletes a benchmark account owned by the caller."""
    _get_owned_account(session, account_id, current_user)
    success = PlatformCrawlerService.delete_benchmark_account(account_id, session=session)
    if not success:
        raise not_found(f"Benchmark account '{account_id}' not found.")
    return {"success": True, "message": "Account removed from monitoring."}


@router.get("/accounts/{account_id}/feed", response_model=AccountFeedResponse)
def get_account_feed(
    account_id: str,
    sort_by: str = Query(default="latest", description="'latest' or 'hot'"),
    limit: int = Query(default=20, ge=1, le=50),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Fetches recent posts/articles from a benchmark account owned by the caller."""
    _get_owned_account(session, account_id, current_user)
    try:
        return PlatformCrawlerService.fetch_account_posts(
            account_id=account_id,
            sort_by=sort_by,
            limit=limit,
            user_id=current_user.id,
            session=session,
        )
    except ValueError:
        # The service raises ValueError for an unresolvable account id. Its
        # message quotes caller-supplied data only, but it is still not echoed:
        # the public contract owns the wording.
        raise AppError(
            code=NOT_FOUND,
            message="Benchmark account not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


@router.post("/accounts/{account_id}/sync", response_model=AccountFeedResponse)
def sync_account_feed(
    account_id: str,
    sort_by: str = Query(default="latest"),
    limit: int = Query(default=20),
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Triggers an on-demand sync of posts from a benchmark account owned by the caller."""
    _get_owned_account(session, account_id, current_user)
    try:
        return PlatformCrawlerService.fetch_account_posts(
            account_id=account_id,
            sort_by=sort_by,
            limit=limit,
            user_id=current_user.id,
            session=session,
        )
    except ValueError:
        # The service raises ValueError for an unresolvable account id. Its
        # message quotes caller-supplied data only, but it is still not echoed:
        # the public contract owns the wording.
        raise AppError(
            code=NOT_FOUND,
            message="Benchmark account not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


# ==============================================================================
# Batch Collection & Structural Blueprint Extraction
# ==============================================================================

@router.post("/batch-ingest", response_model=BatchIngestResponse)
def batch_ingest_posts(
    payload: BatchIngestRequest,
    session: Session = Depends(get_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Batch imports selected articles into MaterialVault and performs structural blueprint extraction."""
    return PlatformCrawlerService.batch_collect_and_deconstruct(
        items=payload.items,
        extract_blueprint=payload.extract_blueprint,
        category=payload.category or "benchmark",
        tags=payload.tags,
        user_id=current_user.id,
        session=session,
    )
