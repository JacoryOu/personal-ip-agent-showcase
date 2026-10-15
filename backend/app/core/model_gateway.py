import contextvars
from contextlib import contextmanager
from enum import Enum
import json
import os
import re
from typing import Any, Dict, List, Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

# Context variables for per-request dynamic overrides from headers
request_model_override: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_model_override", default=None)
request_api_key_override: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_api_key_override", default=None)
request_base_url_override: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_base_url_override", default=None)


@contextmanager
def dynamic_model_context(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
):
    """Context manager for overriding model, api_key, and base_url in current task context."""
    t1 = request_model_override.set(model.strip() if model and model.strip() else None)
    t2 = request_api_key_override.set(api_key.strip() if api_key and api_key.strip() else None)
    t3 = request_base_url_override.set(base_url.strip() if base_url and base_url.strip() else None)
    try:
        yield
    finally:
        request_model_override.reset(t1)
        request_api_key_override.reset(t2)
        request_base_url_override.reset(t3)


class ModelRole(str, Enum):
    OUTLINE = "outline"  # Creative & Divergent
    DRAFT = "draft"      # Stylistic & Ghostwriting
    DIFF = "diff"        # Rigorous & Analytical
    VIRAL_ANALYSIS = "viral_analysis"  # Rhetorical breakdown of benchmark content


