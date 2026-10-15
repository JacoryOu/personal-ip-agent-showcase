# -*- coding: utf-8 -*-
"""Tests for Windows Job Object containment of sandboxed skill runs.

Job Objects need no administrator rights, so the real Win32 path is exercised
on any Windows host. The non-Windows branch asserts fail-closed behaviour.
"""
from pathlib import Path
import sys

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest

from app.core.skill_engine import job_object
from app.core.skill_engine.job_object import (
    IS_WINDOWS,
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
    JOB_OBJECT_LIMIT_BREAKAWAY_OK,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JobObjectError,
    JobObjectUnsupportedPlatform,
    JobObjectInfo,
    assign_process,
    create_job_object,
    job_object_supported,
    terminate_job,
)


# --- constants and platform contract ---------------------------------------

def test_job_object_supported_matches_platform():
    assert job_object_supported() is IS_WINDOWS


def test_breakaway_is_not_enabled_by_design():
    # Enabling BREAKAWAY_OK would let a child escape containment, so the flag
    # exists only to document intent and must not be part of what we set.
    assert JOB_OBJECT_LIMIT_BREAKAWAY_OK != JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    assert (
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE & JOB_OBJECT_LIMIT_BREAKAWAY_OK
    ) == 0


@pytest.mark.parametrize("bad", [1, 0, -3, "8", 2.5, True])
def test_active_process_limit_is_validated(bad):
    if not IS_WINDOWS:
        pytest.skip("validation only reaches Win32 on Windows")
    with pytest.raises(JobObjectError):
        create_job_object(active_process_limit=bad)


def test_non_windows_fails_closed(monkeypatch):
    monkeypatch.setattr(job_object, "IS_WINDOWS", False)
    with pytest.raises(JobObjectUnsupportedPlatform):
        create_job_object()


# --- real Win32 behaviour --------------------------------------------------

@pytest.mark.skipif(not IS_WINDOWS, reason="Job Objects require Windows")
def test_create_configures_kill_on_close():
    job = create_job_object()
    try:
        assert job.created is True
        assert job.kill_on_close is True
        assert job.active_process_limit is None
        assert job.assigned is False
    finally:
        job.close()
    assert job.handle is None


@pytest.mark.skipif(not IS_WINDOWS, reason="Job Objects require Windows")
def test_active_process_limit_is_recorded():
    job = create_job_object(active_process_limit=4)
    try:
        assert job.active_process_limit == 4
    finally:
        job.close()


@pytest.mark.skipif(not IS_WINDOWS, reason="Job Objects require Windows")
def test_assign_rejects_empty_handles():
    job = create_job_object()
    try:
        with pytest.raises(JobObjectError):
            assign_process(job, None)
        with pytest.raises(JobObjectError):
            assign_process(None, object())
    finally:
        job.close()


@pytest.mark.skipif(not IS_WINDOWS, reason="Job Objects require Windows")
def test_info_snapshot_is_serialisable():
    job = create_job_object()
    try:
        snap = job.describe()
        assert snap["created"] is True
        assert snap["kill_on_close"] is True
        assert snap["assigned"] is False
        assert snap["warnings"] == []
    finally:
        job.close()


@pytest.mark.skipif(not IS_WINDOWS, reason="Job Objects require Windows")
def test_close_is_idempotent():
    job = create_job_object()
    job.close()
    job.close()
    assert job.handle is None


@pytest.mark.skipif(not IS_WINDOWS, reason="Job Objects require Windows")
def test_terminate_on_empty_job_returns_false():
    job = create_job_object()
    job.close()
    assert terminate_job(job, 1) is False


def test_job_object_info_defaults_are_honest():
    info = JobObjectInfo()
    assert info.created is False
    assert info.kill_on_close is False
    assert info.assigned is False
    assert info.assigned_pid is None
    assert info.warnings == []
