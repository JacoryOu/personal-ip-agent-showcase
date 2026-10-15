# -*- coding: utf-8 -*-
"""
Obsidian Local Vault Bridge Service.

STRICT READ-ONLY: This service NEVER writes, modifies, renames, or deletes
any file in the user's Obsidian vault directory. It only reads .md files.
"""
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session

from app.core.vault_path_guard import (
    VaultPathError,
    get_allowed_roots,
    iter_safe_markdown_files,
    validate_vault_path,
)
from app.models.dna_record import DNARecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
PreviewItem = Dict[str, Any]
ScanResult = Dict[str, Any]
SyncResult = Dict[str, Any]


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_YAML_KV_RE = re.compile(r"^(\w[\w\-]*)\s*:\s*(.+)$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|[^\[\]]*)?\]\]")
_HASHTAG_RE = re.compile(r"(?<!\w)#([\w\u4e00-\u9fff]+)")
_BOLD_RE = re.compile(r"\*\*([^*]{3,})\*\*")
_QUOTE_RE = re.compile(r"^>\s+(.+)$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(r"^-\s+(.{10,})$", re.MULTILINE)
_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


def _parse_frontmatter(raw: str) -> Tuple[Dict[str, str], str]:
    """Extract YAML frontmatter key-value pairs and return (fm_dict, body)."""
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return {}, raw

    fm_text = match.group(1)
    body = raw[match.end():].lstrip("\n")
    fm: Dict[str, str] = {}
    for m in _YAML_KV_RE.finditer(fm_text):
        fm[m.group(1).lower()] = m.group(2).strip().strip('"').strip("'")
    return fm, body


def _extract_date(fm: Dict[str, str], file_path: Path) -> Optional[datetime]:
    """Try to parse a date from frontmatter 'date', 'created', or file mtime."""
    for key in ("date", "created", "created_at", "time"):
        val = fm.get(key, "")
        if val:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
                try:
                    return datetime.strptime(val.strip()[:19], fmt[:len(val.strip()[:19])]).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
                try:
                    return datetime.fromisoformat(val.strip()).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
    # Fallback: file modification time
    try:
        mtime = file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except OSError:
        return datetime.now(timezone.utc)


def _extract_tags(fm: Dict[str, str], body: str) -> List[str]:
    """Collect tags from frontmatter 'tags' field and inline #hashtags."""
    tags: List[str] = []
    # Frontmatter tags (comma or space separated, or YAML list items)
    raw_tags = fm.get("tags", "")
    if raw_tags:
        # Handle YAML inline list: [tag1, tag2]
        raw_tags = raw_tags.strip("[]")
        for part in re.split(r"[,\s]+", raw_tags):
            part = part.strip().lstrip("#")
            if part:
                tags.append(part)
    # Inline hashtags from body
    for m in _HASHTAG_RE.finditer(body):
        tag = m.group(1)
        if tag not in tags:
            tags.append(tag)
    return [t for t in tags if t]


def _extract_excerpt_and_candidates(body: str) -> Tuple[str, List[str]]:
    """Extract an excerpt (first 200 chars) and candidate golden sentences."""
    candidates: List[str] = []
    # Quotes
    candidates += [m.group(1).strip() for m in _QUOTE_RE.finditer(body)]
    # Bold phrases
    candidates += [m.group(1).strip() for m in _BOLD_RE.finditer(body)]
    # List items (long enough)
    candidates += [m.group(1).strip() for m in _LIST_ITEM_RE.finditer(body)]
    # Headings as structure indicators
    candidates += [m.group(1).strip() for m in _HEADING_RE.finditer(body)]

    # Deduplicate while preserving order
    seen = set()
    unique_candidates: List[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    # Excerpt = first non-empty line of body, max 200 chars
    excerpt = ""
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("---"):
            excerpt = line[:200]
            break

    return excerpt, unique_candidates[:10]


def _classify_candidate(tags: List[str], body: str) -> str:
    """Heuristically classify a note as 'story', 'dna', or 'daily_note'."""
    tag_str = " ".join(tags).lower()
    body_lower = body.lower()
    if any(kw in tag_str for kw in ("日记", "每日", "daily", "周记")):
        return "daily_note"
    if any(kw in body_lower for kw in ("我发现", "我认为", "观点", "方法论", "规律")):
        return "dna"
    return "story"


def _matches_filter(
    tags: List[str],
    file_path: Path,
    target_tags: Optional[List[str]],
    target_folders: Optional[List[str]],
) -> bool:
    """Return True if the note passes the tag/folder filter."""
    if not target_tags and not target_folders:
        return True  # No filter → accept all

    tags_lower = [t.lstrip("#").lower() for t in tags]
    # Check tags
    if target_tags:
        for tt in target_tags:
            if tt.lstrip("#").lower() in tags_lower:
                return True
    # Check folders
    if target_folders:
        path_str = str(file_path).replace("\\", "/")
        for folder in target_folders:
            if folder.rstrip("/") in path_str:
                return True
    return False


# ---------------------------------------------------------------------------
# Public Service class
# ---------------------------------------------------------------------------

class ObsidianBridgeService:
    """
    Read-only gateway to an Obsidian local Markdown vault.

    SAFETY GUARANTEE: No write operation is ever performed against the vault.
    All methods are class-methods for stateless, functional design.
    """

    @classmethod
    def scan_vault(
        cls,
        vault_path: str,
        target_tags: Optional[List[str]] = None,
        target_folders: Optional[List[str]] = None,
    ) -> ScanResult:
        """
        Walk the vault directory, parse .md files, and return a scan preview.

        Returns:
            {
                total_files: int,
                matched_files: int,
                preview_items: [PreviewItem],
            }
        """
        vault, _root = validate_vault_path(vault_path)

        total = 0
        preview_items: List[PreviewItem] = []

        for md_file in iter_safe_markdown_files(vault):
            total += 1
            try:
                # Read-only open
                raw = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                logger.warning("Cannot read %s: %s", md_file, exc)
                continue

            fm, body = _parse_frontmatter(raw)
            tags = _extract_tags(fm, body)

            if not _matches_filter(tags, md_file, target_tags, target_folders):
                continue

            date_dt = _extract_date(fm, md_file)
            wikilinks = _WIKILINK_RE.findall(raw)
            excerpt, candidates = _extract_excerpt_and_candidates(body)
            candidate_type = _classify_candidate(tags, body)
            title = (
                fm.get("title")
                or _HEADING_RE.search(body) and _HEADING_RE.search(body).group(1)
                or md_file.stem
            )

            preview_items.append(
                {
                    "file_path": str(md_file),
                    "title": title,
                    "date": date_dt.isoformat() if date_dt else None,
                    "tags": tags,
                    "excerpt": excerpt,
                    "wikilinks": wikilinks[:20],
                    "candidate_type": candidate_type,
                    "golden_sentences": candidates,
                    "aliases": (fm.get("aliases", "") or "").split(","),
                }
            )

        return {
            "total_files": total,
            "matched_files": len(preview_items),
            "preview_items": preview_items,
        }

    @classmethod
    def sync_items(
        cls,
        vault_path: str,
        selected_items: List[Dict[str, Any]],
        user_id: Optional[str],
        session: Session,
    ) -> SyncResult:
        """
        Convert selected preview items into DNARecord entries with Obsidian lineage metadata.

        Does NOT write anything to the vault.
        """
        if not selected_items:
            return {"synced_count": 0, "records": []}

        # The vault path itself is not written to, but it is the caller's claim
        # about where the selected notes came from. Validate it so a sync cannot
        # be used to launder notes read from outside the allow-list.
        validated_vault, _root = validate_vault_path(vault_path, must_exist=False)

        try:
            parsed_uid = uuid.UUID(str(user_id)) if user_id else uuid.uuid4()
        except (ValueError, AttributeError):
            import hashlib
            parsed_uid = uuid.UUID(hashlib.md5(str(user_id).encode()).hexdigest())

        records_created = []
        for item in selected_items:
            # Parse occurred_at from item date
            date_str = item.get("date")
            occurred_at: Optional[datetime] = None
            if date_str:
                try:
                    occurred_at = datetime.fromisoformat(date_str)
                except ValueError:
                    occurred_at = datetime.now(timezone.utc)

            candidate_type = item.get("candidate_type", "story")
            tags = item.get("tags", [])
            golden_sentences = item.get("golden_sentences", [])

            dna_data: Dict[str, Any] = {
                "source": "obsidian_bridge",
                "source_path": item.get("file_path", ""),
                "title": item.get("title", ""),
                "excerpt": item.get("excerpt", ""),
                "candidate_type": candidate_type,
                "tags": tags,
                "wikilinks": item.get("wikilinks", []),
                "golden_sentences": golden_sentences,
                "occurred_at": occurred_at.isoformat() if occurred_at else None,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }

            record = DNARecord(
                id=uuid.uuid4(),
                user_id=parsed_uid,
                dna_data=dna_data,
            )
            session.add(record)
            records_created.append(
                {
                    "id": str(record.id),
                    "title": item.get("title", ""),
                    "candidate_type": candidate_type,
                    "occurred_at": occurred_at.isoformat() if occurred_at else None,
                }
            )

        session.commit()
        return {
            "synced_count": len(records_created),
            "records": records_created,
        }

    @classmethod
    def get_status(
        cls,
        vault_path: Optional[str],
        session: Session,
    ) -> Dict[str, Any]:
        """Return configured status and note count for a given vault path."""
        resolved_vault: Optional[Path] = None
        allowed = False
        if vault_path:
            try:
                resolved_vault, _root = validate_vault_path(vault_path, must_exist=False)
                allowed = True
            except VaultPathError as exc:
                logger.warning("Rejected Obsidian vault path: %s", exc)

        configured = bool(resolved_vault is not None and resolved_vault.is_dir())
        note_count = 0
        if configured and resolved_vault is not None:
            try:
                note_count = len(iter_safe_markdown_files(resolved_vault))
            except OSError:
                note_count = 0

        from sqlmodel import select as sql_select, func as sql_func
        from app.models.dna_record import DNARecord as _DNARecord

        # Count synced records that came from obsidian
        try:
            all_records = session.exec(sql_select(_DNARecord)).all()
            synced_count = sum(
                1 for r in all_records
                if isinstance(r.dna_data, dict) and r.dna_data.get("source") == "obsidian_bridge"
            )
        except Exception:
            synced_count = 0

        return {
            "configured": configured,
            "vault_path": str(resolved_vault) if resolved_vault else vault_path,
            "path_allowed": allowed,
            "allowed_roots": [str(r) for r in get_allowed_roots()],
            "note_count": note_count,
            "synced_count": synced_count,
            "last_scan_at": None,  # Future: persist scan timestamp to settings
        }
