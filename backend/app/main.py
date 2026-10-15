import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_router, public_endpoints_router
from app.core.config import settings
from app.core.db import init_db
from app.core.errors import (
    AUTH_REQUIRED,
    CONFLICT,
    FORBIDDEN,
    INTERNAL_ERROR,
    NOT_FOUND,
    VALIDATION_ERROR,
    AppError,
    error_response,
    get_request_id,
    log_internal_error,
)
from app.core.request_id import RequestIdMiddleware
from app.core.model_gateway import (
    request_model_override,
    request_api_key_override,
    request_base_url_override,
)
from app.services.inspection_scheduler_service import inspection_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await inspection_scheduler.start()
    yield
    await inspection_scheduler.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Assigns (or propagates) an X-Request-ID so any client-visible error can be
# correlated with the server-side log line that recorded its cause.
app.add_middleware(RequestIdMiddleware)

# Dynamic Request Header Middleware for Model / BYOK Override
@app.middleware("http")
async def dynamic_model_middleware(request: Request, call_next):
    model_override = request.headers.get("x-model-name")
    # BYOK model credentials use a dedicated header so they can never be
    # confused with the application auth credential (which also accepts
    # ``X-Api-Key``). The legacy header is still honoured as a fallback.
    api_key_override = request.headers.get("x-model-api-key") or request.headers.get("x-api-key")
    base_url_override = request.headers.get("x-base-url")

    t1 = request_model_override.set(model_override.strip() if model_override and model_override.strip() else None)
    t2 = request_api_key_override.set(api_key_override.strip() if api_key_override and api_key_override.strip() else None)
    t3 = request_base_url_override.set(base_url_override.strip() if base_url_override and base_url_override.strip() else None)
    try:
        response = await call_next(request)
        return response
    finally:
        request_model_override.reset(t1)
        request_api_key_override.reset(t2)
        request_base_url_override.reset(t3)


# ------------------------------------------------------------------
# CORS configuration
# ------------------------------------------------------------------
# Origins are always an explicit list: "*" is rejected because
# allow_credentials=True is required and the wildcard is illegal with it.
IS_PRODUCTION = settings.ENVIRONMENT.strip().lower() in {"production", "prod"}

configured_origins = [
    f"http://localhost:{settings.FRONTEND_PORT}",
    f"http://127.0.0.1:{settings.FRONTEND_PORT}",
    f"http://{settings.BIND_HOST}:{settings.FRONTEND_PORT}",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
configured_origins += [o for o in settings.CORS_ORIGINS if o != "*"]

if IS_PRODUCTION:
    # In production the localhost development origins are dropped unless the
    # operator explicitly re-added them via CORS_ORIGINS.
    cors_origins = [
        o for o in dict.fromkeys(configured_origins) if "localhost" not in o and "127.0.0.1" not in o
    ]
else:
    cors_origins = list(dict.fromkeys(configured_origins))

allow_origin_regex = None
if not IS_PRODUCTION and settings.CORS_ALLOW_LOCALHOST_REGEX:
    # Development convenience only: any localhost port (Vite dynamic ports).
    allow_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

if not cors_origins and allow_origin_regex is None:
    # Never leave the browser silently cross-origin-blocked without saying so.
    logging.getLogger(__name__).warning(
        "CORS_ALLOWLIST_EMPTY: no origins configured; browser cross-origin requests will be rejected."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=list(settings.CORS_ALLOW_METHODS),
    allow_headers=list(settings.CORS_ALLOW_HEADERS),
)

# ------------------------------------------------------------------
# Static file serving for uploads (e.g. product images)
# ------------------------------------------------------------------
# Toggleable via EXPOSE_UPLOADS so a production deployment is not forced to
# publish every uploaded asset on an unauthenticated static mount.
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
if settings.EXPOSE_UPLOADS:
    try:
        (UPLOAD_DIR / "products").mkdir(parents=True, exist_ok=True)
        app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
    except OSError as exc:  # pragma: no cover - depends on host filesystem
        logging.getLogger(__name__).warning(
            "UPLOADS_MOUNT_FAILED: could not mount /uploads from %s (%s). "
            "Uploaded assets will not be served statically.",
            UPLOAD_DIR,
            exc,
        )
else:
    logging.getLogger(__name__).warning(
        "UPLOADS_DISABLED: EXPOSE_UPLOADS is false, so /uploads is not mounted. "
        "Product image URLs will not resolve unless content is served another way."
    )

# Include API Routers
app.include_router(api_router)
app.include_router(public_endpoints_router)


@app.get("/")
def read_root():
    return {"status": "ok", "message": "Personal Cognitive IP Engine is running"}


# ------------------------------------------------------------------
# Unified error contract
# ------------------------------------------------------------------
# Raw exception text (database messages, filesystem paths, third-party SDK
# payloads) must never reach a client. Expected business failures raise
# AppError; everything else collapses to a fixed INTERNAL_ERROR body while the
# full traceback stays in the server log.

_STATUS_TO_CODE = {
    status.HTTP_401_UNAUTHORIZED: AUTH_REQUIRED,
    status.HTTP_403_FORBIDDEN: FORBIDDEN,
    status.HTTP_404_NOT_FOUND: NOT_FOUND,
    status.HTTP_409_CONFLICT: CONFLICT,
    status.HTTP_422_UNPROCESSABLE_CONTENT: VALIDATION_ERROR,
}


def _code_for_status(status_code: int) -> str:
    if status_code in _STATUS_TO_CODE:
        return _STATUS_TO_CODE[status_code]
    if status_code >= 500:
        return INTERNAL_ERROR
    return VALIDATION_ERROR


@app.exception_handler(AppError)
async def _app_error_handler(request: Request, exc: AppError):
    request_id = get_request_id(request)
    return error_response(
        request_id,
        exc.code,
        exc.message,
        exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    # Never echo the submitted payload back; field names and locations are
    # enough for the client to correct the request.
    request_id = get_request_id(request)
    return error_response(
        request_id,
        VALIDATION_ERROR,
        "The request payload is invalid.",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    request_id = get_request_id(request)
    status_code = int(exc.status_code)
    code = _code_for_status(status_code)
    if status_code >= 500:
        # A 5xx detail is by definition internal context, not a client message.
        log_internal_error(request_id, request, exc)
        detail = "Internal server error."
    else:
        detail = exc.detail if isinstance(exc.detail, str) else None
    return error_response(
        request_id,
        code,
        detail or "Request failed.",
        status_code,
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def _unhandled_error_handler(request: Request, exc: Exception):
    request_id = get_request_id(request)
    log_internal_error(request_id, request, exc)
    return error_response(
        request_id,
        INTERNAL_ERROR,
        "Internal server error.",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
