# -*- coding: utf-8 -*-
"""Tests for SKILL.md permission enforcement and network egress policy.

Two layers are covered here:

1. :mod:`app.core.skill_engine.policy` -- the pre-launch capability gate. A
   denied decision must stop the run BEFORE a token or a process exists.
2. :mod:`app.core.skill_engine.network_guard` -- the runtime egress guard that
   is injected into the child interpreter. Network tests run against a real
   local HTTP server on 127.0.0.1 so they do not depend on the public internet.
"""
from pathlib import Path
import sys

backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.core.skill_engine.discovery import SkillDefinition
from app.core.skill_engine.network_guard import host_is_allowed, parse_hosts
from app.core.skill_engine.policy import (
    Decision,
    ExecutionContext,
    NetworkPolicy,
    SkillPermissionPolicy,
    normalize_permission,
    normalize_permissions,
)
from app.core.skill_engine.windows_sandbox import (
    MODE_RESTRICTED_TOKEN,
    MODE_WSB,
    WindowsSandboxRunner,
)


ECHO_SKILL = """
import argparse, json

parser = argparse.ArgumentParser()
parser.add_argument("--file")
parser.add_argument("--json")
args, _ = parser.parse_known_args()

with open(args.file, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

print(json.dumps({"success": True, "echo": payload}))
"""

CONNECT_SKILL = """
import argparse, json, socket

parser = argparse.ArgumentParser()
parser.add_argument("--file")
parser.add_argument("--json")
args, _ = parser.parse_known_args()

with open(args.file, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

host = payload["host"]
port = int(payload["port"])

result = {"success": True, "allowed": False, "host": host}
try:
    conn = socket.create_connection((host, port), timeout=3)
    conn.close()
    result["allowed"] = True
except Exception as exc:
    result["allowed"] = False
    result["error"] = type(exc).__name__ + ": " + str(exc)

print(json.dumps(result))
"""


def _write_skill(tmp_path, name, source, permissions):
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "main.py").write_text(source, encoding="utf-8")
    return SkillDefinition(
        name=name,
        description="test skill",
        entrypoint="main.py",
        runner_mode=MODE_RESTRICTED_TOKEN,
        skill_dir=str(skill_dir),
        permissions=permissions,
    )


# ==============================================================================
# Normalisation
# ==============================================================================

def test_normalize_permission_aliases():
    assert normalize_permission("network_read") == "network:read"
    assert normalize_permission("Network-Read") == "network:read"
    assert normalize_permission("NETWORK:WRITE") == "network:write"
    assert normalize_permission("filesystem_read") == "filesystem:read"
    assert normalize_permission("fs-write") == "filesystem:write"
    assert normalize_permission("filesystem:isolated") == "filesystem:isolated"


def test_normalize_permissions_dedupes_and_preserves_unknown():
    normalized = normalize_permissions(
        ["network:read", "network_read", "network:write", "totally:unknown"]
    )
    assert normalized == ["network:read", "network:write", "totally:unknown"]


# ==============================================================================
# Decision rules
# ==============================================================================

def test_no_network_declaration_allows_run_but_denies_egress():
    pol = SkillPermissionPolicy(network_policy=NetworkPolicy(allow_any_host=True))
    decision = pol.evaluate(["filesystem:isolated"], ExecutionContext.INTERACTIVE)
    assert decision.decision is Decision.ALLOW
    assert decision.network_egress_allowed is False
    assert decision.network_allowlist == []


def test_declared_network_with_allowlist_is_allowed():
    pol = SkillPermissionPolicy(
        network_policy=NetworkPolicy(allow_hosts=["api.example.com"])
    )
    decision = pol.evaluate(["network:read"], ExecutionContext.INTERACTIVE)
    assert decision.decision is Decision.ALLOW
    assert decision.network_egress_allowed is True
    assert decision.network_allowlist == ["api.example.com"]


def test_declared_network_without_allowlist_is_denied():
    pol = SkillPermissionPolicy(
        network_policy=NetworkPolicy(allow_hosts=[], allow_any_host=False)
    )
    decision = pol.evaluate(["network:read"], ExecutionContext.INTERACTIVE)
    assert decision.decision is Decision.DENY
    assert "network:read" in decision.denied_capabilities
    assert decision.reasons


