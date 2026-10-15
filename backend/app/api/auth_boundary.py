"""API authentication boundary helpers.

Two kinds of routers exist in this application:

* **Private routers** -- every endpoint below them requires a resolved caller
  identity.  The requirement is declared *once*, on the aggregating router, so a
  newly added handler is authenticated by default instead of relying on the
  author remembering to add ``Depends(get_current_user)``.
* **Public routers** -- only the endpoints explicitly mounted here are reachable
  without a credential.

Handlers on private routers may still declare
``current_user: AuthenticatedUser = Depends(get_current_user)`` when they need the
identity itself. FastAPI caches dependencies per request, so declaring the same
dependency on the router and on the handler does not run credential parsing
twice.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Tuple

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user

#: Endpoints that are intentionally reachable without a credential.
#:
#: Each entry is ``METHOD /path`` relative to the application root. Keep this
#: list short and justify every entry: an anonymous endpoint is a public
#: contract, not an oversight.
PUBLIC_ENDPOINTS: FrozenSet[Tuple[str, str]] = frozenset(
    {
        # Static WeChat Moments reference data. It reads no user record and
        # invokes no engine, so it stays anonymously reachable.
        ("GET", "/api/private-domain/templates"),
    }
)


def create_private_router(**kwargs: Any) -> APIRouter:
    """Create an ``APIRouter`` whose endpoints all require authentication."""
    dependencies = list(kwargs.pop("dependencies", []) or [])
    dependencies.append(Depends(get_current_user))
    kwargs["dependencies"] = dependencies
    return APIRouter(**kwargs)


def create_public_router(**kwargs: Any) -> APIRouter:
    """Create an ``APIRouter`` for explicitly public endpoints."""
    kwargs.pop("dependencies", None)
    return APIRouter(**kwargs)


__all__ = [
    "PUBLIC_ENDPOINTS",
    "create_private_router",
    "create_public_router",
]