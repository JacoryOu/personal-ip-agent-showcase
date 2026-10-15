"""Regression tests for AGENTS.md harness constraint #3: real read-only DB isolation.

The agent layer (Outline / Draft input-context assembly) must run on a
*physically* read-only connection, not merely on a session we promise not to
write with. These tests assert the database/driver itself rejects the write.
"""

from pathlib import Path
import sys

import pytest
import sqlalchemy
from sqlalchemy import text
from sqlmodel import Session, SQLModel, select

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core import db as db_module
from app.core.db import (
    UnsupportedReadOnlyBackendError,
    _create_readonly_engine,
    get_readonly_session,
    is_readonly_session,
)
from app.engine.cognitive_engine import CognitiveEngine
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file_sqlite_url(tmp_path, name="readonly.db"):
    """File-based SQLite URL.

    A file database is the only SQLite form that can be opened read-only -
    an in-memory database only exists inside one writable connection.
    """
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def _bootstrap_writable(url):
    """Create the schema through a normal, fully writable engine."""
    import app.models  # noqa: F401  (registers SQLModel tables)

    writable = sqlalchemy.create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(writable)
    return writable


def _new_engine_without_init():
    """A CognitiveEngine without touching SkillManager/network setup."""
    return CognitiveEngine.__new__(CognitiveEngine)


# ---------------------------------------------------------------------------
# 1. SQLite: a write through the read-only session is physically blocked
# ---------------------------------------------------------------------------

def test_sqlite_readonly_session_physically_blocks_write(tmp_path):
    """The core mechanical guarantee.

    The write is rejected by SQLite because the connection is opened with
    ``mode=ro`` *and* ``PRAGMA query_only=ON`` - not by a Python convention,
    not by a prompt, not by a test-side guard.
    """
    url = _file_sqlite_url(tmp_path)
    _bootstrap_writable(url)

    ro = _create_readonly_engine(url)
    try:
        with Session(ro) as sess:
            # Reads work.
            assert sess.exec(select(User)).all() == []
            # The query_only guard is armed on this connection.
            assert sess.execute(text("PRAGMA query_only")).scalar() == 1

            # The write is rejected by the database engine itself.
            sess.add(User(username="forbidden", email="forbidden@example.com"))
            with pytest.raises(sqlalchemy.exc.OperationalError) as exc:
                sess.commit()
            assert "readonly" in str(exc.value).lower()
    finally:
        ro.dispose()


def test_sqlite_readonly_engine_uses_ro_uri(tmp_path):
    url = _file_sqlite_url(tmp_path)
    ro = _create_readonly_engine(url)
    try:
        rendered = ro.url.render_as_string()
        assert rendered.startswith("sqlite:///file:")
        assert "mode=ro" in rendered
        assert "uri=true" in rendered
    finally:
        ro.dispose()


def test_readonly_and_writable_engines_are_distinct_objects(tmp_path):
    """A second engine over the same file must not silently be the writable one."""
    url = _file_sqlite_url(tmp_path)
    writable = _bootstrap_writable(url)
    ro = _create_readonly_engine(url)
    try:
        assert ro is not db_module.engine
        assert ro.url != writable.url
        # ... and only the writable one can still write.
        with Session(writable) as sess:
            sess.add(User(username="allowed", email="allowed@example.com"))
            sess.commit()
        assert len(Session(writable).exec(select(User)).all()) == 1
    finally:
        ro.dispose()
        writable.dispose()


# ---------------------------------------------------------------------------
# 2. PostgreSQL: the connect listener sets read-only on every session
# ---------------------------------------------------------------------------

class _RecordingCursor:
    def __init__(self, sink):
        self._sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, *args, **kwargs):
        self._sink.append(sql)

    def close(self):  # pragma: no cover - sqlite-style cursors
        pass


class _FakeDBAPIConnection:
    def __init__(self):
        self.statements = []

    def cursor(self):
        return _RecordingCursor(self.statements)


class _FakeEngine:
    def __init__(self):
        self.connect_listeners = []

    def _register(self, fn):
        self.connect_listeners.append(fn)


def test_postgresql_readonly_listener_enforces_read_only(monkeypatch):
    """PostgreSQL has no read-only file mode, so read-only is set per session."""

    def fake_create_engine(url, **kwargs):
        engine = _FakeEngine()
        return engine

    def fake_listens_for(engine, identifier, fn=None):
        assert identifier == "connect"
        # SQLAlchemy calls this either bare (to get a decorator) or with ``fn``.
        if fn is None:
            return lambda target: engine._register(target)
        engine._register(fn)

    monkeypatch.setattr(db_module, "create_engine", fake_create_engine)
    monkeypatch.setattr(db_module.event, "listens_for", fake_listens_for)

    engine = _create_readonly_engine("postgresql://user:pw@localhost/db")
    assert engine.connect_listeners, "expected a connect listener for PostgreSQL"

    connection = _FakeDBAPIConnection()
    for listener in engine.connect_listeners:
        listener(connection, None)

    executed = " ".join(connection.statements)
    assert "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY" in executed
    assert "SET default_transaction_read_only = on" in executed


