import os
from pathlib import Path
import sys
import tempfile
import pytest

from app.core.skill_engine.discovery import SkillDefinition
from app.core.skill_engine.windows_sandbox import WindowsSandboxRunner, SAFE_ENV_WHITELIST, SENSITIVE_PATTERNS


def test_environment_sanitization():
    """Verifies sensitive keys are completely stripped and safe keys are retained."""
    runner = WindowsSandboxRunner()
    
    # Inject fake sensitive environment variables
    os.environ["OPENAI_API_KEY"] = "sk-secret-test-key-12345"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
    os.environ["DEEPSEEK_SECRET_TOKEN"] = "token-abcdef"
    
    sanitized = runner.build_sanitized_env()
    
    assert "OPENAI_API_KEY" not in sanitized
    assert "DATABASE_URL" not in sanitized
    assert "DEEPSEEK_SECRET_TOKEN" not in sanitized
    assert sanitized.get("PYTHONIOENCODING") == "utf-8"
    assert sanitized.get("PYTHONUTF8") == "1"
    
    # Check that whitelisted keys (like PATH) are preserved
    if "PATH" in os.environ:
        assert "PATH" in sanitized


def test_watchdog_timeout_kills_process():
    """Verifies the watchdog timer forcefully terminates a hanging/infinite process."""
    runner = WindowsSandboxRunner(default_timeout=1.5)
    
    with tempfile.TemporaryDirectory() as td:
        script = Path(td) / "hang.py"
        script.write_text("import time\nwhile True:\n    time.sleep(0.1)\n", encoding="utf-8")
        
        skill = SkillDefinition(
            name="hanging_skill",
            description="Simulates an infinite loop",
            entrypoint="hang.py",
            skill_dir=td,
        )
        
        result = runner.run_skill_sync(skill, {}, timeout_seconds=1.5)
        
        assert result.timed_out is True
        assert result.success is False
        assert "timed out" in (result.error or "").lower()


def test_wsb_configuration_generation():
    """Verifies generation of Microsoft Windows Sandbox (.wsb) XML profile."""
    runner = WindowsSandboxRunner()
    
    with tempfile.TemporaryDirectory() as td:
        dummy_entry = Path(td) / "run.py"
        dummy_entry.write_text("print('{}')", encoding="utf-8")
        
        skill = SkillDefinition(
            name="test_wsb_skill",
            description="Testing WSB profile generation",
            entrypoint="run.py",
            runner_mode="wsb",
            skill_dir=td,
        )
        
        work_dir = Path(td) / "work"
        work_dir.mkdir()
        
        wsb_xml = runner.generate_wsb_config(skill, {"arg1": "val1"}, work_dir)
        
        assert "<Configuration>" in wsb_xml
        assert "<VGpu>Disable</VGpu>" in wsb_xml
        assert "<ReadOnly>true</ReadOnly>" in wsb_xml
        assert "<LogonCommand>" in wsb_xml
        assert "run.py" in wsb_xml
