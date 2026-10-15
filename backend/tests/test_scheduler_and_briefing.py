# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

# Ensure backend directory is in sys.path
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.core.auth import AuthenticatedUser, get_current_user
from app.core.db import get_session
from app.models.benchmark_account import BenchmarkAccount
from app.models.material import Material
from app.models.user import User
from app.services.inspection_scheduler_service import inspection_scheduler
from app.services.inspection_quota_service import set_grant as inspection_quota_set_grant


@pytest.fixture(autouse=True)
def unattended_pre_authorization(monkeypatch):
    """Explicit unattended pre-authorization for these scheduler tests.

    Unattended execution is deny-by-default on two independent layers:

    * ``SkillPermissionPolicy`` (``COG_SKILL_*``) -- capability + network egress.
    * the workflow permission layer (``COG_WORKFLOW_PRE_AUTHORIZED``).

    Both must be granted explicitly. Test-local monkeypatch keeps the grant from
    leaking into the rest of the suite.
    """
    from app.core.workflow_permissions import (
        ENV_PRE_AUTHORIZED,
        PERM_NETWORK_EGRESS,
        PERM_SKILL_EXEC,
        SKILL_CAP_FS_ISOLATED,
        SKILL_CAP_NETWORK_READ,
    )

    monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_HOSTS", "example.test")
    monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_UNATTENDED", "1")
    monkeypatch.setenv(
        "COG_SKILL_UNATTENDED_ALLOW_PERMISSIONS",
        f"{SKILL_CAP_NETWORK_READ},{SKILL_CAP_FS_ISOLATED}",
    )
    monkeypatch.setenv(
        ENV_PRE_AUTHORIZED,
        ",".join(
            [
                PERM_NETWORK_EGRESS,
                PERM_SKILL_EXEC,
                SKILL_CAP_NETWORK_READ,
                SKILL_CAP_FS_ISOLATED,
            ]
        ),
    )


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            id=uuid.uuid4(),
            username="scheduler_tester",
            profile_data={
                "interest_tags": ["AI", "商业", "独立开发", "超级个体"],
            },
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        # Unattended inspection now requires explicit pre-authorization plus a
        # non-zero budget. Grant it for these legacy scheduler tests.
        inspection_quota_set_grant(
            session,
            user.id,
            authorized=True,
            enabled=True,
            daily_limit=50,
            per_run_limit=50,
        )
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    # The scheduler API authorises on the authenticated identity, not on any
    # client-supplied user_id. Pin the request identity to the same seeded user
    # so the quota grant made in ``session`` actually applies to the call.
    user = session.exec(select(User)).first()
    assert user is not None

    def get_current_user_override() -> AuthenticatedUser:
        return AuthenticatedUser(id=user.id)

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_current_user] = get_current_user_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_scheduler_status_and_settings(client: TestClient, session: Session):
    """Verifies scheduler status retrieval and settings modification."""
    # 1. GET status
    resp = client.get("/api/scheduler/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "interval_hours" in data
    assert "settings" in data
    assert "unread_briefing_count" in data

    # 2. POST settings
    update_payload = {
        "interval_hours": 4,
        "daily_briefing_time": "09:00",
        "viral_threshold_likes": 5000,
        "interest_tags": ["AI智能体", "一人公司", "出海独立开发"],
    }
    resp = client.post("/api/scheduler/settings", json=update_payload)
    assert resp.status_code == 200
    updated_settings = resp.json()
    assert updated_settings["interval_hours"] == 4
    assert updated_settings["daily_briefing_time"] == "09:00"
    assert updated_settings["viral_threshold_likes"] == 5000
    assert "一人公司" in updated_settings["interest_tags"]

    # Verify updated status reflects new settings
    status_resp = client.get("/api/scheduler/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["interval_hours"] == 4
    assert status_data["daily_briefing_time"] == "09:00"


def test_wheel1_trending_radar_harvest(session: Session, monkeypatch):
    """Wheel 1 harvest, ingestion and de-duplication.

    The skill output is injected instead of hitting the real network: the point
    under test is the scheduler's quota gate, the explicit UNATTENDED context
    and the de-duplication logic, none of which depend on live trending data.
    """
    from app.core.skill_engine.windows_sandbox import SandboxExecutionResult
    from app.core.skill_engine.policy import ExecutionContext

    calls = {"n": 0, "context": None, "name": None}

    class _FixedRadar:
        def execute_skill_sync(self, name, args, runner_mode=None,
                               timeout_seconds=None, execution_context=None):
            calls["n"] += 1
            calls["name"] = name
            calls["context"] = execution_context
            return SandboxExecutionResult(
                success=True,
                output=[
                    {
                        "title": "Deterministic trending topic A",
                        "url": "https://example.com/topic-a",
                        "platform": "weibo",
                        "category": "AI",
                        "summary": "Fixed payload so de-duplication is deterministic.",
                        "hot_value": 100,
                        "score": 0.9,
                    },
                    {
                        "title": "Deterministic trending topic B",
                        "url": "https://example.com/topic-b",
                        "platform": "zhihu",
                        "category": "商业",
                        "summary": "Second fixed payload.",
                        "hot_value": 90,
                        "score": 0.8,
                    },
                ],
            )

    monkeypatch.setattr(
        "app.services.inspection_scheduler_service.get_skill_manager",
        lambda: _FixedRadar(),
    )

    user = session.exec(select(User)).first()
    assert user is not None

    new_mats = inspection_scheduler.run_wheel_1(session, user_id=user.id)
    assert len(new_mats) == 2
    assert calls["name"] == "trending-radar"
    # The scheduler must declare UNATTENDED explicitly, never implicitly.
    assert calls["context"] is ExecutionContext.UNATTENDED

    for m in new_mats:
        assert m.material_type == "trending"
        assert m.status == "inbox"
        assert m.title
        assert m.cleaned_content
        assert m.meta_info.get("harvested_by") == "wheel1_radar"

    # Second run with identical payloads must not create duplicates.
    second_run_mats = inspection_scheduler.run_wheel_1(session, user_id=user.id)
    assert len(second_run_mats) == 0
    assert calls["n"] == 2


def test_wheel2_benchmark_silent_deconstruct(session: Session):
    """Verifies Wheel 2 automatic inspection and structural blueprint extraction of benchmark viral posts."""
    user = session.exec(select(User)).first()
    assert user is not None

    # Run wheel 2
    deconstructed = inspection_scheduler.run_wheel_2(session, user_id=user.id)
    assert len(deconstructed) > 0

    for m in deconstructed:
        assert m.material_type == "benchmark"
        assert m.status == "inbox"
        assert m.blueprint_data is not None
        # Structural blueprint components
        bp = m.blueprint_data
        assert "opening_hook" in bp or "hook_style" in bp
        assert "structural_stages" in bp or "key_stages" in bp
        assert "emotional_arc" in bp


def test_trigger_endpoint_execution(client: TestClient, session: Session):
    """Verifies POST /api/scheduler/trigger immediately triggers manual inspection."""
    resp = client.post("/api/scheduler/trigger")
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert "message" in data
    assert "wheel1_new_topics" in data
    assert "wheel2_new_blueprints" in data
    assert "duration_ms" in data


def test_today_briefing_aggregation_and_mark_read(client: TestClient, session: Session):
    """Verifies GET /api/scheduler/briefing/today aggregates trending & benchmark materials and mark-read workflow."""
    user = session.exec(select(User)).first()
    assert user is not None

    # 1. Fetch today's briefing
    resp = client.get("/api/scheduler/briefing/today")
    assert resp.status_code == 200
    briefing = resp.json()

    assert "date" in briefing
    assert "total_items" in briefing
    assert "trending_topics" in briefing
    assert "benchmark_blueprints" in briefing
    assert briefing["total_items"] > 0
    assert briefing["unread"] is True

    # Check trending topics schema
    if briefing["trending_topics"]:
        top = briefing["trending_topics"][0]
        assert top["material_type"] == "trending"
        assert top["status"] == "inbox"

    # Check benchmark blueprints schema
    if briefing["benchmark_blueprints"]:
        bmp = briefing["benchmark_blueprints"][0]
        assert bmp["material_type"] == "benchmark"
        assert bmp["status"] == "inbox"
        assert bmp["blueprint_data"] is not None

    # 2. Mark briefing as read
    mark_resp = client.post("/api/scheduler/briefing/mark-read")
    assert mark_resp.status_code == 200
    assert mark_resp.json()["success"] is True

    # 3. Check briefing again - should now be marked read
    resp_after = client.get("/api/scheduler/briefing/today")
    assert resp_after.status_code == 200
    assert resp_after.json()["unread"] is False


def test_briefing_confirm_into_vault(client: TestClient, session: Session):
    """Verifies POST /api/scheduler/briefing/confirm marks items as confirmed and updates unread status."""
    # Trigger confirm
    resp = client.post("/api/scheduler/briefing/confirm")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "count" in data
    assert "confirmed_date" in data

    # Verify briefing is now read
    b_resp = client.get("/api/scheduler/briefing/today")
    assert b_resp.status_code == 200
    assert b_resp.json()["unread"] is False


def test_scheduler_toggles_and_next_run(session: Session):
    """Verifies wheel enable toggles and next run time calculation."""
    from app.schemas.scheduler_schemas import SchedulerSettings

    user = session.exec(select(User)).first()
    assert user is not None

    # Disabled wheel 1 returns empty
    cfg_no_w1 = SchedulerSettings(wheel1_enabled=False)
    assert inspection_scheduler.run_wheel_1(session, user_id=user.id, custom_settings=cfg_no_w1) == []

    # Disabled wheel 2 returns empty
    cfg_no_w2 = SchedulerSettings(wheel2_enabled=False)
    assert inspection_scheduler.run_wheel_2(session, user_id=user.id, custom_settings=cfg_no_w2) == []

    # Next run calculation
    inspection_scheduler.settings.enabled = True
    inspection_scheduler.settings.interval_hours = 6
    inspection_scheduler.settings.daily_briefing_time = "08:30"
    next_time = inspection_scheduler.calculate_next_run_time()
    assert next_time is not None

    # When disabled, next run time is None
    inspection_scheduler.settings.enabled = False
    assert inspection_scheduler.calculate_next_run_time() is None
    inspection_scheduler.settings.enabled = True

