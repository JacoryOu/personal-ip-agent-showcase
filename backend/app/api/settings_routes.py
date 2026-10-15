
from app.api.settings_common import (
    BASE_URL_REJECTED_MESSAGE,
    _BaseUrlRejected,
    _facade,
    CONNECTION_TEST_FAILED_MESSAGE,
    ConnectionTestRequest,
    ConnectionTestResponse,
    _safe_host,
    is_local_provider_url,
    normalize_model_for_provider,
    router,
    validate_provider_base_url,
)

from fastapi import Depends, Header, Request

from app.core.auth import AuthenticatedUser, get_current_user
from typing import Optional
import os
import time
import logging

from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection(
    payload: ConnectionTestRequest,
    request: Request,
    x_model_name: Optional[str] = Header(None, alias="X-Model-Name"),
    x_model_api_key: Optional[str] = Header(None, alias="X-Model-Api-Key"),
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    x_base_url: Optional[str] = Header(None, alias="X-Base-Url"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ConnectionTestResponse:
    """
    Performs a lightweight chat completion test to verify model provider connectivity,
    validity of API key, and response latency.
    """
    # 1. System Default Mode: Tests the server's own .env configuration
    if payload.is_system_default:
        env_key = (os.environ.get("OPENAI_API_KEY") or settings.OPENAI_API_KEY or "").strip()
        if not env_key or env_key == "dummy-api-key":
            return ConnectionTestResponse(
                success=False,
                latency_ms=0,
                model=settings.OPENAI_MODEL or "system-default",
                message="后端环境 (.env) 尚未配置有效的 OPENAI_API_KEY",
            )
        api_key = env_key
        base_url = (os.environ.get("OPENAI_BASE_URL") or settings.OPENAI_BASE_URL or "").strip() or None
        model = (payload.model or os.environ.get("OPENAI_MODEL") or settings.OPENAI_MODEL or "deepseek-v3").strip()
        model = _facade().normalize_model_for_provider(model, base_url)
    else:
        # 2. BYOK / Custom Provider Mode: NEVER silently fall back to server's .env key!
        # Prefer the dedicated BYOK header; ``X-Api-Key`` is accepted as a
        # legacy fallback because older frontends still send the model key there.
        api_key = (payload.api_key or x_model_api_key or x_api_key or "").strip()
        base_url = (payload.base_url or x_base_url or "").strip() or None
        model = (payload.model or x_model_name or "deepseek-v3").strip()

        # A local (loopback) provider needs no API key; anything else is BYOK.
        is_local = _facade().is_local_provider_url(base_url)

        if not is_local and not api_key:
            return ConnectionTestResponse(
                success=False,
                latency_ms=0,
                model=model,
                message="未检测到 API Key。连接云端大模型服务前，请先输入有效的 API Key (BYOK)。",
            )

        model = _facade().normalize_model_for_provider(model, base_url)

    # SSRF guard: reject private / loopback / metadata endpoints. Loopback is
    # only permitted for an explicit local-provider URL, and only on the
    # local provider port. This runs *before* any socket is opened.
    try:
        _facade().validate_provider_base_url(base_url, allow_loopback=_facade().is_local_provider_url(base_url))
    except _facade()._BaseUrlRejected:
        logger.warning(
            "Rejected model provider base_url (model=%s) by SSRF guard",
            model,
        )
        return ConnectionTestResponse(
            success=False,
            latency_ms=0,
            model=model,
            message=_facade().BASE_URL_REJECTED_MESSAGE,
        )

    start_time = time.perf_counter()
    try:
        client = _facade().AsyncOpenAI(
            api_key=api_key or "no-key-required",
            base_url=base_url,
            timeout=15.0,
        )
        await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        return ConnectionTestResponse(
            success=True,
            latency_ms=latency_ms,
            model=model,
            message="Connection successful",
        )
    except Exception:
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        logger.exception(
            "Model provider connection test failed (model=%s, base_url_host=%s)",
            model,
            _safe_host(base_url),
        )
        return ConnectionTestResponse(
            success=False,
            latency_ms=latency_ms,
            model=model,
            message=CONNECTION_TEST_FAILED_MESSAGE,
        )


@router.get("/current")
async def get_current_settings(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Returns the default server-side model configuration with masked API key."""
    key = os.environ.get("OPENAI_API_KEY") or settings.OPENAI_API_KEY or ""
    masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else ("***" if key else "")
    return {
        "model": os.environ.get("OPENAI_MODEL") or settings.OPENAI_MODEL or "deepseek-v3",
        "base_url": os.environ.get("OPENAI_BASE_URL") or settings.OPENAI_BASE_URL or "",
        "api_key_configured": bool(key and key != "dummy-api-key"),
        "masked_api_key": masked_key,
    }