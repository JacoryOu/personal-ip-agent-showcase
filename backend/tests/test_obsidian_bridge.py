# -*- coding: utf-8 -*-
"""
Tests for the Obsidian Local Vault Bridge.

Coverage:
- scan_vault with mock vault directory
- Read-only verification (no files created/modified)
- Sync converts items to DNARecord with correct occurred_at
- Filter by tags and folders
- Empty vault handling
- Invalid path handling
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path
from datetime import datetime, timezone

import pytest

# Ensure backend root on sys.path
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.vault_path_guard import VaultPathError
from app.services.obsidian_service import ObsidianBridgeService
from app.core.db import init_db, engine
from sqlmodel import Session, select
from app.models.dna_record import DNARecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.fixture(autouse=True)
def _allow_tmp_vault_root(tmp_path: Path, monkeypatch) -> None:
    """Allow this test's tmp_path as an Obsidian vault root.

    Vault paths are now whitelist-enforced via OBSIDIAN_ALLOWED_ROOTS, so any
    test using a pytest temp directory must declare it as an allowed root.
    """
    monkeypatch.setenv("OBSIDIAN_ALLOWED_ROOTS", str(tmp_path))


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    """Create a minimal mock Obsidian vault with several .md files."""
    # Note 1: Has target tag #IP素材, YAML frontmatter, wikilinks, bold text
    (tmp_path / "note_ip_material.md").write_text(
        "---\n"
        "date: 2024-03-15\n"
        "tags: [IP素材, 养生]\n"
        "title: 节气养生笔记\n"
        "---\n\n"
        "# 节气养生笔记\n\n"
        "这是一篇关于[[春分养生]]的日记。\n"
        "> 清晨空腹一杯温水，能唤醒脾胃阳气。\n"
        "**阳气要升发，忌生冷寒凉。**\n"
        "- 每天坚持艾灸足三里，气血循环更顺畅。\n",
        encoding="utf-8",
    )

    # Note 2: Daily note with #养生 tag
    daily_folder = tmp_path / "DailyNotes"
    daily_folder.mkdir()
    (daily_folder / "2024-05-10.md").write_text(
        "---\n"
        "date: 2024-05-10\n"
        "tags: [日记, 每日]\n"
        "---\n\n"
        "今天早上喝了一杯陈皮茶，肠胃舒服很多。\n"
        "[[五年陈皮]][[老白茶]]\n",
        encoding="utf-8",
    )

    # Note 3: No matching tags — should be excluded by tag filter
    (tmp_path / "unrelated.md").write_text(
        "---\n"
        "tags: [读书, 学习]\n"
        "---\n\n"
        "读《原则》第三章。\n",
        encoding="utf-8",
    )

    # Note 4: Inline hashtag only (no frontmatter)
    (tmp_path / "inline_tag.md").write_text(
        "# 关于思考方法论\n\n"
        "今天发现了一个很有趣的规律。 #思考 #IP素材\n"
        "> 认知的边界决定行动的半径。\n",
        encoding="utf-8",
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScanVault:
    def test_scan_returns_structure(self, vault_dir: Path):
        result = ObsidianBridgeService.scan_vault(str(vault_dir))
        assert "total_files" in result
        assert "matched_files" in result
        assert "preview_items" in result
        assert result["total_files"] >= 4  # 3 top-level + 1 in DailyNotes

    def test_scan_all_files_no_filter(self, vault_dir: Path):
        result = ObsidianBridgeService.scan_vault(str(vault_dir))
        # With no filter all .md files are returned
        assert result["matched_files"] == result["total_files"]

    def test_scan_filter_by_tag(self, vault_dir: Path):
        result = ObsidianBridgeService.scan_vault(
            str(vault_dir), target_tags=["IP素材"]
        )
        assert result["matched_files"] >= 2  # note_ip_material.md + inline_tag.md
        for item in result["preview_items"]:
            # All returned items must have the tag or match inline
            assert any("IP素材" in t or "ip素材" in t.lower() for t in item["tags"]) or \
                   item["candidate_type"] in ("story", "dna", "daily_note")

    def test_scan_filter_by_folder(self, vault_dir: Path):
        result = ObsidianBridgeService.scan_vault(
            str(vault_dir), target_folders=["DailyNotes"]
        )
        assert result["matched_files"] == 1
        assert "2024-05-10" in result["preview_items"][0]["file_path"]

    def test_scan_extracts_wikilinks(self, vault_dir: Path):
        result = ObsidianBridgeService.scan_vault(
            str(vault_dir), target_folders=["DailyNotes"]
        )
        item = result["preview_items"][0]
        assert "五年陈皮" in item["wikilinks"] or "老白茶" in item["wikilinks"]

    def test_scan_extracts_golden_sentences(self, vault_dir: Path):
        result = ObsidianBridgeService.scan_vault(
            str(vault_dir), target_tags=["IP素材"]
        )
        # At least one item should have golden sentences
        golden_found = any(len(item["golden_sentences"]) > 0 for item in result["preview_items"])
        assert golden_found

    def test_scan_parses_date_from_frontmatter(self, vault_dir: Path):
        result = ObsidianBridgeService.scan_vault(
            str(vault_dir), target_tags=["IP素材"]
        )
        # note_ip_material.md has date: 2024-03-15
        dates = [item["date"] for item in result["preview_items"] if item.get("date")]
        assert any("2024-03-15" in d for d in dates)

    def test_scan_invalid_path_raises(self):
        # Paths outside the allowed roots are rejected as security violations,
        # not as missing files.
        with pytest.raises(VaultPathError) as exc_info:
            ObsidianBridgeService.scan_vault("/nonexistent/path/that/does/not/exist")
        assert exc_info.value.http_status == 400

    def test_scan_empty_vault(self, tmp_path: Path):
        result = ObsidianBridgeService.scan_vault(str(tmp_path))
        assert result["total_files"] == 0
        assert result["matched_files"] == 0
        assert result["preview_items"] == []


class TestReadOnly:
    """Verify that scanning never creates, modifies, or writes any file."""

    def test_no_files_created_during_scan(self, vault_dir: Path):
        before_files = set(vault_dir.rglob("*"))
        ObsidianBridgeService.scan_vault(str(vault_dir))
        after_files = set(vault_dir.rglob("*"))
        assert before_files == after_files, "Scan created/modified files in the vault!"

    def test_no_files_modified_during_scan(self, vault_dir: Path):
        """File mtimes must not change after scan."""
        mtimes_before = {f: f.stat().st_mtime for f in vault_dir.rglob("*.md")}
        ObsidianBridgeService.scan_vault(str(vault_dir))
        mtimes_after = {f: f.stat().st_mtime for f in vault_dir.rglob("*.md")}
        assert mtimes_before == mtimes_after, "Scan modified file timestamps!"


class TestSyncItems:
    def _make_session(self):
        return Session(engine)

    def test_sync_creates_dna_records(self, vault_dir: Path):
        scan_result = ObsidianBridgeService.scan_vault(
            str(vault_dir), target_tags=["IP素材"]
        )
        items = scan_result["preview_items"][:2]
        user_id = str(uuid.uuid4())

        with self._make_session() as session:
            result = ObsidianBridgeService.sync_items(
                vault_path=str(vault_dir),
                selected_items=items,
                user_id=user_id,
                session=session,
            )

        assert result["synced_count"] == len(items)
        assert len(result["records"]) == len(items)

    def test_sync_occurred_at_matches_note_date(self, vault_dir: Path):
        """Synced record must preserve occurred_at from the note's frontmatter date."""
        scan_result = ObsidianBridgeService.scan_vault(
            str(vault_dir), target_tags=["IP素材"]
        )
        # Find the item with known date 2024-03-15
        target_item = next(
            (i for i in scan_result["preview_items"] if "2024-03-15" in (i.get("date") or "")),
            None,
        )
        assert target_item is not None, "Expected note with date 2024-03-15 not found in preview"

        user_id = str(uuid.uuid4())
        with self._make_session() as session:
            result = ObsidianBridgeService.sync_items(
                vault_path=str(vault_dir),
                selected_items=[target_item],
                user_id=user_id,
                session=session,
            )
            record_meta = result["records"][0]
            assert "2024-03-15" in record_meta["occurred_at"]

    def test_sync_persists_to_db(self, vault_dir: Path):
        """Synced items must be readable from the database."""
        scan_result = ObsidianBridgeService.scan_vault(str(vault_dir))
        items = scan_result["preview_items"][:1]
        user_id = str(uuid.uuid4())
        parsed_uid = uuid.UUID(user_id)

        with self._make_session() as session:
            result = ObsidianBridgeService.sync_items(
                vault_path=str(vault_dir),
                selected_items=items,
                user_id=user_id,
                session=session,
            )
            created_id = uuid.UUID(result["records"][0]["id"])

        with self._make_session() as session:
            record = session.get(DNARecord, created_id)
            assert record is not None
            assert record.user_id == parsed_uid
            assert isinstance(record.dna_data, dict)
            assert record.dna_data["source"] == "obsidian_bridge"

    def test_sync_empty_list(self, vault_dir: Path):
        with self._make_session() as session:
            result = ObsidianBridgeService.sync_items(
                vault_path=str(vault_dir),
                selected_items=[],
                user_id=None,
                session=session,
            )
        assert result["synced_count"] == 0
        assert result["records"] == []

    def test_sync_does_not_write_to_vault(self, vault_dir: Path):
        """Sync must not create any files in the vault directory."""
        before_files = set(vault_dir.rglob("*"))
        scan_result = ObsidianBridgeService.scan_vault(str(vault_dir))
        items = scan_result["preview_items"][:1]

        with self._make_session() as session:
            ObsidianBridgeService.sync_items(
                vault_path=str(vault_dir),
                selected_items=items,
                user_id=None,
                session=session,
            )

        after_files = set(vault_dir.rglob("*"))
        assert before_files == after_files, "Sync created files in the vault!"