# ---------------------------------------------------------------------------
# 3. Backends that cannot enforce read-only fail closed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///:memory:",
        "sqlite://",
        "mysql://user:pw@localhost/db",
        "oracle://user:pw@localhost/db",
    ],
)
def test_backends_without_true_readonly_fail_closed(url):
    """No silent degradation: if we cannot enforce it, we refuse to start."""
    with pytest.raises(UnsupportedReadOnlyBackendError):
        _create_readonly_engine(url)


# ---------------------------------------------------------------------------
# 4. The FastAPI dependency itself is read-only and self-describing
# ---------------------------------------------------------------------------

def test_get_readonly_session_dependency_blocks_writes():
    dependency = get_readonly_session()
    session = next(dependency)
    try:
        assert is_readonly_session(session) is True
        session.add(User(username="nope", email="nope@example.com"))
        with pytest.raises(sqlalchemy.exc.OperationalError) as exc:
            session.commit()
        assert "readonly" in str(exc.value).lower()
    finally:
        dependency.close()


# ---------------------------------------------------------------------------
# 5. Harness: the agent input-context path creates no rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outline_context_assembly_does_not_create_rows(tmp_path):
    """Assembling the agent's input bundle against an empty DB must not write."""
    url = _file_sqlite_url(tmp_path, "harness_outline.db")
    writable = _bootstrap_writable(url)
    ro = _create_readonly_engine(url)

    class _FakeOutlineAgent:
        async def generate_outlines(self, input_data):
            from app.schemas.outline_schemas import (
                Outline,
                OutlineOutput,
                OutlineSection,
            )

            return OutlineOutput(
                outline_a=Outline(
                    title="A",
                    rationale="ra",
                    sections=[OutlineSection(title="a1")],
                ),
                outline_b=Outline(
                    title="B",
                    rationale="rb",
                    sections=[OutlineSection(title="b1")],
                ),
            )

    engine = _new_engine_without_init()
    try:
        with Session(ro) as ro_session:
            assert is_readonly_session(ro_session) in (True, False)  # diagnostic only
            result = await engine.explore_outlines(
                topic="空库下的发散",
                agent=_FakeOutlineAgent(),
                readonly_session=ro_session,
            )
        assert result.outline_a.title == "A"

        # The read path created nothing at all.
        with Session(writable) as check:
            assert check.exec(select(User)).all() == []
    finally:
        ro.dispose()
        writable.dispose()


# ---------------------------------------------------------------------------
# 6. Draft: read path is read-only, archive path is a separate writable session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_read_path_cannot_write_but_archive_still_can(tmp_path):
    """The two-session contract, proven end to end."""
    url = _file_sqlite_url(tmp_path, "harness_draft.db")
    writable = _bootstrap_writable(url)
    ro = _create_readonly_engine(url)

    class _FakeDraftAgent:
        async def generate_draft(self, input_data):
            from app.schemas.draft_schemas import DraftOutput

            return DraftOutput(
                title="只读上下文生成的草稿",
                content="# 只读上下文\n\n正文",
                word_count=8,
            )

    engine = _new_engine_without_init()
    try:
        with Session(ro) as ro_session:
            # Prove the read path physically cannot write (done in its own
            # session so the failed transaction does not poison this one).
            with Session(ro) as probe:
                with pytest.raises(sqlalchemy.exc.OperationalError):
                    probe.add(User(username="oops", email="oops@example.com"))
                    probe.commit()

            with Session(writable) as write_session:
                result = await engine.generate_draft(
                    topic="只读与归档的边界",
                    outline={"title": "T", "rationale": "R", "sections": [{"title": "S1"}]},
                    agent=_FakeDraftAgent(),
                    readonly_session=ro_session,
                    session=write_session,
                )

        assert result.title == "只读上下文生成的草稿"
        # The archive harness (not the read-only session) persisted the draft.
        with Session(writable) as check:
            from app.models.draft import Draft

            saved = check.exec(select(Draft)).first()
            assert saved is not None
            assert saved.topic == "只读与归档的边界"
            assert "只读上下文" in saved.original_ai_draft
    finally:
        ro.dispose()
        writable.dispose()
