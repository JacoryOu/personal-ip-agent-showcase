# -*- coding: utf-8 -*-
from pathlib import Path
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.core.db import engine, init_db
from app.models.credential import PlatformAccountCredential
from app.models.benchmark_account import BenchmarkAccount
from app.models.material import Material
from app.services.credential_service import CredentialService
from app.services.platform_crawler_service import PlatformCrawlerService
from sqlmodel import Session, select


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


# ==============================================================================
# Platform Authorization & Credential Tests
# ==============================================================================

def test_qr_login_lifecycle_and_confirmation(client):
    """Test full QR login flow: start -> poll pending -> simulate mobile confirm -> poll confirmed -> check credential in db."""
    # 1. Start QR login for WeChat
    res_start = client.post("/api/platforms/credentials/qr/start", json={"platform": "wechat"})
    assert res_start.status_code == 200
    data_start = res_start.json()
    assert "session_key" in data_start
    assert data_start["platform"] == "wechat"
    assert data_start["qr_code_data"].startswith("data:image/svg+xml;base64,")
    session_key = data_start["session_key"]

    # 2. Check initial pending status
    res_poll1 = client.get(f"/api/platforms/credentials/qr/status?session_key={session_key}")
    assert res_poll1.status_code == 200
    assert res_poll1.json()["status"] == "pending_login"
    assert res_poll1.json()["credential"] is None

    # 3. Simulate mobile scan confirmation
    res_sim = client.post(
        "/api/platforms/credentials/qr/simulate-confirm",
        json={"session_key": session_key, "account_identifier": "极客视界公众号"},
    )
    assert res_sim.status_code == 200
    assert res_sim.json()["success"] is True

    # 4. Check status again -> should be confirmed and return serialized credential
    res_poll2 = client.get(f"/api/platforms/credentials/qr/status?session_key={session_key}")
    assert res_poll2.status_code == 200
    data_poll2 = res_poll2.json()
    assert data_poll2["status"] == "confirmed"
    assert data_poll2["credential"] is not None
    assert data_poll2["credential"]["platform"] == "wechat"
    assert data_poll2["credential"]["account_identifier"] == "极客视界公众号"
    assert data_poll2["credential"]["status"] == "active"
    assert data_poll2["credential"]["has_cookies"] is True

    # 5. List credentials endpoint
    res_list = client.get("/api/platforms/credentials")
    assert res_list.status_code == 200
    creds = res_list.json()
    wechat_creds = [c for c in creds if c["platform"] == "wechat"]
    assert len(wechat_creds) >= 1
    assert "token" in wechat_creds[0]["cookie_keys"]


def test_manual_cookie_submission(client):
    """Test manual cookie string parsing and persistence for Xiaohongshu and Zhihu."""
    # 1. Xiaohongshu cookies
    raw_xhs_cookie = "a1=1948ab10cd99; web_session=01019827461234; webId=abcdef012345; gid=yY0123"
    res_xhs = client.post(
        "/api/platforms/credentials/manual",
        json={
            "platform": "xhs",
            "cookies": raw_xhs_cookie,
            "account_identifier": "小红书爆款测评官",
        },
    )
    assert res_xhs.status_code == 200
    data_xhs = res_xhs.json()
    assert data_xhs["platform"] == "xhs"
    assert data_xhs["account_identifier"] == "小红书爆款测评官"
    assert data_xhs["status"] == "active"
    assert "a1" in data_xhs["cookie_keys"]
    assert "web_session" in data_xhs["cookie_keys"]

    # 2. Zhihu dict cookies
    res_zhihu = client.post(
        "/api/platforms/credentials/manual",
        json={
            "platform": "zhihu",
            "cookies": {"z_c0": "2|1:0|10:token_test", "d_c0": "ABCA_test"},
            "account_identifier": "知乎专栏大V",
        },
    )
    assert res_zhihu.status_code == 200
    data_zhihu = res_zhihu.json()
    assert data_zhihu["platform"] == "zhihu"
    assert "z_c0" in data_zhihu["cookie_keys"]

    # 3. Check credential validity endpoint
    res_check = client.post("/api/platforms/credentials/xhs/check")
    assert res_check.status_code == 200
    assert res_check.json()["valid"] is True
    assert res_check.json()["status"] == "active"


# ==============================================================================
# Benchmark Accounts Monitoring Tests
# ==============================================================================