def test_wildcard_network_policy_warns():
    pol = SkillPermissionPolicy(network_policy=NetworkPolicy(allow_any_host=True))
    decision = pol.evaluate(["network:read"], ExecutionContext.INTERACTIVE)
    assert decision.decision is Decision.ALLOW
    assert decision.network_allowlist == ["*"]
    assert any("not restricted to specific domains" in w for w in decision.warnings)


def test_unattended_without_preauthorisation_is_denied():
    pol = SkillPermissionPolicy(
        network_policy=NetworkPolicy(
            allow_hosts=["api.example.com"], allow_unattended=True
        )
    )
    decision = pol.evaluate(["network:read"], ExecutionContext.UNATTENDED)
    assert decision.decision is Decision.DENY
    assert any("pre-authorised unattended scope" in r for r in decision.reasons)


def test_unattended_with_preauthorised_scope_is_allowed():
    pol = SkillPermissionPolicy(
        network_policy=NetworkPolicy(
            allow_hosts=["api.example.com"], allow_unattended=True
        ),
        unattended_permissions=["network:read", "filesystem:isolated"],
    )
    decision = pol.evaluate(
        ["network:read", "filesystem:isolated"], ExecutionContext.UNATTENDED
    )
    assert decision.decision is Decision.ALLOW
    assert decision.network_egress_allowed is True


def test_unattended_network_denied_when_policy_forbids_unattended():
    pol = SkillPermissionPolicy(
        network_policy=NetworkPolicy(
            allow_hosts=["api.example.com"], allow_unattended=False
        ),
        unattended_permissions=["network:read"],
    )
    decision = pol.evaluate(["network:read"], ExecutionContext.UNATTENDED)
    assert decision.decision is Decision.DENY


# ==============================================================================
# from_env wiring: the unattended allowlist must be reachable from the
# environment, and must stay empty/deny-by-default when unset.
# ==============================================================================

def test_from_env_denies_unattended_when_nothing_configured(monkeypatch):
    monkeypatch.delenv("COG_SKILL_NETWORK_ALLOW_UNATTENDED", raising=False)
    monkeypatch.delenv("COG_SKILL_UNATTENDED_ALLOW_PERMISSIONS", raising=False)
    pol = SkillPermissionPolicy.from_env()
    assert pol.unattended_permissions == []
    d = pol.evaluate(["network:read", "filesystem:isolated"], ExecutionContext.UNATTENDED)
    assert d.decision is Decision.DENY

def test_from_env_grants_explicit_minimum_scope(monkeypatch):
    monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_UNATTENDED", "true")
    monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_HOSTS", "api.example.com")
    monkeypatch.setenv(
        "COG_SKILL_UNATTENDED_ALLOW_PERMISSIONS",
        "network:read;filesystem:isolated",
    )
    pol = SkillPermissionPolicy.from_env()
    d = pol.evaluate(
        ["network:read", "filesystem:isolated"], ExecutionContext.UNATTENDED
    )
    assert d.decision is Decision.ALLOW
    assert d.network_egress_allowed is True
    # Undeclared-in-allowlist capabilities must still be denied.
    d2 = pol.evaluate(["network:read", "exec"], ExecutionContext.UNATTENDED)
    assert d2.decision is Decision.DENY
    assert "exec" in d2.denied_capabilities

def test_from_env_host_allowlist_keeps_unattended_flag(monkeypatch):
    # Regression: an explicit host allowlist used to drop allow_unattended,
    # which silently denied every scheduled run to an allowed host.
    monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_HOSTS", "api.example.com")
    monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_UNATTENDED", "true")
    np_ = NetworkPolicy.from_env()
    assert np_.allow_unattended is True
    assert np_.host_allowed("api.example.com") is True
    assert np_.host_allowed("evil.example.net") is False

