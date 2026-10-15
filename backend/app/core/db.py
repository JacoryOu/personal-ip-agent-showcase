from typing import Generator
import logging
import os
from urllib.parse import urlsplit

from sqlalchemy import JSON, create_engine, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Session, SQLModel
from app.core.config import settings

logger = logging.getLogger(__name__)

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)

_db_initialized = False


# ---------------------------------------------------------------------------
# Read-only engine for the agent layer (AGENTS.md harness constraint #3)
# ---------------------------------------------------------------------------
# The agent layer (Outline / Draft) must only READ. A second engine pointing at
# the same writable file would provide no protection at all, so the read-only
# engine is backed by *database-level* enforcement:
#
#   * SQLite  -> the connection is opened through the SQLite URI
#                ``file:<abs path>?mode=ro`` (driver opens the file read-only),
#                plus ``PRAGMA query_only=ON`` as defence in depth.
#   * PostgreSQL -> ``SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY``
#                   and ``SET default_transaction_read_only = on`` per session.
#
# Both are enforced by the DB/driver. A write issued through the resulting
# session raises, it is not blocked by Python convention or a prompt.
#
# If the configured backend cannot provide true read-only enforcement we fail
# closed at import/engine-creation time instead of silently degrading.

SESSION_READONLY_FLAG = "_cognitive_engine_readonly"

SUPPORTED_READONLY_DIALECTS = ("sqlite", "postgresql")


class UnsupportedReadOnlyBackendError(RuntimeError):
    """Raised when the configured DB backend cannot enforce true read-only."""


def _detect_dialect(url: str) -> str:
    return urlsplit(url).scheme or ""


def _build_sqlite_readonly_url(url: str) -> str:
    """Rewrite a SQLite URL into a driver-enforced read-only URI.

    SQLite only honours ``mode=ro`` when the connection is opened as a URI, so
    ``uri=true`` is appended as well.
    """
    # Strip any existing query string so we do not produce a malformed URL.
    base = url.split("?", 1)[0]
    prefix = "sqlite:///"
    if not base.startswith(prefix):
        # Fail closed rather than raising a bare AssertionError: a malformed or
        # non-standard SQLite URL must not silently skip read-only enforcement.
        raise UnsupportedReadOnlyBackendError(
            f"Cannot derive a read-only SQLite URL from {url!r}: expected the "
            f"{prefix}<path> form."
        )
    raw_path = base[len(prefix):]

    # ":memory:" (or an empty path) cannot be opened read-only - the data only
    # exists inside the connection. Fail closed rather than pretend.
    if not raw_path or raw_path == ":memory:" or raw_path.startswith(":memory:"):
        raise UnsupportedReadOnlyBackendError(
            "SQLite ':memory:' databases cannot provide a read-only engine: the "
            "database only exists for the lifetime of a single writable "
            "connection. Point DATABASE_URL at a file-based SQLite database to "
            "enable agent-layer read-only isolation."
        )

    abs_path = os.path.abspath(raw_path.replace("\\", "/"))
    return f"sqlite:///file:{abs_path}?mode=ro&uri=true"


def _build_postgresql_readonly_url(url: str) -> str:
    """PostgreSQL needs no URL rewrite; read-only is set per session below."""
    return url


def _create_readonly_engine(url: str):
    dialect = _detect_dialect(url)

    if dialect == "sqlite":
        ro_url = _build_sqlite_readonly_url(url)
        ro_connect_args = {"check_same_thread": False}

        ro_engine = create_engine(ro_url, echo=False, connect_args=ro_connect_args)

        @event.listens_for(ro_engine, "connect")
        def _sqlite_query_only(dbapi_connection, _record):  # pragma: no cover - trivial
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA query_only=ON")
            finally:
                cursor.close()

        return ro_engine

    if dialect in ("postgresql", "postgres"):
        ro_url = _build_postgresql_readonly_url(url)
        ro_engine = create_engine(ro_url, echo=False, connect_args=dict(connect_args))

        @event.listens_for(ro_engine, "connect")
        def _postgres_read_only(dbapi_connection, _record):  # pragma: no cover - trivial
            with dbapi_connection.cursor() as cursor:
                cursor.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
                cursor.execute("SET default_transaction_read_only = on")

        return ro_engine

    raise UnsupportedReadOnlyBackendError(
        f"Cannot enforce a read-only session on DB backend '{dialect or 'unknown'}'. "
        f"Supported backends: {', '.join(SUPPORTED_READONLY_DIALECTS)}."
    )


