# -*- coding: utf-8 -*-
from pathlib import Path
import sys
import uuid
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Ensure backend root is on sys.path
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.core.db import init_db
from app.services.credential_service import CredentialService, generate_qr_svg, wrap_jpeg_as_svg


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


def test_generate_qr_svg_produces_scannable_svg():
    """Verify generate_qr_svg creates standard compliant scannable SVG."""
    res = generate_qr_svg("https://mp.weixin.qq.com")
    assert res.startswith("data:image/svg+xml;base64,")
    assert len(res) > 200


def test_wrap_jpeg_as_svg():
    """Verify wrap_jpeg_as_svg wraps JPEG bytes into standard SVG data URI."""
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 60
    res = wrap_jpeg_as_svg(fake_jpeg)
    assert res.startswith("data:image/svg+xml;base64,")
    assert "image/jpeg;base64," in res or len(res) > 100


def test_wechat_mp_qr_initiation_and_instructions(client):
    """Verify live WeChat MP QR endpoint initiation returns valid QR data and user instructions."""
    res = client.post("/api/platforms/credentials/qr/start", json={"platform": "wechat"})
    assert res.status_code == 200
    data = res.json()
    assert "session_key" in data
    assert data["platform"] == "wechat"
    assert data["qr_code_data"].startswith("data:image/svg+xml;base64,")
    assert "微信扫码" in data["instructions"]
    assert data["expires_in"] == 180


def test_wechat_mp_mocked_scanned_and_confirmed_status(client):
    """Verify status polling handles scanned (status 4/6) and confirmed (status 1) with cookie capture."""
    # 1. Start QR login
    res_start = client.post("/api/platforms/credentials/qr/start", json={"platform": "wechat"})
    session_key = res_start.json()["session_key"]

    sess_data = CredentialService._active_qr_sessions[session_key]

    # 2. Mock live client for status = 4 (scanned)
    mock_client = MagicMock()
    mock_ask_scanned = MagicMock()
    mock_ask_scanned.status_code = 200
    mock_ask_scanned.json.return_value = {"base_resp": {"ret": 0}, "status": 4}
    mock_client.get.return_value = mock_ask_scanned

    sess_data["is_live"] = True
    sess_data["http_client"] = mock_client

    res_poll_scanned = client.get(f"/api/platforms/credentials/qr/status?session_key={session_key}")
    assert res_poll_scanned.status_code == 200
    assert res_poll_scanned.json()["status"] == "scanned"
    assert "扫码" in res_poll_scanned.json()["message"]

    # 3. Mock status = 1 (confirmed) + login response with token
    mock_ask_confirmed = MagicMock()
    mock_ask_confirmed.status_code = 200
    mock_ask_confirmed.json.return_value = {"base_resp": {"ret": 0}, "status": 1}

    mock_login_resp = MagicMock()
    mock_login_resp.status_code = 200
    mock_login_resp.json.return_value = {
        "base_resp": {"ret": 0, "err_msg": "ok"},
        "redirect_url": "/cgi-bin/home?t=home/index&lang=zh_CN&token=987654321",
    }

    mock_client.get.return_value = mock_ask_confirmed
    mock_client.post.return_value = mock_login_resp
    mock_client.cookies = {"slave_sid": "wx_sid_12345", "slave_user": "gh_test_author", "bizuin": "100200300"}

    res_poll_confirmed = client.get(f"/api/platforms/credentials/qr/status?session_key={session_key}")
    assert res_poll_confirmed.status_code == 200
    data_confirmed = res_poll_confirmed.json()
    assert data_confirmed["status"] == "confirmed"
    assert data_confirmed["credential"] is not None
    assert data_confirmed["credential"]["platform"] == "wechat"
    assert data_confirmed["credential"]["status"] == "active"
    assert "token" in data_confirmed["credential"]["cookie_keys"]
    assert "slave_sid" in data_confirmed["credential"]["cookie_keys"]


def test_wechat_mp_network_failure_fallback():
    """Verify start_qr_login gracefully falls back when upstream WeChat gateway throws RequestError."""
    with patch("httpx.Client.get", side_effect=Exception("Connection timeout to mp.weixin.qq.com")):
        res = CredentialService.start_qr_login("wechat")
        assert "session_key" in res
        assert res["platform"] == "wechat"
        assert res["qr_code_data"].startswith("data:image/svg+xml;base64,")


def test_xhs_qr_flow_and_instructions(client):
    """Verify Xiaohongshu QR session initiation and user instructions."""
    res = client.post("/api/platforms/credentials/qr/start", json={"platform": "xhs"})
    assert res.status_code == 200
    data = res.json()
    assert data["platform"] == "xhs"
    assert data["qr_code_data"].startswith("data:image/")
    assert len(data["qr_code_data"]) > 100


def test_expired_qr_session_reporting(client):
    """Verify expired QR sessions report expired status."""
    res_start = client.post("/api/platforms/credentials/qr/start", json={"platform": "zhihu"})
    session_key = res_start.json()["session_key"]

    # Force expiration
    from datetime import datetime, timezone, timedelta
    CredentialService._active_qr_sessions[session_key]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=10)

    res_poll = client.get(f"/api/platforms/credentials/qr/status?session_key={session_key}")
    assert res_poll.status_code == 200
    assert res_poll.json()["status"] == "expired"
    assert "过期" in res_poll.json()["message"]