def test_from_env_unattended_permissions_absent_still_denies(monkeypatch):
    monkeypatch.setenv("COG_SKILL_NETWORK_ALLOW_UNATTENDED", "true")
    monkeypatch.delenv("COG_SKILL_UNATTENDED_ALLOW_PERMISSIONS", raising=False)
    pol = SkillPermissionPolicy.from_env()
    d = pol.evaluate(["filesystem:isolated"], ExecutionContext.UNATTENDED)
    assert d.decision is Decision.DENY


# ==============================================================================
# Host matching
# ==============================================================================

def test_host_is_allowed_exact_and_subdomain():
    allowed = ["example.com"]
    assert host_is_allowed("example.com", allowed)
    assert host_is_allowed("api.example.com", allowed)
    assert not host_is_allowed("notexample.com", allowed)
    assert not host_is_allowed("example.com.evil.net", allowed)


def test_parse_hosts_handles_wildcard():
    assert parse_hosts("*") == ["*"]
    assert host_is_allowed("anything.example.net", ["*"]) is True


# ==============================================================================
# Runner integration: deny happens before any process/token exists
# ==============================================================================

def test_policy_deny_never_creates_a_token(tmp_path, monkeypatch):
    import app.core.skill_engine.windows_sandbox as ws

    calls = []
    monkeypatch.setattr(
        ws, "create_restricted_token", lambda *a, **k: calls.append("token")
    )
    monkeypatch.setattr(
        ws, "run_process_with_restricted_token", lambda *a, **k: calls.append("proc")
    )

    skill = _write_skill(tmp_path, "echo_skill", ECHO_SKILL, ["network:read"])
    runner = WindowsSandboxRunner(
        permission_policy=SkillPermissionPolicy(
            network_policy=NetworkPolicy(allow_hosts=[], allow_any_host=False)
        )
    )
    result = runner.run_skill_sync(skill, {})
    assert result.success is False
    assert result.policy_decision == Decision.DENY.value
    assert result.sandbox_enforced is False
    assert calls == []
    assert result.network_egress_allowed is False


def test_wsb_still_fails_closed_with_policy_in_place(tmp_path):
    skill = _write_skill(tmp_path, "echo_skill", ECHO_SKILL, [])
    result = WindowsSandboxRunner().run_skill_sync(skill, {}, runner_mode=MODE_WSB)
    assert result.success is False
    assert result.runner_mode == "wsb_unsupported"


def test_echo_skill_without_permissions_still_runs(tmp_path):
    """Existing restricted-token behaviour must not regress for skills that
    declare no permissions at all: they run, with network denied."""
    skill = _write_skill(tmp_path, "echo_skill", ECHO_SKILL, [])
    runner = WindowsSandboxRunner(
        default_timeout=60.0,
        permission_policy=SkillPermissionPolicy(
            network_policy=NetworkPolicy(allow_any_host=True)
        ),
    )
    result = runner.run_skill_sync(skill, {"hello": "world"})
    assert result.success is True, result.stderr or result.error
    assert result.policy_decision == Decision.ALLOW.value
    assert result.network_egress_allowed is False
    assert result.network_allowlist == []


# ==============================================================================
# Runtime network guard (real child process, real local server)
# ==============================================================================

@pytest.fixture
def local_http_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def test_child_without_network_permission_is_blocked_from_localhost(tmp_path, local_http_server):
    skill = _write_skill(
        tmp_path, "connect_skill", CONNECT_SKILL, ["filesystem:isolated"]
    )
    runner = WindowsSandboxRunner(
        default_timeout=60.0,
        permission_policy=SkillPermissionPolicy(
            network_policy=NetworkPolicy(allow_any_host=True)
        ),
    )
    result = runner.run_skill_sync(
        skill, {"host": "127.0.0.1", "port": local_http_server}
    )
    assert result.success is True, result.stderr or result.error
    assert result.output["allowed"] is False
    assert "NetworkEgressDenied" in result.output["error"]


