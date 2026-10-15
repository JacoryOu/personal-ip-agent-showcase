from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Personal Cognitive IP Engine"
    API_V1_STR: str = "/api"

    OPENAI_API_KEY: Optional[str] = ""
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"

    OUTLINE_MODEL: Optional[str] = None
    DRAFT_MODEL: Optional[str] = None
    DIFF_MODEL: Optional[str] = None
    OUTLINE_BASE_URL: Optional[str] = None
    DRAFT_BASE_URL: Optional[str] = None
    DIFF_BASE_URL: Optional[str] = None

    IMAGE_MODEL: Optional[str] = "agnes-image-2.5-flash"
    IMAGE_API_KEY: Optional[str] = None
    IMAGE_BASE_URL: Optional[str] = "https://apihub.agnes-ai.com/v1"

    # Hosts a caller may target via X-Image-Base-Url. Anything outside this
    # allowlist is ignored, so the endpoint can never be used as an open proxy
    # for arbitrary third-party providers.
    IMAGE_ALLOWED_BASE_URL_HOSTS: List[str] = [
        "apihub.agnes-ai.com",
        "api.openai.com",
    ]

    # Symmetric key used to encrypt platform credentials at rest.
    # Accepts a raw Fernet key or an arbitrary passphrase (PBKDF2-stretched).
    PLATFORM_CREDENTIAL_MASTER_KEY: Optional[str] = None

    # SSRF guard for server-side outbound fetches (e.g. GET /api/images/proxy).
    OUTBOUND_ALLOWED_HOSTS: List[str] = []
    OUTBOUND_ALLOW_PRIVATE_NETWORK: bool = False
    OUTBOUND_MAX_REDIRECTS: int = 3
    OUTBOUND_TIMEOUT_SECONDS: float = 10.0
    OUTBOUND_MAX_RESPONSE_BYTES: int = 8 * 1024 * 1024

    DATABASE_URL: str = "sqlite:///./app.db"

    # ------------------------------------------------------------------
    # Authentication (P0 security line A)
    # ------------------------------------------------------------------
    # API_KEYS is a comma-separated ``user_id=secret`` list, e.g.
    #   API_KEYS="11111111-1111-1111-1111-111111111111=dev-secret"
    # Secrets come from the environment only; they are never persisted to the
    # database and never written into source control.
    API_KEYS: str = ""
    # When True, unauthenticated requests are rejected with 401 even if
    # API_KEYS is empty. Keeps "no credentials configured" from silently
    # becoming "everyone is the local dev user".
    AUTH_REQUIRED: bool = False
    # Explicit opt-in for single-user local development. Only when this is
    # True (and AUTH_REQUIRED is False) may an unauthenticated request fall
    # back to the fixed well-known local dev identity.
    AUTH_LOCAL_DEV_MODE: bool = False

    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173
    BIND_HOST: str = "127.0.0.1"

    # ------------------------------------------------------------------
    # Environment / CORS / static uploads
    # ------------------------------------------------------------------
    # "development" (default) or "production". Production drops the
    # permissive localhost origin-regex behaviour.
    ENVIRONMENT: str = "development"

    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # When True (development only) any localhost/127.0.0.1 port is accepted,
    # so Vite can pick a free port. Production ignores this entirely.
    CORS_ALLOW_LOCALHOST_REGEX: bool = True

    # Explicit method allowlist. Never "*".
    CORS_ALLOW_METHODS: List[str] = [
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ]

    # Explicit header allowlist, matching what the frontend actually sends
    # (see frontend/src/services/modelSettings.ts) plus the auth headers the
    # backend accepts. Never "*".
    CORS_ALLOW_HEADERS: List[str] = [
        "Accept",
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Model-Name",
        "X-Base-Url",
        "X-Image-Model",
        "X-Image-Api-Key",
        "X-Image-Base-Url",
    ]

    # Expose backend/app/data/uploads as the public /uploads static mount.
    # Set to False to disable the mount entirely (recommended for production
    # deployments that serve user content through an authenticated route).
    EXPOSE_UPLOADS: bool = True

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
