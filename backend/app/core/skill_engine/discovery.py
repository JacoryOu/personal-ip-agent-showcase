"""Skill Discovery Engine for loading and parsing SKILL.md specifications."""

import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import yaml


class SkillDefinitionError(ValueError):
    """Raised when a SKILL.md definition is structurally invalid or unsafe.

    Currently used for entrypoint containment violations: the entrypoint is
    repository-supplied content that decides *which file the sandbox executes*,
    and the restricted token does not constrain that choice.
    """


def resolve_entrypoint_path(entrypoint: str, skill_dir: str | Path) -> Path:
    """Resolve ``entrypoint`` and prove it stays inside ``skill_dir``.

    Rules (fail closed):

    - the joined path must resolve without error;
    - it must live inside the resolved ``skill_dir`` (``relative_to`` must
      succeed). An absolute path is allowed only when it points inside it;
    - the target must not be a directory.

    Returns the resolved absolute path.

    Raises:
        SkillDefinitionError: on traversal (``../../evil.py``), on an absolute
            entrypoint outside the skill directory, or on an unresolvable /
            directory target.
    """
    try:
        skill_root = Path(skill_dir).resolve()
    except (OSError, RuntimeError) as exc:
        raise SkillDefinitionError(
            f"Skill directory cannot be resolved: {skill_dir!r}"
        ) from exc

    raw = Path(str(entrypoint))

    # An absolute entrypoint is not rejected outright -- it is accepted only if it
    # genuinely lives inside the skill directory. Everything else is joined to the
    # skill root first, so ``..`` traversal cannot escape before we check.
    try:
        candidate = raw.resolve() if raw.is_absolute() else (skill_root / raw).resolve()
    except (OSError, RuntimeError) as exc:
        raise SkillDefinitionError(
            f"Skill entrypoint cannot be resolved: {entrypoint!r}"
        ) from exc

    try:
        candidate.relative_to(skill_root)
    except ValueError:
        raise SkillDefinitionError(
            f"Skill entrypoint escapes the skill directory: {entrypoint!r}"
        ) from None

    # ``relative_to`` also succeeds for a sub-directory, so reject a target that
    # exists as a directory. A missing file is not rejected here -- the runner
    # performs that check and fails closed without starting a process.
    if candidate.is_dir():
        raise SkillDefinitionError(
            f"Skill entrypoint is a directory, not a file: {entrypoint!r}"
        )
    return candidate


class SkillDefinition(BaseModel):
    name: str
    description: str
    entrypoint: str
    runner_mode: str = "restricted_token"
    permissions: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    skill_dir: str
    readme_content: Optional[str] = None

    @property
    def entrypoint_path(self) -> Path:
        """Absolute, containment-checked path of the skill entrypoint.

        The entrypoint comes from `SKILL.md` YAML frontmatter, which is
        untrusted repository content. It must resolve to a path *inside*
        `skill_dir`; `../../evil.py` and absolute paths such as
        `C:\\other\\evil.py` are rejected.

        The restricted token drops privileges but does **not** restrict *which*
        file is executed, so this check is the only thing preventing a skill
        from pointing the sandbox at an arbitrary script.

        Raises:
            SkillDefinitionError: the entrypoint escapes `skill_dir` or cannot
                be resolved.
        """
        return resolve_entrypoint_path(self.entrypoint, self.skill_dir)

    def to_tool_definition(self) -> Dict[str, Any]:
        """Converts the skill definition to standard OpenAI Function Tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def find_default_skills_dir() -> Path:
    """Finds the default skills directory across worktree hierarchies."""
    current = Path.cwd().resolve()
    this_file = Path(__file__).resolve()
    candidates = [
        current / "skills",
        current.parent / "skills",
        current.parent.parent / "skills",
        this_file.parents[3] / "skills",
        this_file.parents[4] / "skills",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return current.parent / "skills"


def parse_skill_markdown(skill_file: Path) -> Optional[SkillDefinition]:
    """Parses a SKILL.md file with YAML frontmatter into a SkillDefinition."""
    try:
        raw_text = skill_file.read_text(encoding="utf-8-sig")
    except Exception:
        return None

    # Frontmatter regex: between --- and --- at the start
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw_text, re.DOTALL)
    if not match:
        return None

    frontmatter_raw, body = match.groups()
    try:
        meta = yaml.safe_load(frontmatter_raw)
        if not isinstance(meta, dict):
            return None
    except Exception:
        return None

    name = meta.get("name")
    entrypoint = meta.get("entrypoint")
    description = meta.get("description", "")
    if not name or not entrypoint:
        return None
    if not isinstance(entrypoint, str):
        # A non-string entrypoint (list, dict, int) would blow up path joining
        # in a confusing way; treat it as an invalid definition.
        return None

    skill_dir = skill_file.parent.resolve()

    # Containment is validated here, at load time, so an unsafe skill is never
    # registered. ``discover_skills`` therefore cannot expose it either.
    try:
        resolve_entrypoint_path(entrypoint, skill_dir)
    except SkillDefinitionError as exc:
        logging.getLogger(__name__).error(
            "Rejected skill definition %s: %s", skill_file, exc
        )
        return None

    return SkillDefinition(
        name=name,
        description=description,
        entrypoint=entrypoint,
        runner_mode=meta.get("runner_mode", "restricted_token"),
        permissions=meta.get("permissions", []),
        parameters=meta.get("parameters", {"type": "object", "properties": {}}),
        skill_dir=str(skill_dir),
        readme_content=body.strip() if body else None,
    )


def discover_skills(search_dir: Optional[Path | str] = None) -> Dict[str, SkillDefinition]:
    """Recursively searches for all SKILL.md files in the skills directory."""
    base_dir = Path(search_dir).resolve() if search_dir else find_default_skills_dir()
    skills: Dict[str, SkillDefinition] = {}

    if not base_dir.exists() or not base_dir.is_dir():
        return skills

    # Recursively search for SKILL.md / skill.md
    for file_path in base_dir.rglob("*.md"):
        if file_path.name.lower() == "skill.md":
            skill = parse_skill_markdown(file_path)
            if skill:
                skills[skill.name] = skill
                skills[skill.name.replace("_", "-")] = skill
                skills[skill.name.replace("-", "_")] = skill

    return skills


__all__ = [
    "SkillDefinition",
    "discover_skills",
    "parse_skill_markdown",
    "find_default_skills_dir",
]