readonly_engine = _create_readonly_engine(settings.DATABASE_URL)


def is_readonly_session(session: Session) -> bool:
    """True when ``session`` was issued by :func:`get_readonly_session`."""
    return bool(getattr(session, SESSION_READONLY_FLAG, False))


def init_db() -> None:
    """Initialize database tables, mapping JSONB to JSON for SQLite compatibility."""
    global _db_initialized
    import app.models  # noqa: F401

    if settings.DATABASE_URL.startswith("sqlite"):
        for table in SQLModel.metadata.tables.values():
            for col in table.columns:
                if isinstance(col.type, JSONB):
                    col.type = JSON()

    SQLModel.metadata.create_all(engine)

    # Lightweight auto-migration for SQLite to support schema evolution
    if settings.DATABASE_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                res = conn.execute(text("PRAGMA table_info(drafts)"))
                existing_cols = {row[1] for row in res.fetchall()}
                if existing_cols:
                    if "source_material_id" not in existing_cols:
                        conn.execute(text("ALTER TABLE drafts ADD COLUMN source_material_id CHAR(32)"))
                    if "benchmark_blueprint_id" not in existing_cols:
                        conn.execute(text("ALTER TABLE drafts ADD COLUMN benchmark_blueprint_id VARCHAR"))
                    if "lineage_snapshot" not in existing_cols:
                        conn.execute(text("ALTER TABLE drafts ADD COLUMN lineage_snapshot JSON"))
                    conn.commit()

                # product_vault auto-migration
                pv_res = conn.execute(text("PRAGMA table_info(product_vault)"))
                pv_cols = {row[1] for row in pv_res.fetchall()}
                if pv_cols:
                    if "cover_image" not in pv_cols:
                        conn.execute(text("ALTER TABLE product_vault ADD COLUMN cover_image VARCHAR DEFAULT ''"))
                    if "gallery_images" not in pv_cols:
                        conn.execute(text("ALTER TABLE product_vault ADD COLUMN gallery_images JSON DEFAULT '[]'"))
                    if "service_rights_images" not in pv_cols:
                        conn.execute(text("ALTER TABLE product_vault ADD COLUMN service_rights_images JSON DEFAULT '[]'"))
                    conn.commit()
        except Exception:
            # Auto-migration failures used to be swallowed silently, which let
            # the process mark the database as "initialized" while it was
            # actually running against an out-of-date schema. Log with the full
            # traceback and let the failure propagate so startup stops instead
            # of corrupting data on the first write that hits the missing
            # column.
            logger.exception(
                "SQLite auto-migration failed for %s; refusing to mark the "
                "database as initialized.",
                settings.DATABASE_URL,
            )
            raise

    _db_initialized = True


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions (fully writable)."""
    if not _db_initialized:
        init_db()
    with Session(engine) as session:
        yield session


def get_readonly_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a physically read-only database session.

    Any INSERT/UPDATE/DELETE issued through this session is rejected by the
    database driver (SQLite ``mode=ro`` + ``PRAGMA query_only``, or PostgreSQL
    read-only transactions), not by Python-level convention.

    The schema is created/migrated first via the writable engine when needed;
    that is DDL bootstrap, not agent-layer writing.
    """
    if not _db_initialized:
        init_db()

    with Session(readonly_engine) as session:
        setattr(session, SESSION_READONLY_FLAG, True)
        yield session
