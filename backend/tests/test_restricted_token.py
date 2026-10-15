# -*- coding: utf-8 -*-
"""Tests for the real Windows Restricted Token implementation.

These run under ordinary (non-elevated) Windows user permissions: the token is
derived from the caller's own primary token, so no admin rights or service is
required. On non-Windows platforms the module raises rather than pretending.
"""
from pathlib import Path
import sys

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import contextlib
import os
import sys as _sys

import pytest

from app.core.skill_engine.restricted_token import (
    IS_WINDOWS,
    RestrictedTokenError,
    RestrictedTokenUnsupportedPlatform,
    create_restricted_token,
    restricted_token_supported,
    run_process_with_restricted_token,
)

pytestmark = pytest.mark.skipif(
    not IS_WINDOWS, reason="Windows restricted tokens require Windows"
)


@contextlib.contextmanager
def restricted_token():
    info = create_restricted_token()
    try:
        yield info
    finally:
        info.close()


def base_env() -> dict:
    env = {"PATH": os.environ.get("PATH", "")}
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def test_platform_support_is_reported_truthfully():
    assert restricted_token_supported() is IS_WINDOWS


def test_created_token_is_verified_restricted_and_privilege_free():
    with restricted_token() as info:
        assert info.is_restricted is True
        assert info.privileges_disabled is True
        assert info.deny_only_group_count >= 1, (
            "CreateRestrictedToken must have placed restricting (deny-only) SIDs"
        )
        assert info.user_sid and info.user_sid.startswith("S-1-")
        described = info.describe()
        assert described["is_restricted"] is True
        assert described["privileges_disabled"] is True


def test_child_process_runs_under_the_restricted_token():
    with restricted_token() as info:
        result = run_process_with_restricted_token(
            info,
            [_sys.executable, "-c", "import json,sys;print(json.dumps({'ok':True}))"],
            env=base_env(),
            cwd=str(backend_dir),
            timeout=60,
        )
    assert result.timed_out is False
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert b'"ok": true' in result.stdout.lower()


def test_stdin_input_reaches_the_child():
    with restricted_token() as info:
        result = run_process_with_restricted_token(
            info,
            [_sys.executable, "-c", "import sys;sys.stdout.write(sys.stdin.read())"],
            env=base_env(),
            cwd=str(backend_dir),
            input_data=b"ping",
            timeout=60,
        )
    assert result.returncode == 0
    assert result.stdout == b"ping"


def test_timeout_terminates_the_child():
    with restricted_token() as info:
        result = run_process_with_restricted_token(
            info,
            [_sys.executable, "-c", "import time; time.sleep(30)"],
            env=base_env(),
            cwd=str(backend_dir),
            timeout=1.0,
        )
    assert result.timed_out is True
    assert result.returncode == -1


def test_bad_command_raises_restricted_token_error():
    with restricted_token() as info:
        with pytest.raises(RestrictedTokenError):
            run_process_with_restricted_token(
                info,
                ["definitely-not-a-real-binary-xyz"],
                env=base_env(),
                cwd=str(backend_dir),
                timeout=10,
            )


def test_unsupported_platform_error_is_a_restricted_token_error():
    assert issubclass(RestrictedTokenUnsupportedPlatform, RestrictedTokenError)


def test_json_arguments_survive_command_line_quoting():
    """Regression: the JSON skill payload must reach the child intact.

    The runner passes skill arguments as JSON on the command line. A naive
    quoting helper that doubles backslashes turns every ``\\uXXXX`` escape into
    a literal backslash-u sequence, so the child receives mangled text and
    silently produces different results. This asserts a non-ASCII JSON payload
    round-trips through the real restricted-token child process unchanged.
    """
    import json

    payload = json.dumps(
        {"content": "\u672a\u77e5\u4f20\u7edf\u88ab\u6cdb\u5316\uff01", "mode": "benchmark"},
        ensure_ascii=True,
    )
    with restricted_token() as info:
        result = run_process_with_restricted_token(
            info,
            [sys.executable, "-c", "import sys; sys.stdout.write(sys.argv[1])", payload],
            env=base_env(),
            cwd=str(backend_dir),
            timeout=20,
        )
    assert result.returncode == 0
    assert result.stdout.decode("utf-8") == payload
    assert json.loads(result.stdout.decode("utf-8"))["content"] == (
        "\u672a\u77e5\u4f20\u7edf\u88ab\u6cdb\u5316\uff01"
    )