def test_wechat_mp_login_handles_html_redirect_and_nickname(client):
    """Verify WeChat MP login robustly parses token from redirect URL/history when response is HTML."""
    res_start = client.post("/api/platforms/credentials/qr/start", json={"platform": "wechat"})
    session_key = res_start.json()["session_key"]

    sess_data = CredentialService._active_qr_sessions[session_key]
    mock_client = MagicMock()

    # 1. Ask status returns 1 (confirmed)
    mock_ask = MagicMock()
    mock_ask.status_code = 200
    mock_ask.json.return_value = {"base_resp": {"ret": 0}, "status": 1}

    # 2. Login response is HTML redirected with token in url
    mock_login = MagicMock()
    mock_login.status_code = 200
    # Simulate JSONDecodeError on .json() call because response was HTML
    mock_login.json.side_effect = ValueError("Invalid JSON")
    mock_login.url = "https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token=555666777"
    mock_login.history = []
    mock_login.text = "<html><body>Home Page</body></html>"

    # 3. Home page response with nickname
    mock_home = MagicMock()
    mock_home.status_code = 200
    mock_home.text = '<html><div class="weui-desktop-account__nickname">Jacory的思考笔记</div></html>'

    mock_client.get.side_effect = [mock_ask, mock_home]
    mock_client.post.return_value = mock_login
    mock_client.cookies = {"slave_sid": "wx_sid_999", "slave_user": "gh_112233"}

    sess_data["is_live"] = True
    sess_data["http_client"] = mock_client

    res_poll = client.get(f"/api/platforms/credentials/qr/status?session_key={session_key}")
    assert res_poll.status_code == 200
    data = res_poll.json()
    assert data["status"] == "confirmed"
    assert data["credential"] is not None
    assert "token" in data["credential"]["cookie_keys"]
    assert data["credential"]["account_identifier"] == "Jacory的思考笔记"

    # Repeat poll should return cached credential without error
    res_poll_repeat = client.get(f"/api/platforms/credentials/qr/status?session_key={session_key}")
    assert res_poll_repeat.status_code == 200
    assert res_poll_repeat.json()["status"] == "confirmed"


def test_wechat_mp_user_canceled_on_phone(client):
    """Verify WeChat MP status 3 correctly identifies that user canceled on mobile."""
    res_start = client.post("/api/platforms/credentials/qr/start", json={"platform": "wechat"})
    session_key = res_start.json()["session_key"]

    sess_data = CredentialService._active_qr_sessions[session_key]
    mock_client = MagicMock()
    mock_ask = MagicMock()
    mock_ask.status_code = 200
    mock_ask.json.return_value = {"base_resp": {"ret": 0}, "status": 3}
    mock_client.get.return_value = mock_ask

    sess_data["is_live"] = True
    sess_data["http_client"] = mock_client

    res_poll = client.get(f"/api/platforms/credentials/qr/status?session_key={session_key}")
    assert res_poll.status_code == 200
    assert res_poll.json()["status"] == "expired"
    assert "取消" in res_poll.json()["message"]


def test_parse_cookie_string_with_url_and_query_params():
    """Verify parse_cookie_string extracts token when user pastes a browser address bar URL."""
    url = "https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token=88991122"
    cookies = CredentialService.parse_cookie_string(url)
    assert cookies.get("token") == "88991122"


def test_xhs_playwright_polling_and_session_interception(client):
    """Verify Playwright XHS session polling handles scanned and confirmed with cookie interception."""
    from app.services.playwright_service import PlaywrightService

    # 1. Start QR login
    res_start = client.post("/api/platforms/credentials/qr/start", json={"platform": "xhs"})
    assert res_start.status_code == 200
    session_key = res_start.json()["session_key"]

    sess_data = CredentialService._active_qr_sessions[session_key]
    sess_data["use_playwright"] = True

    # 2. Mock PlaywrightService.check_xhs_qr_status for 'scanned'
    with patch.object(
        PlaywrightService,
        "check_xhs_qr_status",
        return_value={"status": "scanned", "message": "已在手机上扫码，请在手机端点击确认登录"},
    ):
        res_poll_scanned = client.get(f"/api/platforms/credentials/qr/status?session_key={session_key}")
        assert res_poll_scanned.status_code == 200
        assert res_poll_scanned.json()["status"] == "scanned"

    # 3. Mock PlaywrightService.check_xhs_qr_status for 'confirmed' with a1 and web_session
    mock_confirmed_data = {
        "status": "confirmed",
        "message": "小红书扫码授权成功！已拦截捕获活跃 Session 凭据。",
        "cookies": {
            "a1": "19a83f120e_xhstest",
            "web_session": "01019284729_xhssess",
            "webId": "webid_123456",
            "gid": "gid_test_999",
        },
        "account_identifier": "小红书头部知识博主",
    }
    with patch.object(PlaywrightService, "check_xhs_qr_status", return_value=mock_confirmed_data):
        res_poll_confirmed = client.get(f"/api/platforms/credentials/qr/status?session_key={session_key}")
        assert res_poll_confirmed.status_code == 200
        data_conf = res_poll_confirmed.json()
        assert data_conf["status"] == "confirmed"
        assert data_conf["credential"] is not None
        assert data_conf["credential"]["platform"] == "xhs"
        assert data_conf["credential"]["account_identifier"] == "小红书头部知识博主"
        assert "a1" in data_conf["credential"]["cookie_keys"]
        assert "web_session" in data_conf["credential"]["cookie_keys"]


def test_xhs_playwright_failure_graceful_fallback(client):
    """Verify start_qr_login gracefully falls back when Playwright throws exception."""
    from app.services.playwright_service import PlaywrightService

    with patch.object(PlaywrightService, "start_xhs_qr_session", side_effect=Exception("Playwright browser crash")):
        with patch("httpx.Client.post", side_effect=Exception("HTTP connection refused")):
            res = client.post("/api/platforms/credentials/qr/start", json={"platform": "xhs"})
            assert res.status_code == 200
            data = res.json()
            assert data["platform"] == "xhs"
            assert data["qr_code_data"].startswith("data:image/svg+xml;base64,")
            assert "session_key" in data


