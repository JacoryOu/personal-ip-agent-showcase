# -*- coding: utf-8 -*-
"""Playwright Headless Browser Automation Service for Live QR Login and Session Interception."""

import base64
from datetime import datetime, timedelta, timezone
import logging
import queue
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Check if Playwright is available in python environment
try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None  # type: ignore
    Browser = None  # type: ignore
    BrowserContext = None  # type: ignore
    Page = None  # type: ignore
    Playwright = None  # type: ignore


class PlaywrightWorker(threading.Thread):
    """Dedicated background worker thread for Playwright sync API execution."""

    def __init__(self):
        super().__init__(name="PlaywrightBrowserWorker", daemon=True)
        self.cmd_queue: queue.Queue = queue.Queue()
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self._init_event = threading.Event()
        self._init_error: Optional[Exception] = None

    def run(self):
        if not PLAYWRIGHT_AVAILABLE:
            self._init_error = RuntimeError("Playwright package is not installed.")
            self._init_event.set()
            return

        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            self.running = True
            logger.info("Playwright Chromium browser worker started successfully.")
        except Exception as e:
            logger.warning(f"Failed to initialize Playwright Chromium: {e}")
            self._init_error = e
            self._init_event.set()
            return

        self._init_event.set()

        while self.running:
            try:
                task = self.cmd_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            cmd = task.get("cmd")
            args = task.get("args", {})
            resp_q = task.get("resp_q")

            try:
                if cmd == "start_xhs_qr":
                    res = self._handle_start_xhs_qr(args)
                    if resp_q:
                        resp_q.put({"success": True, "data": res})
                elif cmd == "check_xhs_qr":
                    res = self._handle_check_xhs_qr(args)
                    if resp_q:
                        resp_q.put({"success": True, "data": res})
                elif cmd == "close_session":
                    self._handle_close_session(args)
                    if resp_q:
                        resp_q.put({"success": True})
                elif cmd == "stop":
                    self._handle_stop()
                    if resp_q:
                        resp_q.put({"success": True})
                    break
            except Exception as e:
                logger.error(f"Error executing command '{cmd}' in PlaywrightWorker: {e}", exc_info=True)
                if resp_q:
                    resp_q.put({"success": False, "error": str(e)})

    def _handle_start_xhs_qr(self, args: Dict[str, Any]) -> Dict[str, Any]:
        session_key = args["session_key"]
        timeout_ms = int(args.get("timeout_sec", 15.0) * 1000)

        # Close existing context for this key if any
        if session_key in self.contexts:
            try:
                self.contexts[session_key]["context"].close()
            except Exception:
                pass
            del self.contexts[session_key]

        context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        login_url = args.get("login_url", "https://creator.xiaohongshu.com/login")
        page.goto(login_url, timeout=timeout_ms, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Find QR image element with multiple heuristic strategies
        qr_data_uri = None
        imgs = page.query_selector_all("img")
        for img in imgs:
            src = img.get_attribute("src") or ""
            if "data:image" in src:
                qr_data_uri = src
                break
            if any(term in src.lower() for term in ["qrcode", "qr-code", "login/qr", "barcode"]):
                try:
                    b64 = base64.b64encode(img.screenshot()).decode("utf-8")
                    qr_data_uri = f"data:image/png;base64,{b64}"
                    break
                except Exception:
                    pass

        # Check canvas elements (common modern QR rendering technique)
        if not qr_data_uri:
            canvases = page.query_selector_all("canvas, .qrcode-box canvas, .login-box canvas, [class*='qrcode'] canvas")
            for canvas in canvases:
                try:
                    b64 = base64.b64encode(canvas.screenshot()).decode("utf-8")
                    qr_data_uri = f"data:image/png;base64,{b64}"
                    break
                except Exception:
                    pass

        # Fallback to screenshot of QR code container
        if not qr_data_uri:
            qr_selectors = [
                ".qrcode-img",
                ".qrcode-container",
                ".qrcode-box",
                ".login-box img",
                ".code-box",
                "[class*='qrcode']",
                "[class*='qr-code']",
                ".login-container img",
                ".login-card img",
            ]
            for sel in qr_selectors:
                qr_container = page.query_selector(sel)
                if qr_container:
                    try:
                        screenshot_bytes = qr_container.screenshot()
                        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                        qr_data_uri = f"data:image/png;base64,{b64}"
                        break
                    except Exception:
                        pass

        # Final fallback: screenshot login card container if present
        if not qr_data_uri:
            login_box = page.query_selector(".login-box, .login-container, .login-card, .login-content")
            if login_box:
                try:
                    b64 = base64.b64encode(login_box.screenshot()).decode("utf-8")
                    qr_data_uri = f"data:image/png;base64,{b64}"
                except Exception:
                    pass

        if not qr_data_uri:
            context.close()
            raise RuntimeError("Could not find or extract QR code image from Xiaohongshu login page.")

        now = datetime.now(timezone.utc)
        self.contexts[session_key] = {
            "context": context,
            "page": page,
            "created_at": now,
            "expires_at": now + timedelta(seconds=180),
            "status": "pending_login",
        }

        return {
            "session_key": session_key,
            "qr_code_data": qr_data_uri,
            "expires_in": 180,
            "instructions": "请打开「小红书 App」扫描二维码完成登录授权。网页已启动无头浏览器实时会话拦截。",
        }

    def _handle_check_xhs_qr(self, args: Dict[str, Any]) -> Dict[str, Any]:
        session_key = args["session_key"]
        session_info = self.contexts.get(session_key)
        if not session_info:
            return {"status": "expired", "message": "Playwright 会话不存在或已关闭。"}

        page: Page = session_info["page"]
        context: BrowserContext = session_info["context"]

        # Check expiration
        now = datetime.now(timezone.utc)
        if now > session_info["expires_at"]:
            try:
                context.close()
            except Exception:
                pass
            self.contexts.pop(session_key, None)
            return {"status": "expired", "message": "二维码已过期，请刷新重新获取。"}

        # Read active cookies
        cookies_list = context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies_list}

        # Check if login confirmed
        curr_url = page.url
        is_redirected = ("login" not in curr_url) and ("xiaohongshu.com" in curr_url)
        has_session_cookie = "web_session" in cookie_dict
        has_a1_and_id = "a1" in cookie_dict and ("webId" in cookie_dict or "gid" in cookie_dict or "customer-session-id" in cookie_dict)

        if has_session_cookie or (is_redirected and has_a1_and_id):
            logger.info(f"Playwright detected Xiaohongshu login confirmation! (url={curr_url})")
            # Try to grab nickname
            account_name = "小红书创作者"
            try:
                nick_elem = page.query_selector(".user-name, .name, .avatar-name, .header-user")
                if nick_elem:
                    txt = nick_elem.inner_text().strip()
                    if txt:
                        account_name = txt
            except Exception:
                pass

            # Close context cleanly
            try:
                context.close()
            except Exception:
                pass
            self.contexts.pop(session_key, None)

            return {
                "status": "confirmed",
                "message": "小红书扫码授权成功！已拦截捕获活跃 Session 凭据。",
                "cookies": cookie_dict,
                "account_identifier": account_name,
            }

        # Check scanned state
        try:
            page_text = page.inner_text("body")
            if any(term in page_text for term in ["已扫码", "请在手机端确认", "扫描成功", "请在手机上点击确认"]):
                return {"status": "scanned", "message": "已在手机上扫码，请在手机端点击确认登录"}
            if any(term in page_text for term in ["二维码已失效", "请点击刷新"]):
                try:
                    context.close()
                except Exception:
                    pass
                self.contexts.pop(session_key, None)
                return {"status": "expired", "message": "二维码已在平台端失效，请刷新重新扫描。"}
        except Exception:
            pass

        return {"status": "pending_login", "message": "等待用户手机端扫码..."}

    def _handle_close_session(self, args: Dict[str, Any]):
        session_key = args["session_key"]
        info = self.contexts.pop(session_key, None)
        if info and "context" in info:
            try:
                info["context"].close()
            except Exception:
                pass

    def _handle_stop(self):
        for k, info in list(self.contexts.items()):
            try:
                info["context"].close()
            except Exception:
                pass
        self.contexts.clear()
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
        self.running = False


class PlaywrightService:
    """Singleton service wrapping the background Playwright browser worker."""

    _worker: Optional[PlaywrightWorker] = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def is_available(cls) -> bool:
        """Checks if Playwright is installed and worker can be initialized."""
        if not PLAYWRIGHT_AVAILABLE:
            return False
        worker = cls._get_or_create_worker()
        return worker is not None and worker.running

    @classmethod
    def _get_or_create_worker(cls) -> Optional[PlaywrightWorker]:
        with cls._lock:
            if cls._worker and cls._worker.is_alive() and cls._worker.running:
                return cls._worker

            if not PLAYWRIGHT_AVAILABLE:
                return None

            worker = PlaywrightWorker()
            worker.start()
            worker._init_event.wait(timeout=10.0)

            if worker.running:
                cls._worker = worker
                return worker
            else:
                logger.warning(f"Playwright worker failed to run: {worker._init_error}")
                return None

    @classmethod
    def start_xhs_qr_session(
        cls,
        session_key: str,
        login_url: str = "https://creator.xiaohongshu.com/login",
        timeout_sec: float = 15.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Launches isolated headless browser context, navigates to Xiaohongshu creator login,
        extracts live QR code image as Base64 data URI, and returns session payload.
        Returns None if Playwright is not available or encounters error (graceful fallback).
        """
        worker = cls._get_or_create_worker()
        if not worker or not worker.running:
            logger.info("Playwright worker not available, falling back to standard QR code generation.")
            return None

        resp_q: queue.Queue = queue.Queue()
        worker.cmd_queue.put({
            "cmd": "start_xhs_qr",
            "args": {
                "session_key": session_key,
                "login_url": login_url,
                "timeout_sec": timeout_sec,
            },
            "resp_q": resp_q,
        })

        try:
            res = resp_q.get(timeout=timeout_sec + 5.0)
            if res.get("success"):
                return res["data"]
            else:
                logger.warning(f"Playwright start_xhs_qr returned error: {res.get('error')}")
                return None
        except Exception as e:
            logger.warning(f"Playwright start_xhs_qr timed out or failed: {e}")
            return None

    @classmethod
    def check_xhs_qr_status(cls, session_key: str) -> Optional[Dict[str, Any]]:
        """
        Polls active Playwright browser session for cookie changes or navigation.
        Returns None if session is not managed by Playwright.
        """
        worker = cls._get_or_create_worker()
        if not worker or not worker.running:
            return None

        resp_q: queue.Queue = queue.Queue()
        worker.cmd_queue.put({
            "cmd": "check_xhs_qr",
            "args": {"session_key": session_key},
            "resp_q": resp_q,
        })

        try:
            res = resp_q.get(timeout=5.0)
            if res.get("success"):
                return res["data"]
            return None
        except Exception as e:
            logger.warning(f"Playwright check_xhs_qr timed out or failed: {e}")
            return None

    @classmethod
    def close_session(cls, session_key: str) -> None:
        """Cleanly closes isolated browser context and page for session_key."""
        worker = cls._worker
        if not worker or not worker.running:
            return
        worker.cmd_queue.put({
            "cmd": "close_session",
            "args": {"session_key": session_key},
            "resp_q": None,
        })

    @classmethod
    def shutdown(cls) -> None:
        """Shuts down all browser instances and background worker."""
        with cls._lock:
            worker = cls._worker
            if worker:
                resp_q: queue.Queue = queue.Queue()
                worker.cmd_queue.put({"cmd": "stop", "args": {}, "resp_q": resp_q})
                try:
                    resp_q.get(timeout=5.0)
                except Exception:
                    pass
                cls._worker = None


__all__ = ["PlaywrightService", "PLAYWRIGHT_AVAILABLE"]