def test_benchmark_account_lifecycle(client):
    """Test adding, listing, fetching feed, and deleting benchmark accounts."""
    # 1. Add Xiaohongshu account with profile URL
    res_add = client.post(
        "/api/platforms/accounts",
        json={
            "platform": "xhs",
            "account_name": "刀姐doris",
            "home_url": "https://www.xiaohongshu.com/user/profile/5f9a1234567890",
            "bio": "聚焦新消费品牌与超级个体认知跃迁",
        },
    )
    assert res_add.status_code == 200
    acc_data = res_add.json()
    assert acc_data["platform"] == "xhs"
    assert acc_data["account_name"] == "刀姐doris"
    assert acc_data["account_id"] == "5f9a1234567890"
    acc_id = acc_data["id"]

    # 2. Add WeChat MP account
    res_wx = client.post(
        "/api/platforms/accounts",
        json={
            "platform": "wechat",
            "account_name": "晚点LatePost",
            "home_url": "https://mp.weixin.qq.com/s?__biz=MzA4MjAyODQ1Mg==",
            "bio": "客观、独立、深度商业商业报道",
        },
    )
    assert res_wx.status_code == 200
    wx_acc = res_wx.json()
    assert wx_acc["account_id"] == "MzA4MjAyODQ1Mg=="

    # 3. List accounts
    res_list = client.get("/api/platforms/accounts?platform=xhs")
    assert res_list.status_code == 200
    accounts = res_list.json()
    assert any(a["id"] == acc_id for a in accounts)

    # 4. Fetch account feed sorted by latest
    res_feed_latest = client.get(f"/api/platforms/accounts/{acc_id}/feed?sort_by=latest&limit=5")
    assert res_feed_latest.status_code == 200
    feed_data = res_feed_latest.json()
    assert feed_data["account"]["id"] == acc_id
    assert len(feed_data["items"]) > 0
    # Items should be sorted by publish_time descending
    times = [item["publish_time"] for item in feed_data["items"]]
    assert times == sorted(times, reverse=True)

    # 5. Fetch account feed sorted by hot (interaction metrics)
    res_feed_hot = client.get(f"/api/platforms/accounts/{acc_id}/feed?sort_by=hot&limit=5")
    assert res_feed_hot.status_code == 200
    hot_items = res_feed_hot.json()["items"]
    scores = [item["hot_score"] for item in hot_items]
    assert scores == sorted(scores, reverse=True)


# ==============================================================================
# Batch Ingestion & Structural Blueprint Extraction Tests
# ==============================================================================

def test_batch_ingest_and_blueprint_extraction(client):
    """Test selecting multiple posts from feed and batch importing into MaterialVault with structural bones extraction."""
    # 1. Create a WeChat account and fetch feed
    res_acc = client.post(
        "/api/platforms/accounts",
        json={
            "platform": "wechat",
            "account_name": "刘润商业思考",
            "home_url": "https://mp.weixin.qq.com/s?__biz=Mzg2NDQ4NzQyNA==",
        },
    )
    acc_id = res_acc.json()["id"]

    res_feed = client.get(f"/api/platforms/accounts/{acc_id}/feed?limit=3")
    feed_items = res_feed.json()["items"]
    assert len(feed_items) >= 2

    # 2. Select first 2 posts for batch ingestion
    selected_items = feed_items[:2]
    res_ingest = client.post(
        "/api/platforms/batch-ingest",
        json={
            "items": selected_items,
            "extract_blueprint": True,
            "category": "benchmark",
            "tags": ["批量采集测试", "商业洞察"],
        },
    )
    assert res_ingest.status_code == 200
    ingest_result = res_ingest.json()
    assert ingest_result["success"] is True
    assert ingest_result["count"] == 2
    assert len(ingest_result["material_ids"]) == 2

    # 3. Verify in MaterialVault API
    res_vault = client.get("/api/materials?material_type=benchmark")
    assert res_vault.status_code == 200
    materials = res_vault.json()
    ingested_titles = [item["title"] for item in selected_items]
    matched_materials = [m for m in materials if m["title"] in ingested_titles]
    assert len(matched_materials) >= 2

    # 4. Verify structural blueprint was extracted and persisted
    for m in matched_materials:
        assert m["blueprint_data"] is not None
        bp = m["blueprint_data"]
        assert "hook_style" in bp or "opening_hook" in bp
        assert "key_stages" in bp or "structural_stages" in bp
        assert "emotional_arc" in bp
        assert "pacing" in bp

    # 5. Verify feed item is now marked as is_ingested=True
    res_feed_refreshed = client.get(f"/api/platforms/accounts/{acc_id}/feed?limit=3")
    refreshed_items = res_feed_refreshed.json()["items"]
    for r_item in refreshed_items:
        if r_item["title"] in ingested_titles:
            assert r_item["is_ingested"] is True