class TestAPIEndpoints:
    """Integration test using TestClient."""

    def test_scan_endpoint(self, vault_dir: Path):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        res = client.post(
            "/api/obsidian/scan",
            json={"vault_path": str(vault_dir)},
        )
        assert res.status_code == 200
        data = res.json()
        assert "total_files" in data
        assert "preview_items" in data

    def test_scan_endpoint_invalid_path(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        res = client.post(
            "/api/obsidian/scan",
            json={"vault_path": "/absolutely/nonexistent/vault"},
        )
        # Paths outside the allow-list are rejected as 4xx security errors.
        assert 400 <= res.status_code < 500

    def test_sync_endpoint(self, vault_dir: Path):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)

        # First scan
        scan_res = client.post(
            "/api/obsidian/scan",
            json={"vault_path": str(vault_dir)},
        )
        items = scan_res.json()["preview_items"][:1]

        sync_res = client.post(
            "/api/obsidian/sync",
            json={
                "vault_path": str(vault_dir),
                "selected_items": items,
                "user_id": str(uuid.uuid4()),
            },
        )
        assert sync_res.status_code == 200
        data = sync_res.json()
        assert data["synced_count"] >= 1

    def test_status_endpoint_no_path(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        res = client.get("/api/obsidian/status")
        assert res.status_code == 200
        data = res.json()
        assert data["configured"] is False

    def test_status_endpoint_with_valid_path(self, vault_dir: Path):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        res = client.get(f"/api/obsidian/status?vault_path={vault_dir}")
        assert res.status_code == 200
        data = res.json()
        assert data["configured"] is True
        assert data["note_count"] >= 4
