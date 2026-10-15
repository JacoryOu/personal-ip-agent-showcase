"""Image Generation API endpoints."""

import base64
import logging
import time
from typing import Optional
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import settings
from app.core.net_guard import OutboundRequestBlocked, safe_fetch
from app.services.image_service import ImageService, get_image_service

logger = logging.getLogger(__name__)

#: Content types the image proxy is willing to inline as a data URI.
ALLOWED_PROXY_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/bmp",
        "image/svg+xml",
    }
)

#: Hard ceiling for a proxied image, independent of the global outbound cap.
MAX_PROXY_IMAGE_BYTES = 8 * 1024 * 1024

#: Ports that are not plausible for an LLM API endpoint.
_ALLOWED_BASE_URL_SCHEMES = ("http", "https")


def _base_url_override_allowed(raw: str) -> bool:
    """Return ``True`` when a caller-supplied base URL targets an allowed host.

    The caller may only redirect the image engine at hosts the operator listed
    in ``IMAGE_ALLOWED_BASE_URL_HOSTS``. Anything else (internal addresses, cloud
    metadata hosts, arbitrary third parties) is rejected, which keeps the
    endpoint from becoming an open proxy.
    """
    candidate = (raw or "").strip()
    if not candidate:
        return False
    try:
        parts = urlsplit(candidate)
    except ValueError:
        return False
    if parts.scheme not in _ALLOWED_BASE_URL_SCHEMES or not parts.hostname:
        return False
    if parts.username or parts.password:
        return False
    host = parts.hostname.lower()
    for allowed in settings.IMAGE_ALLOWED_BASE_URL_HOSTS:
        allowed_host = str(allowed).strip().lower()
        if host == allowed_host or host.endswith("." + allowed_host):
            return True
    return False


def _resolve_service_overrides(
    service: ImageService,
    headers: Optional[dict] = None,
) -> ImageService:
    """Apply caller headers only when they stay inside the operator allowlist.

    An api key or model override is honoured *together with* an allowlisted
    ``X-Image-Base-Url`` host. A base URL that is not allowlisted is discarded,
    so the operator's own key can never be sent to a host the caller picked.
    """
    if not headers:
        return service
    lowered = {str(k).lower(): v for k, v in headers.items()}
    requested_base = lowered.get("x-image-base-url")
    if not requested_base or not _base_url_override_allowed(requested_base):
        return service
    return ImageService(
        model=lowered.get("x-image-model") or None,
        api_key=lowered.get("x-image-api-key") or None,
        base_url=requested_base.strip(),
    )

router = APIRouter(tags=["images"])


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Description or core concept for image generation", min_length=1)
    size: Optional[str] = Field(None, description="Image dimensions or tier e.g. 2K, 1024x1792, 1792x1024")
    style: Optional[str] = Field(None, description="Visual theme style e.g. dark_gold, indigo_purple, clean_minimal")
    platform: Optional[str] = Field(None, description="Target platform e.g. xiaohongshu, wechat")
    aspect_ratio: Optional[str] = Field(None, description="Aspect ratio e.g. 3:4, 16:9, 1:1")
    # NOTE: ``api_key`` / ``base_url`` were removed on purpose. Accepting them
    # from the caller turned this endpoint into an open proxy for arbitrary
    # third-party LLM providers and leaked the operator's credentials into
    # client code. Credentials are resolved server-side only.


class ImageGenerateResponse(BaseModel):
    image_url: str
    prompt: str
    revised_prompt: Optional[str] = None
    is_fallback: Optional[bool] = False
    size: Optional[str] = None
    model: Optional[str] = None


@router.post("/generate", response_model=ImageGenerateResponse)
async def generate_image(
    payload: ImageGenerateRequest,
    request: Request,
    service: ImageService = Depends(get_image_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ImageGenerateResponse:
    """
    Generates an AI background or cover image using Agnes Image 2.5 Flash
    or OpenAI / Wanx compatible engines, with platform prompt optimization
    and resilient SVG fallback.
    """
    clean_prompt = payload.prompt.strip()
    if not clean_prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Prompt cannot be empty.",
        )

    service = _resolve_service_overrides(service, dict(request.headers))

    try:
        result = await service.generate(
            prompt=clean_prompt,
            size=payload.size,
            style=payload.style,
            platform=payload.platform,
            aspect_ratio=payload.aspect_ratio,
        )
        return ImageGenerateResponse(**result)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(ve),
        )
    except Exception:
        # Never echo the provider/upstream message: it can contain the target
        # base URL, the operator key, or the raw upstream response body.
        logger.warning("Image generation failed.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image generation failed.",
        )


@router.get("/proxy")
async def proxy_image(
    url: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Proxy a remote image, hardened against SSRF.

    Every hop of the redirect chain is re-validated by
    :func:`app.core.net_guard.safe_fetch`, so an allowed host cannot bounce the
    request into the private network or a cloud metadata endpoint.
    """
    if not url or not url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="url is required"
        )

    try:
        result = await safe_fetch(url.strip(), max_bytes=MAX_PROXY_IMAGE_BYTES)
    except OutboundRequestBlocked as exc:
        # Deliberately terse: DNS/address detail is not useful to a caller and
        # is useful to an attacker probing the guard.
        logger.info("Blocked outbound image proxy request: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The requested URL is not permitted.",
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upstream image request failed: {exc.__class__.__name__}",
        )

    if result.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upstream returned HTTP {result.status_code}.",
        )

    content_type = (result.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_PROXY_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upstream response was not a supported image type.",
        )

    encoded = base64.b64encode(result.content).decode("ascii")
    return {"data_uri": f"data:{content_type};base64,{encoded}"}


class ImageConnectionTestResponse(BaseModel):
    success: bool
    latency_ms: int
    model: str
    message: str


@router.post("/test-connection", response_model=ImageConnectionTestResponse)
async def test_image_connection(
    service: ImageService = Depends(get_image_service),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ImageConnectionTestResponse:
    """Probe the server-side configured image engine.

    The caller cannot supply a key or base URL; see ``ImageGenerateRequest``.
    """
    target_model = service.resolve_model()
    target_key = service.resolve_api_key()
    target_base = service.resolve_base_url() or "https://apihub.agnes-ai.com/v1"

    if not target_key.strip():
        return ImageConnectionTestResponse(
            success=False,
            latency_ms=0,
            model=target_model,
            message="服务端未配置生图 API Key。请在服务端环境变量中设置后重试。",
        )

    start_time = time.perf_counter()
    headers = {"Authorization": f"Bearer {target_key.strip()}"}
    test_url = target_base.rstrip("/")
    if not test_url.endswith("/images/generations"):
        test_url = f"{test_url}/images/generations"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                test_url,
                headers=headers,
                json={
                    "model": target_model,
                    "prompt": "ping",
                    "size": "1K",
                    "extra_body": {"response_format": "url"},
                },
            )
            latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            if resp.status_code == 200:
                return ImageConnectionTestResponse(
                    success=True,
                    latency_ms=latency_ms,
                    model=target_model,
                    message="生图引擎连通测试成功 (HTTP 200 OK)",
                )
            return ImageConnectionTestResponse(
                success=False,
                latency_ms=latency_ms,
                model=target_model,
                message=f"生图服务响应异常 (HTTP {resp.status_code})",
            )
    except Exception:
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        logger.warning("Image engine connectivity probe failed.", exc_info=True)
        return ImageConnectionTestResponse(
            success=False,
            latency_ms=latency_ms,
            model=target_model,
            message="生图接口连接异常，请检查服务端配置。",
        )