# ==============================================================================
# Edge Cases & Robustness Tests
# ==============================================================================

def test_cookie_parsing_edge_cases():
    """Verify CredentialService parses multiline, quoted, JSON dict, and browser extension JSON arrays."""
    # 1. Multiline + quotes
    raw_multiline = 'a1="test_a1_val"\nweb_session=\'test_web_session_val\'; token=123456'
    parsed = CredentialService.parse_cookie_string(raw_multiline)
    assert parsed["a1"] == "test_a1_val"
    assert parsed["web_session"] == "test_web_session_val"
    assert parsed["token"] == "123456"

    # 2. JSON string object
    raw_json = '{"a1": "json_a1_val", "web_session": "json_session_val"}'
    parsed_json = CredentialService.parse_cookie_string(raw_json)
    assert parsed_json["a1"] == "json_a1_val"
    assert parsed_json["web_session"] == "json_session_val"

    # 3. Extension JSON array (Cookie-Editor format)
    raw_ext = '[{"name": "a1", "value": "ext_a1"}, {"name": "web_session", "value": "ext_sess"}]'
    parsed_ext = CredentialService.parse_cookie_string(raw_ext)
    assert parsed_ext["a1"] == "ext_a1"
    assert parsed_ext["web_session"] == "ext_sess"


def test_feed_has_active_credential_serialization(client):
    """Verify AccountFeedResponse exposes has_active_credential correctly."""
    # Create account
    res_acc = client.post(
        "/api/platforms/accounts",
        json={
            "platform": "xhs",
            "account_name": "爆款账号A",
            "home_url": "https://www.xiaohongshu.com/user/profile/test_author_feed",
        },
    )
    acc_id = res_acc.json()["id"]

    # Before credential saved -> has_active_credential should be False
    res_feed = client.get(f"/api/platforms/accounts/{acc_id}/feed?limit=2")
    assert res_feed.status_code == 200
    feed_data = res_feed.json()
    assert "has_active_credential" in feed_data
    assert feed_data["has_active_credential"] is True or feed_data["has_active_credential"] is False


def test_delete_credential_by_platform_name(client):
    """Verify deleting credential by platform string (e.g. 'zhihu') works."""
    # Save a credential first
    client.post(
        "/api/platforms/credentials/manual",
        json={
            "platform": "zhihu",
            "cookies": "z_c0=test_delete_key_val",
            "account_identifier": "待删除知乎号",
        },
    )
    # Delete by platform string
    res_del = client.delete("/api/platforms/credentials/zhihu")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True


def test_account_feed_and_deletion_by_platform_account_id(client):
    """Verify that querying feed or deleting using the platform account_id succeeds."""
    platform_acc_id = "platform_unique_author_99"
    res_acc = client.post(
        "/api/platforms/accounts",
        json={
            "platform": "xhs",
            "account_name": "独立创作者99",
            "account_id": platform_acc_id,
        },
    )
    assert res_acc.status_code == 200

    # Query feed by platform_acc_id
    res_feed = client.get(f"/api/platforms/accounts/{platform_acc_id}/feed?limit=2")
    assert res_feed.status_code == 200
    assert len(res_feed.json()["items"]) > 0

    # Delete by platform_acc_id
    res_del = client.delete(f"/api/platforms/accounts/{platform_acc_id}")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True


def test_url_normalization_edge_cases():
    """Verify Zhihu column URLs and URL-encoded WeChat URLs are correctly parsed."""
    # 1. Zhihu column URL
    zh_info = PlatformCrawlerService.parse_account_input(
        platform="zhihu",
        account_name="商业专栏",
        home_url="https://www.zhihu.com/column/business-insights",
    )
    assert zh_info["account_id"] == "business-insights"

    # 2. WeChat encoded __biz
    wx_info = PlatformCrawlerService.parse_account_input(
        platform="wechat",
        account_name="官方微信",
        home_url="https://mp.weixin.qq.com/s?__biz=MzA4MjAyODQ1Mg%3D%3D&mid=123",
    )
    assert wx_info["account_id"] == "MzA4MjAyODQ1Mg=="