def extract_json_from_text(raw_content: str) -> Any:
    """
    Resiliently extracts and loads JSON from LLM output.
    Handles:
    - Pure JSON strings
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Reasoning model outputs (e.g. DeepSeek-R1 <think>...</think>)
    - Preamble / conversational prefix or suffix text by matching outer { ... } or [ ... ]
    """
    if not raw_content or not isinstance(raw_content, str) or not raw_content.strip():
        raise ValueError("Empty content received from model.")

    text = raw_content.strip()

    # 1. Strip reasoning chain tags (e.g. DeepSeek-R1 <think>...</think>)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # 2. Try direct json.loads
    try:
        return json.loads(text)
    except Exception:
        pass

    # 3. Try regex match for ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if match:
        block_content = match.group(1).strip()
        try:
            return json.loads(block_content)
        except Exception:
            pass

    # 4. Try finding outermost curly braces { ... }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 5. Try finding outermost square brackets [ ... ]
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        candidate = text[first_bracket : last_bracket + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 6. Fallback: strip leading and trailing backticks and whitespace
    clean = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    clean = re.sub(r"\s*```$", "", clean)
    return json.loads(clean)


class ModelGateway:
    def __init__(
        self,
        default_client: Optional[AsyncOpenAI] = None,
        clients: Optional[Dict[str, AsyncOpenAI]] = None,
    ):
        """
        Initializes the ModelGateway.
        Maintains an internal cache of AsyncOpenAI clients keyed by (api_key, base_url).
        """
        self._clients: Dict[str, AsyncOpenAI] = {}
        self._role_clients: Dict[ModelRole, AsyncOpenAI] = {}
        self._default_client = default_client
        if clients:
            self._clients.update(clients)

    def register_client_for_role(self, role: ModelRole, client: AsyncOpenAI) -> None:
        """Explicitly assigns an AsyncOpenAI client to a specific role (useful for tests/custom adapters)."""
        self._role_clients[role] = client

    def get_model_for_role(self, role: ModelRole, model_override: Optional[str] = None) -> str:
        """
        Resolves the model name for the given role.
        Precedence:
        1. Explicit model_override parameter.
        2. Dynamic request header override (request_model_override).
        3. Role-specific environment variable or settings (e.g. OUTLINE_MODEL).
        4. Fallback to settings.OPENAI_MODEL (or env OPENAI_MODEL).
        5. Default to 'gpt-4o'.
        """
        if model_override and model_override.strip():
            return model_override.strip()

        dyn_model = request_model_override.get()
        if dyn_model and dyn_model.strip():
            return dyn_model.strip()

        if role == ModelRole.OUTLINE:
            role_model = os.environ.get("OUTLINE_MODEL") or settings.OUTLINE_MODEL
        elif role == ModelRole.DRAFT:
            role_model = os.environ.get("DRAFT_MODEL") or settings.DRAFT_MODEL
        elif role == ModelRole.DIFF:
            role_model = os.environ.get("DIFF_MODEL") or settings.DIFF_MODEL
        else:
            role_model = None

        if role_model and role_model.strip():
            return role_model.strip()

        fallback = os.environ.get("OPENAI_MODEL") or settings.OPENAI_MODEL or "gpt-4o"
        return fallback.strip()

    def get_base_url_for_role(self, role: ModelRole) -> Optional[str]:
        """
        Resolves the base URL for the given role.
        Precedence:
        1. Dynamic request header override (request_base_url_override).
        2. Role-specific environment variable or settings (e.g. OUTLINE_BASE_URL).
        3. Fallback to settings.OPENAI_BASE_URL (or env OPENAI_BASE_URL).
        """
        dyn_base_url = request_base_url_override.get()
        if dyn_base_url and dyn_base_url.strip():
            return dyn_base_url.strip()

        if role == ModelRole.OUTLINE:
            role_base_url = os.environ.get("OUTLINE_BASE_URL") or settings.OUTLINE_BASE_URL
        elif role == ModelRole.DRAFT:
            role_base_url = os.environ.get("DRAFT_BASE_URL") or settings.DRAFT_BASE_URL
        elif role == ModelRole.DIFF:
            role_base_url = os.environ.get("DIFF_BASE_URL") or settings.DIFF_BASE_URL
        else:
            role_base_url = None

        if not (role_base_url and role_base_url.strip()):
            role_base_url = os.environ.get("OPENAI_BASE_URL") or settings.OPENAI_BASE_URL

        if role_base_url and role_base_url.strip():
            return role_base_url.strip()
        return None

    def get_api_key_for_role(self, role: ModelRole) -> str:
        """
        Resolves the API key for the given role.
        Precedence:
        1. Dynamic request header override (request_api_key_override).
        2. Role-specific env var (e.g. OUTLINE_API_KEY).
        3. settings.OPENAI_API_KEY or env OPENAI_API_KEY.
        4. Default to 'dummy-api-key'.
        """
        dyn_api_key = request_api_key_override.get()
        if dyn_api_key and dyn_api_key.strip():
            return dyn_api_key.strip()

        role_key = os.environ.get(f"{role.name}_API_KEY")
        if role_key and role_key.strip():
            return role_key.strip()

        return (
            os.environ.get("OPENAI_API_KEY")
            or settings.OPENAI_API_KEY
            or "dummy-api-key"
        )

    def get_client_for_role(self, role: ModelRole) -> AsyncOpenAI:
        """
        Retrieves or instantiates an AsyncOpenAI client for the given role,
        caching clients per (api_key, base_url).
        """
        dyn_api_key = request_api_key_override.get()
        dyn_base_url = request_base_url_override.get()
        has_dynamic = bool((dyn_api_key and dyn_api_key.strip()) or (dyn_base_url and dyn_base_url.strip()))

        if not has_dynamic:
            if role in self._role_clients:
                return self._role_clients[role]

            if self._default_client is not None:
                return self._default_client

        api_key = self.get_api_key_for_role(role)
        base_url = self.get_base_url_for_role(role)
        cache_key = f"{api_key}::{base_url}"

        if cache_key not in self._clients:
            self._clients[cache_key] = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
        return self._clients[cache_key]

    async def generate_structured(
        self,
        role: ModelRole,
        messages: list[dict],
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> T:
        """
        Generates structured output for the designated role using dual-layer resilient parsing:
        1. Attempts client.beta.chat.completions.parse.
           If the provider wraps output in markdown fences (e.g. DeepSeek-V3), rescues and parses the raw payload.
        2. If parse returns None or fails, falls back to client.chat.completions.create with json_object format.
        3. If json_object format is unsupported, falls back to unconstrained create with JSON extraction.
        4. If model refusal is encountered at any stage, raises ValueError(f"Model refused request: {refusal}").
        5. If all fail, raises ValueError("Failed to parse the response from the model.").
        """
        client = self.get_client_for_role(role)
        model = self.get_model_for_role(role, model_override=model_override)

        formatted_messages = list(messages)
        if system_prompt:
            formatted_messages = [{"role": "system", "content": system_prompt}] + formatted_messages

        # Layer 1: Native OpenAI Structured Outputs via beta.chat.completions.parse
        try:
            response = await client.beta.chat.completions.parse(
                model=model,
                messages=formatted_messages,
                response_format=response_model,
            )
            if response and response.choices:
                choice = response.choices[0]
                refusal = getattr(choice.message, "refusal", None)
                if refusal:
                    raise ValueError(f"Model refused request: {refusal}")

                if getattr(choice.message, "parsed", None) is not None:
                    return choice.message.parsed
        except ValueError as ve:
            if "Model refused request:" in str(ve):
                raise

            # Rescue raw string if pydantic.ValidationError was raised by beta.chat.completions.parse
            # (common when DeepSeek or other proxies return markdown fences ```json ... ```)
            raw_input = None
            if hasattr(ve, "errors") and callable(ve.errors):
                try:
                    err_list = ve.errors()
                    if err_list and isinstance(err_list, list):
                        raw_input = err_list[0].get("input")
                except Exception:
                    pass

            if isinstance(raw_input, str) and raw_input.strip():
                try:
                    data = extract_json_from_text(raw_input)
                    return response_model.model_validate(data)
                except Exception:
                    pass
            # Fall through to Layer 2
        except Exception as e:
            # Check for APIResponseValidationError wrapper or similar
            raw_content = None
            if hasattr(e, "body") and isinstance(e.body, dict):
                try:
                    raw_content = e.body.get("choices", [{}])[0].get("message", {}).get("content")
                except Exception:
                    pass
            if isinstance(raw_content, str) and raw_content.strip():
                try:
                    data = extract_json_from_text(raw_content)
                    return response_model.model_validate(data)
                except Exception:
                    pass
            # Fall through to Layer 2

        # Layer 2: Resilient standard completion fallback with JSON extraction
        try:
            raw_resp = await client.chat.completions.create(
                model=model,
                messages=formatted_messages,
                response_format={"type": "json_object"},
            )
            if raw_resp and raw_resp.choices:
                choice = raw_resp.choices[0]
                refusal = getattr(choice.message, "refusal", None)
                if refusal:
                    raise ValueError(f"Model refused request: {refusal}")

                raw_content = choice.message.content or ""
                data = extract_json_from_text(raw_content)
                return response_model.model_validate(data)
            raise ValueError("Failed to parse the response from the model.")
        except ValueError as ve:
            if "Model refused request:" in str(ve):
                raise
            raise ValueError("Failed to parse the response from the model.") from ve
        except Exception:
            # If response_format={"type": "json_object"} is rejected by third-party proxy, try unconstrained create
            pass

        # Layer 3: Unconstrained standard completion (for providers rejecting response_format={"type": "json_object"})
        try:
            raw_resp = await client.chat.completions.create(
                model=model,
                messages=formatted_messages,
            )
            if raw_resp and raw_resp.choices:
                choice = raw_resp.choices[0]
                refusal = getattr(choice.message, "refusal", None)
                if refusal:
                    raise ValueError(f"Model refused request: {refusal}")

                raw_content = choice.message.content or ""
                data = extract_json_from_text(raw_content)
                return response_model.model_validate(data)
            raise ValueError("Failed to parse the response from the model.")
        except ValueError as ve:
            if "Model refused request:" in str(ve):
                raise
            raise ValueError("Failed to parse the response from the model.") from ve
        except Exception as e:
            raise ValueError("Failed to parse the response from the model.") from e


_gateway_instance: Optional[ModelGateway] = None


def get_model_gateway() -> ModelGateway:
    """Singleton accessor for ModelGateway."""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = ModelGateway()
    return _gateway_instance


def set_model_gateway(gateway: Optional[ModelGateway]) -> None:
    """Sets or resets the global ModelGateway instance (useful in test teardown/fixtures)."""
    global _gateway_instance
    _gateway_instance = gateway


__all__ = [
    "ModelRole",
    "ModelGateway",
    "get_model_gateway",
    "set_model_gateway",
    "request_model_override",
    "request_api_key_override",
    "request_base_url_override",
    "dynamic_model_context",
]