def test_child_with_network_permission_can_reach_allowed_host(tmp_path, local_http_server):
    skill = _write_skill(tmp_path, "connect_skill", CONNECT_SKILL, ["network:read"])
    runner = WindowsSandboxRunner(
        default_timeout=60.0,
        permission_policy=SkillPermissionPolicy(
            network_policy=NetworkPolicy(allow_hosts=["127.0.0.1"])
        ),
    )
    result = runner.run_skill_sync(
        skill, {"host": "127.0.0.1", "port": local_http_server}
    )
    assert result.success is True, result.stderr or result.error
    assert result.output["allowed"] is True
    assert result.network_egress_allowed is True
    assert result.network_allowlist == ["127.0.0.1"]


def test_child_with_network_permission_cannot_reach_denied_host(tmp_path, local_http_server):
    skill = _write_skill(tmp_path, "connect_skill", CONNECT_SKILL, ["network:read"])
    runner = WindowsSandboxRunner(
        default_timeout=60.0,
        permission_policy=SkillPermissionPolicy(
            network_policy=NetworkPolicy(allow_hosts=["api.example.com"])
        ),
    )
    result = runner.run_skill_sync(
        skill, {"host": "127.0.0.1", "port": local_http_server}
    )
    assert result.success is True, result.stderr or result.error
    assert result.output["allowed"] is False
    assert "NetworkEgressDenied" in result.output["error"]


# ---------------------------------------------------------------------------
# Fail-closed behaviour of the injected guard itself.
# ---------------------------------------------------------------------------


def test_sitecustomize_template_fails_closed_instead_of_swallowing_errors():
    """The generated sitecustomize must NOT swallow install failures.

    A silent ``except: pass`` here would mean the policy said "egress denied"
    while the child process ran with unrestricted network access. The template
    therefore must not contain a bare swallowing handler around install().
    """
    from app.core.skill_engine.network_guard import SITECUSTOMIZE_TEMPLATE

    # The template must catch BaseException AND hard-exit, because CPython
    # merely *warns* when sitecustomize raises and continues startup.
    assert "except BaseException" in SITECUSTOMIZE_TEMPLATE
    assert "os._exit(" in SITECUSTOMIZE_TEMPLATE
    # install() must still be invoked, and never behind a swallowing handler.
    assert "_guard.install()" in SITECUSTOMIZE_TEMPLATE


def test_broken_guard_child_fails_closed(tmp_path):
    """If the guard cannot be installed the child must not run normally.

    We corrupt the copied guard module inside an installed guard directory, then
    start a real Python child with that directory on PYTHONPATH. Because
    sitecustomize re-raises, interpreter startup aborts and the process exits
    non-zero without executing the skill body.
    """
    import os
    import subprocess

    from app.core.skill_engine.network_guard import install_network_guard_dir

    guard_dir = install_network_guard_dir(tmp_path, ["example.com"])
    # Break the guard module so that importing/installing it explodes.
    (guard_dir / "cog_network_guard.py").write_text(
        "raise RuntimeError('simulated guard failure')\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = str(guard_dir) + os.pathsep + env.get("PYTHONPATH", "")
    env["COG_SKILL_NETWORK_ALLOW_HOSTS"] = "example.com"

    marker = tmp_path / "should_not_exist.txt"
    script = tmp_path / "skill_body.py"
    script.write_text(
        "from pathlib import Path\n"
        "Path(r'%s').write_text('ran', encoding='utf-8')\n" % marker,
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 78, proc.stdout
    assert "simulated guard failure" in (proc.stderr or "")
    assert "cog-network-guard" in (proc.stderr or "")
    assert not marker.exists(), "skill body must not run when the guard fails"


def test_working_guard_child_still_runs(tmp_path):
    """Sanity check that the fail-closed change does not break normal skills."""
    import os
    import subprocess

    from app.core.skill_engine.network_guard import install_network_guard_dir

    guard_dir = install_network_guard_dir(tmp_path, ["example.com"])

    env = dict(os.environ)
    env["PYTHONPATH"] = str(guard_dir) + os.pathsep + env.get("PYTHONPATH", "")
    env["COG_SKILL_NETWORK_ALLOW_HOSTS"] = "example.com"

    script = tmp_path / "ok.py"
    script.write_text("print('ok')\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout
