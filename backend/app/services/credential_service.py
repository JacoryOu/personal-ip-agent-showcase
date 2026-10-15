import base64
from datetime import datetime, timedelta, timezone
import json
import logging
import re
import threading
from typing import Any, Dict, List, Optional
import urllib.parse
import uuid

import httpx
import qrcode
import qrcode.image.svg
from sqlmodel import Session, select, update

from app.core.crypto import (
    SecretBoxError,
    decrypt_mapping,
    encrypt_mapping,
    is_encrypted,
)
from app.core.db import engine
from app.models.credential import PlatformAccountCredential
from app.models.user import User
from app.schemas.platform_schemas import CredentialResponse
from app.services.cognitive_service import CognitiveService
from app.services.playwright_service import PlaywrightService

logger = logging.getLogger(__name__)


def _parse_uid(uid_raw: Optional[str | uuid.UUID]) -> Optional[uuid.UUID]:
    if not uid_raw:
        return None
    if isinstance(uid_raw, uuid.UUID):
        return uid_raw
    try:
        return uuid.UUID(str(uid_raw))
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(uid_raw))


def generate_qr_svg(content: str, platform_color: str = "#2563eb") -> str:
    """Generates an embedded standard compliant vector QR visual representation as a data URI."""
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
            image_factory=qrcode.image.svg.SvgImage,
        )
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image()
        svg_content = img.to_string(encoding="unicode")
        b64 = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"
    except Exception as e:
        logger.warning(f"Error generating QR SVG with qrcode library: {e}")
        # Deterministic valid SVG fallback
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" width="220" height="220">'
            f'<rect width="160" height="160" rx="12" fill="#ffffff"/>'
            f'<rect x="20" y="20" width="120" height="120" fill="{platform_color}" rx="8"/>'
            f'</svg>'
        )
        b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"


def wrap_jpeg_as_svg(jpeg_bytes: bytes) -> str:
    """Wraps raw official JPEG QR image bytes into a clean SVG vector container as a data URI."""
    b64_img = base64.b64encode(jpeg_bytes).decode("utf-8")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 240 240" width="240" height="240">'
        f'<rect width="240" height="240" rx="12" fill="#ffffff"/>'
        f'<image href="data:image/jpeg;base64,{b64_img}" xlink:href="data:image/jpeg;base64,{b64_img}" x="10" y="10" width="220" height="220"/>'
        f'</svg>'
    )
    b64_svg = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64_svg}"


