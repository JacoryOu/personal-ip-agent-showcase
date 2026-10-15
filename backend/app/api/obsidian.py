# -*- coding: utf-8 -*-
"""
Obsidian Bridge API endpoints.

Prefix: /api/obsidian
- POST /api/obsidian/scan   — scan vault preview
- POST /api/obsidian/sync   — ingest selected notes
- GET  /api/obsidian/status — configured status
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.db import get_session
from app.core.errors import (
    NOT_FOUND,
    VALIDATION_ERROR,
    AppError,
)
from app.core.vault_path_guard import (
    VaultPathError,
    VaultPathNotADirectory,
    VaultPathNotFound,
    get_allowed_roots,
)
from app.services.obsidian_service import ObsidianBridgeService

router = APIRouter(tags=["obsidian"])


def _vault_path_app_error(exc: VaultPathError) -> AppError:
    """Map a vault rejection onto the public error contract.

    ``VaultPathError`` messages embed the resolved absolute filesystem path,
    so they must never be echoed to the client. Each subclass gets a fixed,
    path-free public message; the original detail is left to the server log.
    """
    if isinstance(exc, VaultPathNotFound):
        return AppError(code=NOT_FOUND, message="Vault path does not exist.")
    if isinstance(exc, VaultPathNotADirectory):
        return AppError(code=VALIDATION_ERROR, message="Vault path is not a directory.")
    return AppError(code=VALIDATION_ERROR, message="Vault path is not allowed.")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    vault_path: str
    target_tags: Optional[List[str]] = None
    target_folders: Optional[List[str]] = None


class SyncRequest(BaseModel):
    vault_path: str
    selected_items: List[Dict[str, Any]]
    # Retained for backward compatibility but never used for authorization:
    # the acting identity always comes from the authenticated caller.
    user_id: Optional[str] = None


class StatusRequest(BaseModel):
    vault_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/scan")
def scan_vault(
    payload: ScanRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Scan an Obsidian vault directory and return a filtered preview of matched notes.

    STRICT READ-ONLY — no files are written or modified.
    """
    try:
        result = ObsidianBridgeService.scan_vault(
            vault_path=payload.vault_path,
            target_tags=payload.target_tags,
            target_folders=payload.target_folders,
        )
        return result
    except VaultPathError as exc:
        raise _vault_path_app_error(exc) from exc


@router.post("/sync")
def sync_items(
    payload: SyncRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Ingest selected preview items from an Obsidian vault into the DNA memory store.
    """
    try:
        result = ObsidianBridgeService.sync_items(
            vault_path=payload.vault_path,
            selected_items=payload.selected_items,
            user_id=str(current_user.id),
            session=session,
        )
        return result
    except VaultPathError as exc:
        raise _vault_path_app_error(exc) from exc


@router.get("/status")
def get_obsidian_status(
    vault_path: Optional[str] = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Return the Obsidian bridge configuration status and sync statistics."""
    try:
        return ObsidianBridgeService.get_status(vault_path=vault_path, session=session)
    except VaultPathError as exc:
        raise _vault_path_app_error(exc) from exc


@router.get("/allowed-roots")
def get_allowed_vault_roots(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the vault roots the bridge is currently allowed to read from.

    Authenticated: the response reveals host filesystem layout, so it is part
    of the private surface rather than a public capability probe.
    """
    return {"allowed_roots": [str(r) for r in get_allowed_roots()]}
