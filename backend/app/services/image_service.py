"""Backend AI Image Generation Service.

Provides Agnes Image 2.5 Flash native integration and OpenAI-compatible image generation
(e.g. DALL-E 3, Wanx DashScope, CogView) with platform-tailored prompt optimization,
aspect ratio / size mapping, and resilient fallback generation.
"""

import base64
import html
import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.net_guard import OutboundRequestBlocked, OutboundPolicy, safe_fetch

logger = logging.getLogger(__name__)

#: Host allowlist for the native Agnes HTTP call. Kept in sync with
#: ``settings.IMAGE_ALLOWED_BASE_URL_HOSTS`` so the base URL a caller may pick
#: and the host the egress guard will actually dial cannot drift apart.
DEFAULT_IMAGE_ALLOWED_HOSTS: Tuple[str, ...] = (
    "apihub.agnes-ai.com",
    "api.openai.com",
)


def build_image_outbound_policy(
    allowed_hosts: Optional[Tuple[str, ...]] = None,
) -> OutboundPolicy:
    """Outbound policy for image-provider HTTP calls.

    Ports are restricted to 443. Plain http / port 80 is *not* opened up: an
    image provider reached over cleartext would leak the API key, and no
    configured provider needs it.
    """
    return OutboundPolicy(
        allowed_hosts=tuple(allowed_hosts or DEFAULT_IMAGE_ALLOWED_HOSTS),
        allow_private_network=False,
        max_redirects=int(settings.OUTBOUND_MAX_REDIRECTS),
        timeout_seconds=60.0,
        max_response_bytes=int(settings.OUTBOUND_MAX_RESPONSE_BYTES),
        allowed_ports=(443,),
    )


def is_agnes_model(model: Optional[str], base_url: Optional[str] = None) -> bool:
    """Checks whether model name or base URL targets Agnes Image engine."""
    if model and "agnes" in model.lower():
        return True
    if base_url and "agnes-ai.com" in base_url.lower():
        return True
    return False