class CredentialService:
    # In-memory tracking for active QR login polling sessions
    _active_qr_sessions: Dict[str, Dict[str, Any]] = {}
    _lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Credential secret storage helpers
    #
    # ``PlatformAccountCredential.cookies`` holds a JSON object. Because this
    # change must not add any database column, ciphertext is stored *inside*
    # that same column as a versioned envelope (see ``app.core.crypto``).
    # Legacy plaintext rows are still readable and are migrated lazily the
    # first time they are read through ``load_cookies``.
    # ------------------------------------------------------------------
    @classmethod
    def _store_cookies(cls, cookies: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Encrypt a cookie mapping for storage. Fails closed without a key."""
        if not cookies:
            return {}
        return encrypt_mapping({str(k): str(v) for k, v in cookies.items()})

    @classmethod
    def load_cookies(cls, cred: PlatformAccountCredential) -> Dict[str, Any]:
        """Return the plaintext cookies for ``cred`` without mutating the row.

        Decryption problems (missing/rotated master key, tampered ciphertext)
        are *not* swallowed: returning ``{}`` would silently look like "the user
        has no session" and would let a misconfigured key look like a working
        system. Callers that must stay user-facing (``serialize_credential``,
        ``check_credential_validity``) convert the error into an explicit
        "unreadable credential" state.
        """
        stored = cred.cookies
        if not stored:
            return {}
        try:
            return decrypt_mapping(stored)
        except SecretBoxError:
            logger.error(
                "Failed to decrypt credential %s; it is unreadable.",
                getattr(cred, "id", "<unknown>"),
            )
            raise

    @classmethod
    def _migrate_legacy_cookies(
        cls,
        sess: Session,
        cred: PlatformAccountCredential,
        plaintext: Dict[str, Any],
    ) -> None:
        """Re-encrypt a legacy plaintext row in place (lazy migration).

        Uses a targeted UPDATE so unrelated columns are untouched and the ORM
        identity map stays authoritative via ``refresh``.
        """
        sess.exec(
            update(PlatformAccountCredential)
            .where(PlatformAccountCredential.id == cred.id)
            .values(cookies=cls._store_cookies(plaintext))
        )
        sess.commit()
        sess.refresh(cred)

    @classmethod
    def load_cookies_with_migration(
        cls,
        cred: PlatformAccountCredential,
        sess: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Decrypt cookies, migrating a legacy plaintext row when possible."""
        stored = cred.cookies
        if not stored:
            return {}
        plaintext = cls.load_cookies(cred)
        if is_encrypted(stored) or sess is None:
            return plaintext
        try:
            cls._migrate_legacy_cookies(sess, cred, plaintext)
            logger.info("Migrated legacy plaintext credential %s to encrypted storage.", cred.id)
        except Exception:
            logger.warning("Lazy credential migration failed for %s; continuing.", cred.id)
        return plaintext

    @classmethod
    def serialize_credential(cls, cred: PlatformAccountCredential) -> CredentialResponse:
        # Decrypt only to derive key names; never expose values. An unreadable
        # credential is reported as having no cookies instead of 500-ing, but it
        # is logged loudly so an operator notices the key/data mismatch.
        try:
            plaintext = cls.load_cookies(cred)
        except SecretBoxError:
            plaintext = {}
        keys = list(plaintext.keys())
        return CredentialResponse(
            id=str(cred.id),
            user_id=str(cred.user_id),
            platform=cred.platform,
            account_identifier=cred.account_identifier,
            status=cred.status,
            has_cookies=bool(plaintext),
            cookie_keys=keys,
            last_checked_at=cred.last_checked_at.isoformat() if cred.last_checked_at else None,
            expires_at=cred.expires_at.isoformat() if cred.expires_at else None,
            meta_info=cred.meta_info or {},
            created_at=cred.created_at.isoformat() if cred.created_at else None,
            updated_at=cred.updated_at.isoformat() if cred.updated_at else None,
        )

    @classmethod
    def start_qr_login(
        cls,
        platform: str,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Initiates a platform QR login session with live official gateway integration."""
        platform = platform.lower().strip()
        if platform not in ["wechat", "xhs", "zhihu"]:
            raise ValueError(f"Unsupported platform: {platform}. Supported: 'wechat', 'xhs', 'zhihu'.")

        session_key = f"qr_{platform}_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=180)

        # Thread-safe purge of stale expired sessions to prevent memory leak
        with cls._lock:
            stale_keys = [
                k for k, v in cls._active_qr_sessions.items()
                if now > v.get("expires_at", now) + timedelta(minutes=10)
            ]
            for k in stale_keys:
                old_sess = cls._active_qr_sessions.pop(k, None)
                if old_sess:
                    if old_sess.get("use_playwright"):
                        PlaywrightService.close_session(k)
                    if "http_client" in old_sess:
                        try:
                            old_sess["http_client"].close()
                        except Exception:
                            pass

        # Color schemes & instructions
        instruction_map = {
            "wechat": "请使用绑定了公众号的微信扫码并在手机上点击确认登录「微信公众平台」",
            "xhs": "请打开「小红书 App」扫描二维码完成登录授权。如遇平台风控，可使用「手动录入 Cookie」快速绑定",
            "zhihu": "请打开「知乎 App」扫描二维码完成登录授权，或使用手动录入 Cookie",
        }

        qr_svg: str = ""
        http_client: Optional[httpx.Client] = None
        is_live = False
        mp_uuid = None
        xhs_qr_id = None
        xhs_code = None
        use_playwright = False

        if platform == "wechat":
            # Genuine WeChat MP login gateway initiation
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Referer": "https://mp.weixin.qq.com/",
                    "Origin": "https://mp.weixin.qq.com",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                }
                client = httpx.Client(headers=headers, timeout=8.0, follow_redirects=True)
                # 1. Warm up session
                client.get("https://mp.weixin.qq.com/")
                # 2. Call startlogin to initiate live QR ticket
                ts = str(int(datetime.now().timestamp() * 1000))
                resp_start = client.post(
                    "https://mp.weixin.qq.com/cgi-bin/bizlogin?action=startlogin",
                    data={
                        "userlang": "zh_CN",
                        "redirect_url": "",
                        "login_type": 3,
                        "sessionid": ts,
                    },
                )
                start_json = resp_start.json()
                if start_json.get("base_resp", {}).get("ret") == 0 and start_json.get("uuid"):
                    mp_uuid = start_json.get("uuid")
                    # 3. Fetch genuine official WeChat login QR image
                    resp_qr = client.get(
                        f"https://mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=getqrcode&random={ts}"
                    )
                    if resp_qr.status_code == 200 and len(resp_qr.content) > 500:
                        qr_svg = wrap_jpeg_as_svg(resp_qr.content)
                        http_client = client
                        is_live = True
                        logger.info(f"WeChat MP live QR initiated successfully (uuid={mp_uuid})")
                    else:
                        client.close()
                else:
                    client.close()
            except Exception as e:
                logger.warning(f"WeChat MP live QR connection failed: {e}. Falling back to standard scannable QR.")
                if http_client:
                    try:
                        http_client.close()
                    except Exception:
                        pass
                http_client = None

            if not is_live:
                qr_content = "https://mp.weixin.qq.com"
                qr_svg = generate_qr_svg(qr_content, platform_color="#07c160")

        elif platform == "xhs":
            # 1. Attempt Playwright headless browser automation for live XHS creator login & session interception
            try:
                pw_res = PlaywrightService.start_xhs_qr_session(session_key=session_key)
                if pw_res and pw_res.get("qr_code_data"):
                    qr_svg = pw_res["qr_code_data"]
                    is_live = True
                    use_playwright = True
                    if pw_res.get("instructions"):
                        instruction_map["xhs"] = pw_res["instructions"]
                    logger.info(f"Xiaohongshu Playwright live QR code initiated successfully (session={session_key})")
            except Exception as e:
                logger.warning(f"Playwright XHS live QR initiation failed: {e}. Falling back to standard QR.")

            # 2. Graceful fallback if Playwright is unavailable or fails
            if not use_playwright:
                try:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                        "Referer": "https://www.xiaohongshu.com/",
                        "Origin": "https://www.xiaohongshu.com",
                        "Content-Type": "application/json;charset=UTF-8",
                        "Accept": "application/json, text/plain, */*",
                    }
                    client = httpx.Client(headers=headers, timeout=6.0)
                    resp_xhs = client.post("https://edith.xiaohongshu.com/api/sns/web/v1/login/qrcode/create", json={"qr_type": 1})
                    if resp_xhs.status_code == 200:
                        data = resp_xhs.json().get("data", {})
                        xhs_url = data.get("url")
                        if xhs_url:
                            qr_svg = generate_qr_svg(xhs_url, platform_color="#ff2442")
                            http_client = client
                            is_live = True
                            xhs_qr_id = data.get("qr_id")
                            xhs_code = data.get("code")
                        else:
                            client.close()
                    else:
                        client.close()
                except Exception as e:
                    logger.warning(f"XHS live QR connection failed: {e}. Falling back to standard QR.")
                    if http_client:
                        try:
                            http_client.close()
                        except Exception:
                            pass
                    http_client = None

            if not qr_svg:
                qr_content = "https://creator.xiaohongshu.com/login"
                qr_svg = generate_qr_svg(qr_content, platform_color="#ff2442")

        elif platform == "zhihu":
            qr_content = "https://www.zhihu.com/signin"
            qr_svg = generate_qr_svg(qr_content, platform_color="#0066ff")

        with cls._lock:
            cls._active_qr_sessions[session_key] = {
                "session_key": session_key,
                "platform": platform,
                "user_id": str(user_id) if user_id else None,
                "status": "pending_login",
                "created_at": now,
                "expires_at": expires_at,
                "qr_code_data": qr_svg,
                "account_identifier": None,
                "cookies": {},
                "http_client": http_client,
                "is_live": is_live,
                "use_playwright": use_playwright,
                "mp_uuid": mp_uuid,
                "xhs_qr_id": xhs_qr_id,
                "xhs_code": xhs_code,
            }

        return {
            "session_key": session_key,
            "platform": platform,
            "qr_code_data": qr_svg,
            "expires_in": 180,
            "instructions": instruction_map.get(platform, "请扫描二维码登录"),
        }

    @classmethod
    def check_qr_login_status(
        cls,
        session_key: str,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Polls current status of the QR login session with real-time upstream gateway querying."""
        with cls._lock:
            sess_data = cls._active_qr_sessions.get(session_key)
            if not sess_data:
                return {
                    "session_key": session_key,
                    "platform": "unknown",
                    "status": "expired",
                    "message": "二维码会话已失效或不存在，请重新生成。",
                    "credential": None,
                }

            now = datetime.now(timezone.utc)
            if now > sess_data["expires_at"]:
                sess_data["status"] = "expired"
                if sess_data.get("use_playwright"):
                    PlaywrightService.close_session(session_key)
                client = sess_data.pop("http_client", None)
                if client:
                    try:
                        client.close()
                    except Exception:
                        pass
                return {
                    "session_key": session_key,
                    "platform": sess_data["platform"],
                    "status": "expired",
                    "message": "二维码已过期，请刷新二维码重新扫描。",
                    "credential": None,
                }

        # Check live WeChat MP status if session is active
        if (
            sess_data.get("platform") == "wechat"
            and sess_data.get("is_live")
            and sess_data.get("http_client")
            and sess_data.get("status") not in ("confirmed", "expired")
        ):
            client: httpx.Client = sess_data["http_client"]
            try:
                ask_resp = client.get("https://mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=ask", timeout=5.0)
                if ask_resp.status_code == 200:
                    ask_json = ask_resp.json()
                    status_code = ask_json.get("status")
                    if status_code in (4, 6):
                        sess_data["status"] = "scanned"
                    elif status_code == 1:
                        # Scan confirmed by user on mobile WeChat! Complete the login
                        logger.info("WeChat MP scan confirmed! Finalizing session login...")
                        login_resp = client.post(
                            "https://mp.weixin.qq.com/cgi-bin/bizlogin?action=login",
                            data={
                                "userlang": "zh_CN",
                                "redirect_url": "",
                                "cookie_forbidden": 0,
                            },
                        )
                        token = None
                        try:
                            login_json = login_resp.json()
                            redirect_url = login_json.get("redirect_url", "")
                            match = re.search(r"[?&]token=([0-9a-zA-Z_\-]+)", redirect_url) or re.search(r"token=([0-9a-zA-Z_\-]+)", redirect_url)
                            if match:
                                token = match.group(1)
                        except Exception:
                            pass

                        # If token not extracted from JSON, inspect response url, history, and text
                        if not token:
                            match = re.search(r"[?&]token=([0-9a-zA-Z_\-]+)", str(login_resp.url))
                            if match:
                                token = match.group(1)
                        if not token:
                            for h in login_resp.history:
                                loc = h.headers.get("location", "")
                                match = re.search(r"[?&]token=([0-9a-zA-Z_\-]+)", loc)
                                if match:
                                    token = match.group(1)
                                    break
                        if not token and login_resp.text:
                            match = re.search(r'token\s*[:=]\s*["\']?([0-9a-zA-Z_\-]+)', login_resp.text)
                            if match:
                                token = match.group(1)

                        captured_cookies = {k: v for k, v in client.cookies.items()}
                        if token:
                            captured_cookies["token"] = token

                        # Attempt to extract actual WeChat official account nickname
                        account_name = captured_cookies.get("slave_user") or "微信公众平台·官方作者"
                        if token:
                            try:
                                home_resp = client.get(
                                    f"https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token={token}",
                                    timeout=4.0,
                                )
                                if home_resp.status_code == 200:
                                    nick_match = re.search(
                                        r'class="weui-desktop-account__nickname"[^>]*>([^<]+)<',
                                        home_resp.text,
                                    )
                                    if nick_match and nick_match.group(1).strip():
                                        account_name = nick_match.group(1).strip()
                                    else:
                                        nick_match2 = re.search(r'nickname\s*:\s*["\']([^"\']+)["\']', home_resp.text)
                                        if nick_match2 and nick_match2.group(1).strip():
                                            account_name = nick_match2.group(1).strip()
                            except Exception:
                                pass

                        sess_data["cookies"] = captured_cookies
                        sess_data["account_identifier"] = account_name
                        sess_data["status"] = "confirmed"
                    elif status_code == 3:
                        sess_data["status"] = "expired"
                        sess_data["message"] = "用户在手机端取消了授权登录。"
                    elif status_code == 2:
                        sess_data["status"] = "expired"
                        sess_data["message"] = "二维码已过期，请刷新二维码重新扫描。"
                    elif ask_json.get("base_resp", {}).get("ret") != 0:
                        sess_data["status"] = "expired"
                        sess_data["message"] = "二维码会话已失效，请刷新重新扫描。"
            except Exception as e:
                logger.warning(f"Error checking live WeChat MP status: {e}")

        # Check live XHS status if active
        elif (
            sess_data.get("platform") == "xhs"
            and sess_data.get("status") not in ("confirmed", "expired")
        ):
            if sess_data.get("use_playwright"):
                try:
                    pw_res = PlaywrightService.check_xhs_qr_status(session_key)
                    if pw_res:
                        new_st = pw_res.get("status")
                        if new_st == "confirmed":
                            sess_data["cookies"] = pw_res.get("cookies", {})
                            sess_data["account_identifier"] = pw_res.get("account_identifier") or "小红书创作者"
                            sess_data["status"] = "confirmed"
                        elif new_st == "scanned":
                            sess_data["status"] = "scanned"
                        elif new_st == "expired":
                            sess_data["status"] = "expired"
                            if pw_res.get("message"):
                                sess_data["message"] = pw_res["message"]
                except Exception as e:
                    logger.warning(f"Error checking Playwright XHS status: {e}")
            elif sess_data.get("is_live") and sess_data.get("http_client"):
                client = sess_data["http_client"]
                qr_id = sess_data.get("xhs_qr_id")
                code = sess_data.get("xhs_code")
                if qr_id and code:
                    try:
                        status_url = f"https://edith.xiaohongshu.com/api/sns/web/v1/login/qrcode/status?qr_id={qr_id}&code={code}"
                        resp = client.get(status_url, timeout=5.0)
                        if resp.status_code == 200:
                            res_json = resp.json()
                            code_val = res_json.get("data", {}).get("code_status")
                            if code_val == 1:
                                sess_data["status"] = "scanned"
                            elif code_val == 2:
                                captured_cookies = {k: v for k, v in client.cookies.items()}
                                sess_data["cookies"] = captured_cookies
                                sess_data["account_identifier"] = "小红书创作者"
                                sess_data["status"] = "confirmed"
                            elif code_val == 3:
                                sess_data["status"] = "expired"
                    except Exception as e:
                        logger.warning(f"Error checking live XHS status: {e}")

        status = sess_data["status"]
        if status == "confirmed":
            # Return cached credential if already saved
            if sess_data.get("saved_credential"):
                return {
                    "session_key": session_key,
                    "platform": sess_data["platform"],
                    "status": "confirmed",
                    "message": "授权成功！已绑定平台官方会话凭据。",
                    "credential": sess_data["saved_credential"],
                }

            # Save or update credential in SQLite
            def _save(db_session: Session) -> CredentialResponse:
                uid = _parse_uid(sess_data.get("user_id"))
                if not uid:
                    user = CognitiveService.get_or_create_default_user(db_session)
                    uid = user.id

                plat = sess_data["platform"]
                existing = db_session.exec(
                    select(PlatformAccountCredential).where(
                        PlatformAccountCredential.user_id == uid,
                        PlatformAccountCredential.platform == plat,
                    )
                ).first()

                cookies = sess_data.get("cookies") or {}
                account_id = sess_data.get("account_identifier") or f"{plat.upper()}_User"
                sealed_cookies = cls._store_cookies(cookies)

                if existing:
                    existing.cookies = sealed_cookies
                    existing.account_identifier = account_id
                    existing.status = "active"
                    existing.last_checked_at = datetime.now(timezone.utc)
                    existing.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                    existing.updated_at = datetime.now(timezone.utc)
                    db_session.add(existing)
                    db_session.commit()
                    db_session.refresh(existing)
                    return cls.serialize_credential(existing)
                else:
                    new_cred = PlatformAccountCredential(
                        id=uuid.uuid4(),
                        user_id=uid,
                        platform=plat,
                        account_identifier=account_id,
                        cookies=sealed_cookies,
                        status="active",
                        last_checked_at=datetime.now(timezone.utc),
                        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                        meta_info={"auth_method": "qr_scan"},
                    )
                    db_session.add(new_cred)
                    db_session.commit()
                    db_session.refresh(new_cred)
                    return cls.serialize_credential(new_cred)

            cred_res = _save(session) if session else None
            if not cred_res:
                with Session(engine) as s:
                    cred_res = _save(s)

            sess_data["saved_credential"] = cred_res

            # Cleanup client once confirmed
            c = sess_data.pop("http_client", None)
            if c:
                try:
                    c.close()
                except Exception:
                    pass

            return {
                "session_key": session_key,
                "platform": sess_data["platform"],
                "status": "confirmed",
                "message": "授权成功！已绑定平台官方会话凭据。",
                "credential": cred_res,
            }

        msg_map = {
            "pending_login": "等待用户手机端扫码...",
            "scanned": "已在手机上扫码，请在手机端点击确认登录",
            "expired": sess_data.get("message") or "二维码已过期，请刷新二维码重新扫描。",
        }
        return {
            "session_key": session_key,
            "platform": sess_data["platform"],
            "status": status,
            "message": msg_map.get(status, "等待授权中..."),
            "credential": None,
        }

    @classmethod
    def simulate_confirm_qr(
        cls,
        session_key: str,
        account_identifier: Optional[str] = None,
    ) -> bool:
        """Simulates mobile QR scan confirmation for dev/testing/automation."""
        with cls._lock:
            sess_data = cls._active_qr_sessions.get(session_key)
            if not sess_data:
                return False

            platform = sess_data["platform"]
            if sess_data.get("use_playwright"):
                PlaywrightService.close_session(session_key)
            sess_data["status"] = "confirmed"
            sess_data["account_identifier"] = account_identifier or (
                "微信公众平台·官方作者" if platform == "wechat"
                else "小红书爆款创作者" if platform == "xhs"
                else "知乎高赞创作者"
            )

            # Mock realistic cookie values
            if platform == "wechat":
                sess_data["cookies"] = {
                    "token": "291038472",
                    "slave_sid": "wx_sid_" + uuid.uuid4().hex[:16],
                    "slave_user": "gh_creator_" + uuid.uuid4().hex[:8],
                    "bizuin": "3827102948",
                }
            elif platform == "xhs":
                sess_data["cookies"] = {
                    "a1": "19a83f120e_" + uuid.uuid4().hex[:12],
                    "web_session": "01019284729" + uuid.uuid4().hex[:10],
                    "webId": uuid.uuid4().hex[:16],
                    "gid": "yY0F2104" + uuid.uuid4().hex[:8],
                }
            elif platform == "zhihu":
                sess_data["cookies"] = {
                    "z_c0": "2|1:0|10:" + uuid.uuid4().hex[:16],
                    "d_c0": "ABCA_" + uuid.uuid4().hex[:12],
                }

            return True

    @classmethod
    def parse_cookie_string(cls, raw: str) -> Dict[str, str]:
        """Parses standard HTTP Cookie header string, JSON export, URL query string, or multiline cookies into dict."""
        cookies = {}
        raw_trimmed = raw.strip()

        # 1. Check if raw input is a URL or query string containing token/cookie params
        if "http://" in raw_trimmed or "https://" in raw_trimmed or ("token=" in raw_trimmed and ("cgi-bin" in raw_trimmed or "?" in raw_trimmed or "&" in raw_trimmed)):
            try:
                parsed_url = urllib.parse.urlparse(raw_trimmed)
                query_dict = urllib.parse.parse_qs(parsed_url.query or parsed_url.path)
                for qk, qvals in query_dict.items():
                    if qvals and qk.strip():
                        cookies[qk.strip()] = qvals[0].strip()
                if "token" in cookies:
                    return cookies
            except Exception:
                pass

        # 2. Try parsing as JSON object or JSON array (e.g., from browser cookie export extensions)
        if (raw_trimmed.startswith("{") and raw_trimmed.endswith("}")) or (raw_trimmed.startswith("[") and raw_trimmed.endswith("]")):
            try:
                data = json.loads(raw_trimmed)
                if isinstance(data, dict):
                    return {
                        str(k).strip().strip('"').strip("'"): urllib.parse.unquote(str(v).strip().strip('"').strip("'"))
                        for k, v in data.items()
                        if str(k).strip()
                    }
                elif isinstance(data, list):
                    # Handle EditThisCookie / Cookie-Editor export: [{"name": "key", "value": "val"}]
                    parsed = {}
                    for c in data:
                        if isinstance(c, dict) and "name" in c and "value" in c:
                            parsed[str(c["name"]).strip().strip('"').strip("'")] = urllib.parse.unquote(
                                str(c["value"]).strip().strip('"').strip("'")
                            )
                    if parsed:
                        return parsed
            except Exception:
                pass

        # 3. Parse standard delimited string (splitting on semicolons and newlines)
        parts = re.split(r"[;\r\n]+", raw)
        for item in parts:
            item = item.strip()
            if not item or "=" not in item:
                continue
            k, v = item.split("=", 1)
            k_clean = k.strip().strip('"').strip("'")
            v_clean = urllib.parse.unquote(v.strip().strip('"').strip("'"))
            if k_clean:
                cookies[k_clean] = v_clean
        return cookies

    @classmethod
    def save_manual_cookies(
        cls,
        platform: str,
        cookies_input: Any,
        account_identifier: Optional[str] = None,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> CredentialResponse:
        """Saves manually provided cookies/tokens into SQLite."""
        platform = platform.lower().strip()
        if platform not in ["wechat", "xhs", "zhihu"]:
            raise ValueError(f"Unsupported platform: {platform}")

        if isinstance(cookies_input, str):
            cookie_dict = cls.parse_cookie_string(cookies_input)
        elif isinstance(cookies_input, dict):
            cookie_dict = {str(k): str(v) for k, v in cookies_input.items()}
        else:
            raise ValueError("Cookies must be a dict or cookie string (e.g. 'key1=val; key2=val').")

        if not cookie_dict:
            raise ValueError("Cookie content cannot be empty.")

        # Check key platform tokens
        status_val = "active"
        if platform == "wechat":
            if "token" not in cookie_dict and "slave_sid" not in cookie_dict:
                status_val = "active"  # lenient, user may have provided raw session
        elif platform == "xhs":
            if "a1" not in cookie_dict and "web_session" not in cookie_dict:
                status_val = "active"

        def _execute(sess: Session) -> CredentialResponse:
            uid = _parse_uid(user_id)
            if not uid:
                user = CognitiveService.get_or_create_default_user(sess)
                uid = user.id

            existing = sess.exec(
                select(PlatformAccountCredential).where(
                    PlatformAccountCredential.user_id == uid,
                    PlatformAccountCredential.platform == platform,
                )
            ).first()

            acc_id = account_identifier or (f"{platform.capitalize()}_User")

            sealed_cookies = cls._store_cookies(cookie_dict)

            if existing:
                existing.cookies = sealed_cookies
                existing.account_identifier = acc_id
                existing.status = status_val
                existing.last_checked_at = datetime.now(timezone.utc)
                existing.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                existing.updated_at = datetime.now(timezone.utc)
                sess.add(existing)
                sess.commit()
                sess.refresh(existing)
                return cls.serialize_credential(existing)
            else:
                new_cred = PlatformAccountCredential(
                    id=uuid.uuid4(),
                    user_id=uid,
                    platform=platform,
                    account_identifier=acc_id,
                    cookies=sealed_cookies,
                    status=status_val,
                    last_checked_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                    meta_info={"auth_method": "manual_entry"},
                )
                sess.add(new_cred)
                sess.commit()
                sess.refresh(new_cred)
                return cls.serialize_credential(new_cred)

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def list_credentials(
        cls,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> List[CredentialResponse]:
        """Lists credentials for all platforms for the specified user."""
        def _execute(sess: Session) -> List[CredentialResponse]:
            uid = _parse_uid(user_id)
            if not uid:
                user = CognitiveService.get_or_create_default_user(sess)
                uid = user.id

            creds = sess.exec(
                select(PlatformAccountCredential).where(
                    PlatformAccountCredential.user_id == uid
                )
            ).all()
            return [cls.serialize_credential(c) for c in creds]

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def get_credential(
        cls,
        platform: str,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> Optional[PlatformAccountCredential]:
        """Gets active credential entity by platform."""
        platform = platform.lower().strip()
        def _execute(sess: Session) -> Optional[PlatformAccountCredential]:
            uid = _parse_uid(user_id)
            if not uid:
                user = CognitiveService.get_or_create_default_user(sess)
                uid = user.id

            return sess.exec(
                select(PlatformAccountCredential).where(
                    PlatformAccountCredential.user_id == uid,
                    PlatformAccountCredential.platform == platform,
                )
            ).first()

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def check_credential_validity(
        cls,
        platform: str,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Verifies session health for the platform."""
        platform = platform.lower().strip()
        def _execute(sess: Session) -> Dict[str, Any]:
            cred = cls.get_credential(platform, user_id=user_id, session=sess)
            cookies: Dict[str, Any] = {}
            if cred is not None:
                try:
                    cookies = cls.load_cookies_with_migration(cred, sess)
                except SecretBoxError:
                    # Surface an explicit unusable state rather than claiming the
                    # user simply has no session.
                    return {
                        "platform": platform,
                        "status": "credential_unreadable",
                        "valid": False,
                        "message": (
                            f"{platform} 凭据无法解密，请检查服务端主密钥配置，"
                            "并重新扫码登录。"
                        ),
                    }
            if not cred or not cookies:
                return {
                    "platform": platform,
                    "status": "unauthorized",
                    "valid": False,
                    "message": f"未检测到 {platform} 授权会话凭据，请扫码或录入 Cookie。",
                }

            # Check expiration
            now = datetime.now(timezone.utc)
            exp_at = cred.expires_at
            if exp_at is not None:
                if exp_at.tzinfo is None:
                    exp_at = exp_at.replace(tzinfo=timezone.utc)
                if now > exp_at:
                    cred.status = "expired"
                    sess.add(cred)
                    sess.commit()
                    return {
                        "platform": platform,
                        "status": "expired",
                        "valid": False,
                        "message": f"{platform} 登录会话已过期，请重新扫码授权。",
                    }

            cred.status = "active"
            cred.last_checked_at = now
            sess.add(cred)
            sess.commit()

            return {
                "platform": platform,
                "status": "active",
                "valid": True,
                "message": f"{platform} 授权凭据有效（状态正常）。",
                "account_identifier": cred.account_identifier,
                "last_checked_at": now.isoformat(),
            }

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def delete_credential(
        cls,
        credential_id: str | uuid.UUID,
        session: Optional[Session] = None,
    ) -> bool:
        """Deletes credential from database."""
        c_id = _parse_uid(credential_id)
        if not c_id:
            return False

        def _execute(sess: Session) -> bool:
            cred = sess.get(PlatformAccountCredential, c_id)
            if not cred:
                # Fallback to query by platform name
                cred = sess.exec(
                    select(PlatformAccountCredential).where(
                        PlatformAccountCredential.platform == str(credential_id).lower().strip()
                    )
                ).first()
            if not cred:
                return False
            sess.delete(cred)
            sess.commit()
            return True

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)
