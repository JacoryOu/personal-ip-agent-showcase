# -*- coding: utf-8 -*-
"""Regression coverage for DB-backed per-user inspection scheduler state.

These tests prove the four pieces of per-user scheduler state (settings,
dismissed date, last quota decision, last execution summary) survive a service
restart, are isolated between users, and are never fabricated for a malformed
or non-user scope.
"""
from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models.scheduler_state import SchedulerUserState
from app.models.user import User
from app.schemas.scheduler_schemas import SchedulerSettings
from app.services import inspection_scheduler_service as svc_mod
from app.services.inspection_scheduler_service import DEFAULT_SCOPE, InspectionSchedulerService


@pytest.fixture(name="engine")
def engine_fixture():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture(name="users")
def users_fixture(engine):
    with Session(engine) as s:
        a = User(id=uuid.uuid4(), username="sched_a", profile_data={})
        b = User(id=uuid.uuid4(), username="sched_b", profile_data={})
        s.add(a)
        s.add(b)
        s.commit()
        s.refresh(a)
        s.refresh(b)
        yield a.id, b.id


@pytest.fixture(name="svc")
def svc_fixture(engine, monkeypatch):
    # The service falls back to a module-level engine when no session is passed;
    # point it at the test engine so "no session" paths stay observable.
    monkeypatch.setattr(svc_mod, "engine", engine)
    return InspectionSchedulerService()


def test_settings_survive_new_service_instance(svc, engine, users):
    uid_a, _ = users
    updated = svc.update_settings({"interval_hours": 7}, user_id=uid_a, session=Session(engine))
    assert updated.interval_hours == 7

    # A brand new instance (as after a process restart) must read the same value.
    fresh = InspectionSchedulerService()
    assert fresh.get_settings(uid_a, session=Session(engine)).interval_hours == 7


def test_settings_are_isolated_per_user(svc, engine, users):
    uid_a, uid_b = users
    svc.update_settings({"interval_hours": 3}, user_id=uid_a, session=Session(engine))
    svc.update_settings({"interval_hours": 11}, user_id=uid_b, session=Session(engine))

    fresh = InspectionSchedulerService()
    assert fresh.get_settings(uid_a, session=Session(engine)).interval_hours == 3
    assert fresh.get_settings(uid_b, session=Session(engine)).interval_hours == 11


def test_missing_row_returns_default_settings(svc, engine):
    unknown = uuid.uuid4()
    with Session(engine) as s:
        cfg = svc.get_settings(unknown, session=s)
        rows = s.exec(select(SchedulerUserState)).all()
    assert isinstance(cfg, SchedulerSettings)
    assert cfg.interval_hours == SchedulerSettings().interval_hours
    # Reading must not create a row for a user that has no state yet.
    assert rows == []


def test_malformed_user_id_creates_no_row(svc, engine):
    svc.update_settings({"interval_hours": 5}, user_id="not-a-uuid", session=Session(engine))
    with Session(engine) as s:
        rows = s.exec(select(SchedulerUserState)).all()
    assert rows == []


def test_default_scope_stays_in_memory_only(svc, engine):
    svc.update_settings({"interval_hours": 9}, user_id=None, session=Session(engine))
    assert svc.get_settings(DEFAULT_SCOPE, session=Session(engine)).interval_hours == 9
    with Session(engine) as s:
        rows = s.exec(select(SchedulerUserState)).all()
    # DEFAULT_SCOPE belongs to no users row, so it must never be persisted.
    assert rows == []


def test_dismissed_date_persists(svc, engine, users):
    uid_a, _ = users
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    svc.mark_briefing_read(date_str=today, user_id=uid_a, session=Session(engine))

    fresh = InspectionSchedulerService()
    with Session(engine) as s:
        assert fresh._read_dismissed_date(s, uid_a) == today


def test_summary_and_quota_decision_persist(svc, engine, users):
    uid_a, _ = users
    summary = {"success": True, "wheel1_new_topics": 2}
    decision = {"allowed": True, "reason": "pre-authorised"}
    with Session(engine) as s:
        svc._write_state_field(s, uid_a, "last_summary", summary)
        svc._write_state_field(s, uid_a, "quota_decision", decision)

    fresh = InspectionSchedulerService()
    with Session(engine) as s:
        assert fresh._read_state_json(s, uid_a, "last_summary") == summary
        assert fresh._read_state_json(s, uid_a, "quota_decision") == decision


def test_state_row_is_unique_per_user(svc, engine, users):
    uid_a, _ = users
    with Session(engine) as s:
        svc._write_state_field(s, uid_a, "last_summary", {"n": 1})
        svc._write_state_field(s, uid_a, "last_summary", {"n": 2})
        rows = s.exec(select(SchedulerUserState)).all()
    assert len(rows) == 1
    assert rows[0].last_summary == {"n": 2}
