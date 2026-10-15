# -*- coding: utf-8 -*-
"""Central vault path allow-list guard for the Obsidian bridge.

The Obsidian bridge is READ-ONLY, but "read-only" over an arbitrary
user-supplied directory is still an arbitrary-file-read primitive. Every vault
path that enters the service must therefore be resolved and proven to live
inside one of the configured allowed roots.

Rules:
- Allowed roots come from ``OBSIDIAN_ALLOWED_ROOTS`` (comma separated).
- The default is deliberately narrow and project-local: ``<backend>/data/obsidian_vaults``.
  Nothing outside the project is readable by default.
- Validation is performed on ``Path.resolve()`` output, so ``..`` traversal and
  symlink / junction escapes are both rejected.
- Every failure raises :class:`VaultPathError`, which the API layer maps to 4xx.
"""
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Directory name (relative to the backend package root) used as the safe default.
DEFAULT_VAULT_DIRNAME = os.path.join("data", "obsidian_vaults")
ALLOWED_ROOTS_ENV = "OBSIDIAN_ALLOWED_ROOTS"


class VaultPathError(ValueError):
    """Raised when a vault path is rejected. Maps to HTTP 400 by default."""

    http_status = 400


class VaultPathNotFound(VaultPathError):
    """Raised when the (validated) vault path does not exist."""

    http_status = 404


class VaultPathNotADirectory(VaultPathError):
    """Raised when the (validated) vault path is not a directory."""

    http_status = 400


def _backend_root() -> Path:
    # app/core/vault_path_guard.py -> app/core -> app -> backend
    return Path(__file__).resolve().parents[2]


def default_allowed_root() -> Path:
    return (_backend_root() / DEFAULT_VAULT_DIRNAME).resolve()


def _split_roots(raw: str) -> List[str]:
    parts = []
    for chunk in raw.split(","):
        chunk = chunk.strip().strip('"').strip("'")
        if chunk:
            parts.append(chunk)
    return parts


def get_allowed_roots() -> List[Path]:
    """Return the resolved allow-list roots.

    ``OBSIDIAN_ALLOWED_ROOTS`` entries are resolved relative to the backend
    directory when they are not absolute, so relative config stays project-local.
    """
    raw = os.environ.get(ALLOWED_ROOTS_ENV, "")
    roots: List[Path] = []
    for entry in _split_roots(raw):
        candidate = Path(entry).expanduser()
        if not candidate.is_absolute():
            candidate = _backend_root() / candidate
        try:
            roots.append(candidate.resolve())
        except OSError:  # pragma: no cover - unresolvable path
            logger.warning("Ignoring unresolvable allowed root: %s", entry)
    if not roots:
        roots.append(default_allowed_root())
    return roots


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_vault_path(
    vault_path: str,
    *,
    allowed_roots: Optional[List[Path]] = None,
    must_exist: bool = True,
) -> Tuple[Path, Path]:
    """Validate ``vault_path`` against the allow-list.

    Returns ``(resolved_vault, matched_root)``.

    Raises:
        VaultPathError: path is empty, outside every allowed root, or (when
            ``must_exist``) missing / not a directory.
    """
    if not vault_path or not str(vault_path).strip():
        raise VaultPathError("Vault path must not be empty")

    raw = Path(str(vault_path).strip()).expanduser()
    try:
        resolved = raw.resolve()
    except OSError as exc:
        raise VaultPathError(f"Vault path cannot be resolved: {exc}") from exc

    roots = allowed_roots if allowed_roots is not None else get_allowed_roots()
    if not roots:
        # fail closed
        raise VaultPathError("No allowed vault roots are configured")

    for root in roots:
        if resolved == root or _is_within(resolved, root):
            if must_exist:
                if not resolved.exists():
                    raise VaultPathNotFound(f"Vault path does not exist: {resolved}")
                if not resolved.is_dir():
                    raise VaultPathNotADirectory(f"Vault path is not a directory: {resolved}")
            return resolved, root

    allowed_display = ", ".join(str(r) for r in roots)
    raise VaultPathError(
        f"Vault path is outside the allowed roots. Allowed roots: {allowed_display}"
    )

# --- Safe vault traversal -------------------------------------------------
# ``Path.rglob()`` follows Windows junctions / reparse points and symlinks. A
# junction planted inside an allowed vault therefore turns the read-only scan
# into an arbitrary-file-read primitive: files outside the vault are parsed,
# counted and returned to the client as previews, excerpts or note counts.
#
# The iterator below refuses to descend into any link-like entry and re-proves
# containment for every candidate, so a link can never widen the allow-list
# that ``validate_vault_path`` established.

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_DEVICE = 0x40


def _is_link_like(path: Path) -> bool:
    """Return True when ``path`` is a symlink, junction or other reparse point.

    ``os.path.islink`` covers symlinks (including Windows directory symlinks);
    ``st_file_attributes`` covers the broader reparse-point class, which is what
    ``mklink /J`` produces. Never raises: an entry we cannot stat is treated as
    link-like so the caller skips it (fail closed).
    """
    try:
        if os.path.islink(path):
            return True
        st = os.stat(path, follow_symlinks=False)
    except (OSError, ValueError):
        return True
    attrs = getattr(st, "st_file_attributes", None)
    if isinstance(attrs, int):
        if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
            return True
        if attrs & FILE_ATTRIBUTE_DEVICE:
            return True
    return False


def _safe_resolve(path: Path) -> Optional[Path]:
    """``Path.resolve()`` that returns ``None`` instead of raising."""
    try:
        return path.resolve()
    except (OSError, RuntimeError, ValueError):
        # OSError   -> permission denied / broken link
        # RuntimeError -> symlink loop
        return None


def iter_safe_markdown_files(vault_root: Path) -> List[Path]:
    """Return every ``*.md`` file physically inside ``vault_root``.

    Guarantees:

    - symlinks, junctions and reparse points are never followed or emitted;
    - every emitted path is re-resolved and proven to live inside
      ``vault_root.resolve()`` (post-traversal containment re-check);
    - unreadable or unresolvable entries are skipped instead of raising;
    - files are returned in a stable, case-insensitive sorted order so scan
      output stays deterministic.

    Returns an empty list when the root cannot be resolved or is not a
    directory.
    """
    root_resolved = _safe_resolve(Path(vault_root))
    if root_resolved is None or not root_resolved.is_dir():
        return []

    found: List[Path] = []

    # Iterative walk. os.walk lets us prune link-like directories *before*
    # descending into them, which Path.rglob cannot do.
    for dirpath, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        current = Path(dirpath)

        safe_dirs = []
        for name in dirnames:
            child = current / name
            if _is_link_like(child):
                logger.info("Skipping link-like vault directory: %s", child)
                continue
            safe_dirs.append(name)
        dirnames[:] = safe_dirs

        for name in filenames:
            if not name.lower().endswith(".md"):
                continue
            candidate = current / name
            if _is_link_like(candidate):
                logger.info("Skipping link-like vault file: %s", candidate)
                continue

            resolved = _safe_resolve(candidate)
            if resolved is None:
                logger.warning("Skipping unresolvable vault entry: %s", candidate)
                continue
            if not _is_within(resolved, root_resolved):
                logger.warning("Skipping vault entry outside vault root: %s", resolved)
                continue
            if not resolved.is_file():
                continue
            found.append(resolved)

    found.sort(key=lambda p: str(p).lower())
    return found
