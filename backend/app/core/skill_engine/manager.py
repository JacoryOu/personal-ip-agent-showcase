"""Skill Manager singleton for orchestrating discovery and sandboxed execution."""

from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from app.core.skill_engine.discovery import SkillDefinition, discover_skills
from app.core.skill_engine.policy import ExecutionContext
from app.core.skill_engine.windows_sandbox import SandboxExecutionResult, WindowsSandboxRunner


class SkillManager:
    def __init__(self, skills_dir: Optional[Path | str] = None):
        self.skills_dir = skills_dir
        self.runner = WindowsSandboxRunner()
        self._skills: Dict[str, SkillDefinition] = {}
        self.reload()

    def reload(self) -> None:
        """Reloads all skills from the filesystem."""
        self._skills = discover_skills(self.skills_dir)

    def list_skills(self) -> List[Dict[str, Any]]:
        """Returns a summary list of all registered skills for the API/UI."""
        unique_skills = {skill.name: skill for skill in self._skills.values()}.values()
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "runner_mode": skill.runner_mode,
                "permissions": skill.permissions,
                "parameters": skill.parameters,
                "entrypoint": skill.entrypoint,
            }
            for skill in unique_skills
        ]

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        return self._skills.get(name)

    async def execute_skill(
        self,
        name: str,
        args: Dict[str, Any],
        runner_mode: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> SandboxExecutionResult:
        """Executes a discovered skill through the WindowsSandboxRunner.

        ``execution_context`` must be set explicitly to ``UNATTENDED`` for
        scheduled/batch runs; interactive callers can leave it as ``None``
        (defaults to interactive, or to COG_SKILL_EXECUTION_CONTEXT).
        """
        skill = self.get_skill(name)
        if not skill:
            return SandboxExecutionResult(
                success=False,
                error=f"Skill '{name}' not found. Available: {list(self._skills.keys())}",
                returncode=-1,
            )

        return await self.runner.run_skill(
            skill=skill,
            args=args,
            runner_mode=runner_mode,
            timeout_seconds=timeout_seconds,
            execution_context=execution_context,
        )

    def execute_skill_sync(
        self,
        name: str,
        args: Dict[str, Any],
        runner_mode: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        execution_context: Optional[ExecutionContext] = None,
    ) -> SandboxExecutionResult:
        """Synchronous skill execution."""
        skill = self.get_skill(name)
        if not skill:
            return SandboxExecutionResult(
                success=False,
                error=f"Skill '{name}' not found. Available: {list(self._skills.keys())}",
                returncode=-1,
            )

        return self.runner.run_skill_sync(
            skill=skill,
            args=args,
            runner_mode=runner_mode,
            timeout_seconds=timeout_seconds,
            execution_context=execution_context,
        )


_lock = Lock()
_instance: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SkillManager()
    return _instance


__all__ = ["SkillManager", "get_skill_manager"]