def map_agnes_params(
    size: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    platform: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Maps input dimension, aspect ratio, or platform to Agnes Image 2.5 Flash specifications.
    Returns: (size_tier, ratio)
    - size_tier: '1K', '2K', '3K', '4K' (default '2K')
    - ratio: '3:4', '16:9', '1:1', '4:3', '9:16', '2:3', '3:2', '21:9' (default '3:4')
    """
    valid_tiers = {"1K", "2K", "3K", "4K"}
    valid_ratios = {"3:4", "16:9", "1:1", "4:3", "9:16", "2:3", "3:2", "21:9"}

    tier = "2K"
    if size:
        clean_s = size.strip().upper()
        if clean_s in valid_tiers:
            tier = clean_s

    ratio = None
    if aspect_ratio:
        clean_ar = aspect_ratio.strip().lower()
        if clean_ar in valid_ratios:
            ratio = clean_ar
        elif clean_ar in ("3/4", "vertical", "portrait"):
            ratio = "3:4"
        elif clean_ar in ("16/9", "horizontal", "landscape", "banner"):
            ratio = "16:9"
        elif clean_ar in ("1/1", "square"):
            ratio = "1:1"
        elif clean_ar in ("4/3",):
            ratio = "4:3"
        elif clean_ar in ("9/16",):
            ratio = "9:16"
        elif clean_ar in ("2/3",):
            ratio = "2:3"
        elif clean_ar in ("3/2",):
            ratio = "3:2"
        elif clean_ar in ("21/9",):
            ratio = "21:9"

    if not ratio and size:
        clean_s = size.strip().lower()
        if clean_s in valid_ratios:
            ratio = clean_s
        elif clean_s in ("3:4", "3/4", "vertical", "portrait", "xhs", "xiaohongshu", "1024x1792"):
            ratio = "3:4"
        elif clean_s in ("16:9", "16/9", "horizontal", "landscape", "banner", "wechat", "1792x1024"):
            ratio = "16:9"
        elif clean_s in ("1:1", "1/1", "square", "1024x1024"):
            ratio = "1:1"

    if not ratio and platform:
        clean_p = platform.strip().lower()
        if clean_p in ("xiaohongshu", "xhs", "redbook"):
            ratio = "3:4"
        elif clean_p in ("wechat", "weixin", "official_account"):
            ratio = "16:9"

    if not ratio:
        ratio = "3:4"

    return tier, ratio


class ImageService:
    def __init__(
        self,
        client: Optional[AsyncOpenAI] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self._custom_client = client
        self._custom_model = model
        self._custom_api_key = api_key
        self._custom_base_url = base_url

    def resolve_api_key(self) -> str:
        if self._custom_api_key:
            return self._custom_api_key
        return (
            os.environ.get("IMAGE_API_KEY")
            or settings.IMAGE_API_KEY
            or os.environ.get("OPENAI_API_KEY")
            or settings.OPENAI_API_KEY
            or ""
        )

    def resolve_base_url(self) -> Optional[str]:
        if self._custom_base_url:
            return self._custom_base_url
        return (
            os.environ.get("IMAGE_BASE_URL")
            or settings.IMAGE_BASE_URL
            or os.environ.get("OPENAI_BASE_URL")
            or settings.OPENAI_BASE_URL
            or None
        )

    def resolve_model(self) -> str:
        if self._custom_model:
            return self._custom_model
        return (
            os.environ.get("IMAGE_MODEL")
            or settings.IMAGE_MODEL
            or "agnes-image-2.5-flash"
        )

    def get_client(self) -> AsyncOpenAI:
        if self._custom_client:
            return self._custom_client

        api_key = self.resolve_api_key() or "dummy-api-key"
        base_url = self.resolve_base_url()
        return AsyncOpenAI(api_key=api_key, base_url=base_url)

    def map_size(
        self,
        size: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> str:
        """
        Maps requested dimension or aspect ratio to OpenAI DALL-E standard sizes:
        - 1024x1792: 3:4 / vertical portrait (Xiaohongshu native cover)
        - 1792x1024: 16:9 / horizontal landscape (WeChat official banner / hero)
        - 1024x1024: 1:1 square
        """
        valid_sizes = {"1024x1024", "1024x1792", "1792x1024"}

        # 1. Direct size matching
        if size:
            clean_s = size.strip().lower()
            if clean_s in valid_sizes:
                return clean_s
            if clean_s in ("3:4", "3/4", "vertical", "portrait", "xhs", "xiaohongshu"):
                return "1024x1792"
            if clean_s in ("16:9", "16/9", "horizontal", "landscape", "banner", "wechat"):
                return "1792x1024"
            if clean_s in ("1:1", "1/1", "square"):
                return "1024x1024"

        # 2. Aspect ratio mapping
        if aspect_ratio:
            clean_ar = aspect_ratio.strip().lower()
            if clean_ar in ("3:4", "3/4", "vertical", "portrait"):
                return "1024x1792"
            if clean_ar in ("16:9", "16/9", "horizontal", "landscape", "banner"):
                return "1792x1024"
            if clean_ar in ("1:1", "square"):
                return "1024x1024"

        # 3. Platform default mapping
        if platform:
            clean_p = platform.strip().lower()
            if clean_p in ("xiaohongshu", "xhs", "redbook"):
                return "1024x1792"
            if clean_p in ("wechat", "weixin", "official_account"):
                return "1792x1024"

        return "1024x1792"

    def optimize_prompt(
        self,
        prompt: str,
        platform: Optional[str] = None,
        style: Optional[str] = None,
    ) -> str:
        """
        Optimizes user or system prompt for Xiaohongshu cover visual aesthetics
        or WeChat editorial business illustrations.
        """
        clean_prompt = prompt.strip()
        platform_key = (platform or "xiaohongshu").strip().lower()
        style_key = (style or "dark_gold").strip().lower()

        # Style tone additions
        style_modifiers = {
            "dark_gold": "luxury deep obsidian and dark indigo gradient atmosphere, warm glowing amber highlights, premium cinematic lighting, volumetric light rays, elegant minimalist composition",
            "indigo_purple": "futuristic deep indigo and cyber violet ambient lighting, ethereal neon glow, sleek modern gradient, pristine studio lighting",
            "clean_minimal": "clean light porcelain aesthetic, architectural minimalism, bright soft daylight, clean negative space, Scandinavian editorial elegance",
        }
        chosen_style = style_modifiers.get(style_key, style_modifiers["dark_gold"])

        if platform_key in ("xiaohongshu", "xhs", "redbook"):
            optimized = (
                f"{clean_prompt}, commercial editorial photography, vertical 3:4 composition with balanced central negative space for typography overlay, "
                f"{chosen_style}, soft focus background, hyper-detailed textures, 8k resolution, cinematic masterpiece"
            )
        elif platform_key in ("wechat", "weixin"):
            optimized = (
                f"{clean_prompt}, wide-angle editorial technology and business conceptual artwork, 16:9 ratio, "
                f"{chosen_style}, sophisticated visual metaphors, hyper-detailed, ray tracing, studio lighting, 8k wallpaper"
            )
        else:
            optimized = f"{clean_prompt}, {chosen_style}, ultra-detailed, 8k resolution, cinematic aesthetic"

        return optimized

    def generate_fallback_svg_data_url(
        self,
        prompt: str,
        size: str = "1024x1792",
        platform: Optional[str] = None,
        style: Optional[str] = None,
    ) -> str:
        """
        Generates an artistic standalone SVG data URI as guaranteed zero-dependency fallback.
        Ensures frontend canvas and image rendering never break under any network or quota issues.
        """
        try:
            w_str, h_str = size.split("x")
            width, height = int(w_str), int(h_str)
        except Exception:
            width, height = 1024, 1792

        platform_tag = "XIAOHONGSHU VISUAL AI" if (platform and "wechat" not in platform.lower()) else "EDITORIAL COVER AI"
        clean_title = html.escape(prompt[:60] if prompt else "Personal Cognitive IP")
        
        # Determine theme gradient colors
        style_key = (style or "dark_gold").lower()
        if "indigo" in style_key:
            c1, c2, c3 = "#1e1b4b", "#31104b", "#0f172a"
            accent = "#38bdf8"
            circle_color = "rgba(56, 189, 248, 0.15)"
        elif "minimal" in style_key:
            c1, c2, c3 = "#f8fafc", "#e2e8f0", "#cbd5e1"
            accent = "#2563eb"
            circle_color = "rgba(37, 99, 235, 0.12)"
        else:
            c1, c2, c3 = "#090d16", "#141b2d", "#1f1d36"
            accent = "#f59e0b"
            circle_color = "rgba(245, 158, 11, 0.12)"

        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="50%" stop-color="{c2}"/>
      <stop offset="100%" stop-color="{c3}"/>
    </linearGradient>
    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#fbbf24" stop-opacity="0.2"/>
    </linearGradient>
    <radialGradient id="glowGrad" cx="50%" cy="35%" r="60%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="{c1}" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <!-- Background Base -->
  <rect width="{width}" height="{height}" fill="url(#bgGrad)" />

  <!-- Ambient Light Sphere -->
  <circle cx="{width // 2}" cy="{int(height * 0.4)}" r="{int(min(width, height) * 0.55)}" fill="url(#glowGrad)" />

  <!-- Geometric Abstract Shapes -->
  <g opacity="0.6">
    <circle cx="{int(width * 0.85)}" cy="{int(height * 0.2)}" r="{int(min(width, height) * 0.25)}" fill="{circle_color}" />
    <circle cx="{int(width * 0.15)}" cy="{int(height * 0.75)}" r="{int(min(width, height) * 0.35)}" fill="{circle_color}" />
    <circle cx="{width // 2}" cy="{int(height * 0.4)}" r="{int(min(width, height) * 0.38)}" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="8 8" opacity="0.4"/>
    <circle cx="{width // 2}" cy="{int(height * 0.4)}" r="{int(min(width, height) * 0.22)}" fill="none" stroke="{accent}" stroke-width="2" opacity="0.6"/>
  </g>

  <!-- Modern Grid Mesh Lines -->
  <g stroke="rgba(255, 255, 255, 0.05)" stroke-width="1">
    <line x1="0" y1="{height // 4}" x2="{width}" y2="{height // 4}" />
    <line x1="0" y1="{height // 2}" x2="{width}" y2="{height // 2}" />
    <line x1="0" y1="{int(height * 0.75)}" x2="{width}" y2="{int(height * 0.75)}" />
    <line x1="{width // 4}" y1="0" x2="{width // 4}" y2="{height}" />
    <line x1="{width // 2}" y1="0" x2="{width // 2}" y2="{height}" />
    <line x1="{int(width * 0.75)}" y1="0" x2="{int(width * 0.75)}" y2="{height}" />
  </g>

  <!-- Center Editorial Aesthetic Framing -->
  <rect x="{int(width * 0.08)}" y="{int(height * 0.12)}" width="{int(width * 0.84)}" height="{int(height * 0.76)}" rx="36" fill="none" stroke="url(#goldGrad)" stroke-width="2" opacity="0.35" />
</svg>'''

        b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"

    async def _generate_with_agnes(
        self,
        prompt: str,
        size: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        platform: Optional[str] = None,
        style: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes native HTTP call to Agnes Image 2.5 Flash endpoint.
        Adheres strictly to Agnes specification:
        - endpoint: POST https://apihub.agnes-ai.com/v1/images/generations
        - extra_body: {"response_format": "url"} (CRITICAL: NOT top-level response_format)
        - size: "1K" | "2K" | "3K" | "4K"
        - ratio: "3:4" | "16:9" | "1:1" ...
        """
        effective_key = api_key or self.resolve_api_key()
        if (not effective_key) or effective_key.strip() in ("dummy-api-key", "sk-dummy"):
            raise ValueError("No valid API Key configured for Agnes Image generation")

        effective_base_url = (base_url or self.resolve_base_url() or "https://apihub.agnes-ai.com/v1").rstrip("/")
        endpoint = f"{effective_base_url}/images/generations"
        effective_model = model or self.resolve_model()

        agnes_size, agnes_ratio = map_agnes_params(size=size, aspect_ratio=aspect_ratio, platform=platform)
        optimized_prompt = self.optimize_prompt(prompt, platform=platform, style=style)

        payload = {
            "model": effective_model,
            "prompt": optimized_prompt,
            "size": agnes_size,
            "ratio": agnes_ratio,
            "extra_body": {
                "response_format": "url",
            },
        }

        headers = {
            "Authorization": f"Bearer {effective_key}",
            "Content-Type": "application/json",
        }

        # Single egress path: every outbound hop goes through net_guard, so
        # scheme, embedded credentials, host allowlist, DNS-resolved private /
        # metadata / link-local ranges, port allowlist and redirect re-validation
        # are enforced here instead of being re-implemented per caller.
        policy = build_image_outbound_policy(
            tuple(settings.IMAGE_ALLOWED_BASE_URL_HOSTS) or DEFAULT_IMAGE_ALLOWED_HOSTS
        )
        try:
            result = await safe_fetch(
                endpoint,
                policy,
                method="POST",
                headers=headers,
                json=payload,
            )
        except OutboundRequestBlocked as exc:
            raise RuntimeError(f"Blocked outbound image request: {exc}") from exc

        if result.status_code >= 400:
            raise RuntimeError(
                f"Image provider returned HTTP {result.status_code}"
            )

        try:
            data = json.loads(result.content.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError("Image provider returned a non-JSON response") from exc

        items = data.get("data", [])
        if not items:
            raise RuntimeError("No image data returned from Agnes API")

        item = items[0]
        img_url = item.get("url")
        b64 = item.get("b64_json")
        if not img_url and b64:
            img_url = f"data:image/png;base64,{b64}"
        if not img_url:
            raise RuntimeError("Neither url nor b64_json found in Agnes response item")

        revised = item.get("revised_prompt") or optimized_prompt
        return {
            "image_url": img_url,
            "prompt": prompt,
            "revised_prompt": revised,
            "is_fallback": False,
            "size": f"{agnes_size} ({agnes_ratio})",
            "model": effective_model,
        }

    async def generate(
        self,
        prompt: str,
        size: Optional[str] = None,
        style: Optional[str] = None,
        platform: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates an image using Agnes Image 2.5 Flash or OpenAI-compatible API,
        with automatic parameter mapping, prompt optimization, and graceful SVG fallback.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Image prompt cannot be empty.")

        model = self.resolve_model()
        base_url = self.resolve_base_url()
        api_key = self.resolve_api_key()

        if is_agnes_model(model, base_url):
            agnes_size, agnes_ratio = map_agnes_params(size=size, aspect_ratio=aspect_ratio, platform=platform)
            size_label = f"{agnes_size} ({agnes_ratio})"
            try:
                return await self._generate_with_agnes(
                    prompt=prompt,
                    size=size,
                    aspect_ratio=aspect_ratio,
                    platform=platform,
                    style=style,
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                )
            except Exception as e:
                logger.warning("Agnes image generation failed (%s). Activating fallback.", e)
                fallback_svg = self.generate_fallback_svg_data_url(
                    prompt=prompt,
                    size="1024x1792" if agnes_ratio == "3:4" else ("1792x1024" if agnes_ratio == "16:9" else "1024x1024"),
                    platform=platform,
                    style=style,
                )
                return {
                    "image_url": fallback_svg,
                    "prompt": prompt,
                    "revised_prompt": self.optimize_prompt(prompt, platform=platform, style=style),
                    "is_fallback": True,
                    "size": size_label,
                    "model": model,
                }

        # OpenAI / Wanx / CogView compatible client
        mapped_size = self.map_size(size=size, aspect_ratio=aspect_ratio, platform=platform)
        optimized_prompt = self.optimize_prompt(prompt, platform=platform, style=style)
        is_dummy_key = (not api_key) or (api_key.strip() in ("dummy-api-key", "sk-dummy"))

        if not is_dummy_key:
            try:
                client = self.get_client()
                response = await client.images.generate(
                    model=model,
                    prompt=optimized_prompt,
                    size=mapped_size,
                    n=1,
                    response_format="url",
                )
                if response and response.data and len(response.data) > 0:
                    item = response.data[0]
                    img_url = getattr(item, "url", None)
                    revised = getattr(item, "revised_prompt", None) or optimized_prompt
                    if img_url:
                        return {
                            "image_url": img_url,
                            "prompt": prompt,
                            "revised_prompt": revised,
                            "is_fallback": False,
                            "size": mapped_size,
                            "model": model,
                        }
            except Exception as e:
                logger.warning("OpenAI-compatible image generation failed (%s). Activating fallback.", e)

        # Resilient fallback generation
        fallback_url = self.generate_fallback_svg_data_url(
            prompt=prompt,
            size=mapped_size,
            platform=platform,
            style=style,
        )
        return {
            "image_url": fallback_url,
            "prompt": prompt,
            "revised_prompt": optimized_prompt,
            "is_fallback": True,
            "size": mapped_size,
            "model": model,
        }


_image_service: Optional[ImageService] = None


def get_image_service() -> ImageService:
    global _image_service
    if _image_service is None:
        _image_service = ImageService()
    return _image_service


def set_image_service(service: Optional[ImageService]) -> None:
    global _image_service
    _image_service = service


__all__ = [
    "ImageService",
    "get_image_service",
    "set_image_service",
    "is_agnes_model",
    "map_agnes_params",
    "build_image_outbound_policy",
    "DEFAULT_IMAGE_ALLOWED_HOSTS",
]
