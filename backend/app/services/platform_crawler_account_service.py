"""Benchmark account parsing and CRUD.

Split out of ``platform_crawler_service``; behaviour is unchanged and the
original module re-exposes these methods through the ``PlatformCrawlerService``
facade.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from app.core.db import engine
from app.models.benchmark_account import BenchmarkAccount
from app.schemas.platform_schemas import BenchmarkAccountResponse
from app.services.cognitive_service import CognitiveService
from app.services.platform_crawler_support_service import _parse_uid



class PlatformCrawlerAccountMixin:

    @classmethod
    def serialize_account(cls, acc: BenchmarkAccount) -> BenchmarkAccountResponse:
        return BenchmarkAccountResponse(
            id=str(acc.id),
            user_id=str(acc.user_id),
            platform=acc.platform,
            account_name=acc.account_name,
            account_id=acc.account_id,
            home_url=acc.home_url,
            avatar_url=acc.avatar_url,
            bio=acc.bio,
            follower_count=acc.follower_count or 0,
            notes_count=acc.notes_count or 0,
            last_synced_at=acc.last_synced_at.isoformat() if acc.last_synced_at else None,
            status=acc.status,
            meta_info=acc.meta_info or {},
            created_at=acc.created_at.isoformat() if acc.created_at else None,
            updated_at=acc.updated_at.isoformat() if acc.updated_at else None,
        )

    @classmethod
    def parse_account_input(
        cls,
        platform: str,
        account_name: str,
        account_id: Optional[str] = None,
        home_url: Optional[str] = None,
    ) -> Dict[str, str]:
        """Normalizes account identifier and home_url based on platform conventions."""
        platform = platform.lower().strip()
        parsed_id = (account_id or "").strip()
        url = (home_url or "").strip()

        if url:
            unquoted_url = urllib.parse.unquote(url)
            if platform == "xhs":
                # Matches /user/profile/(id)
                m = re.search(r"user/profile/([a-zA-Z0-9_-]+)", url)
                if m:
                    parsed_id = m.group(1)
            elif platform == "zhihu":
                # Matches /people/(token) or /column/(token)
                m = re.search(r"(?:people|column|org)/([a-zA-Z0-9_-]+)", url)
                if m:
                    parsed_id = m.group(1)
            elif platform == "wechat":
                # If mp article or gh link with __biz
                m = re.search(r"__biz=([a-zA-Z0-9=_-]+)", unquoted_url)
                if m:
                    parsed_id = m.group(1)

        if not parsed_id:
            parsed_id = f"{platform}_{uuid.uuid5(uuid.NAMESPACE_DNS, account_name).hex[:10]}"

        if not url:
            if platform == "xhs":
                url = f"https://www.xiaohongshu.com/user/profile/{parsed_id}"
            elif platform == "zhihu":
                url = f"https://www.zhihu.com/people/{parsed_id}"
            elif platform == "wechat":
                url = f"https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz={parsed_id}"

        return {
            "account_id": parsed_id,
            "home_url": url,
        }

    @classmethod
    def create_benchmark_account(
        cls,
        platform: str,
        account_name: str,
        account_id: Optional[str] = None,
        home_url: Optional[str] = None,
        avatar_url: Optional[str] = None,
        bio: Optional[str] = None,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> BenchmarkAccountResponse:
        """Adds or updates a monitored benchmark account."""
        parsed_info = cls.parse_account_input(platform, account_name, account_id, home_url)
        final_acc_id = parsed_info["account_id"]
        final_url = parsed_info["home_url"]

        def _execute(sess: Session) -> BenchmarkAccountResponse:
            uid = _parse_uid(user_id)
            if not uid:
                user = CognitiveService.get_or_create_default_user(sess)
                uid = user.id

            existing = sess.exec(
                select(BenchmarkAccount).where(
                    BenchmarkAccount.user_id == uid,
                    BenchmarkAccount.platform == platform,
                    BenchmarkAccount.account_name == account_name.strip(),
                )
            ).first()

            avatar = avatar_url or (
                f"https://api.dicebear.com/7.x/identicon/svg?seed={account_name}"
            )
            bio_text = bio or f"{platform.upper()} 优质对标创作者 · 持续分享行业前沿与高价值思考"

            if existing:
                existing.account_id = final_acc_id
                existing.home_url = final_url
                if avatar_url:
                    existing.avatar_url = avatar_url
                if bio:
                    existing.bio = bio
                existing.updated_at = datetime.now(timezone.utc)
                sess.add(existing)
                sess.commit()
                sess.refresh(existing)
                return cls.serialize_account(existing)
            else:
                new_acc = BenchmarkAccount(
                    id=uuid.uuid4(),
                    user_id=uid,
                    platform=platform,
                    account_name=account_name.strip(),
                    account_id=final_acc_id,
                    home_url=final_url,
                    avatar_url=avatar,
                    bio=bio_text,
                    follower_count=28500,
                    notes_count=142,
                    last_synced_at=None,
                    status="active",
                )
                sess.add(new_acc)
                sess.commit()
                sess.refresh(new_acc)
                return cls.serialize_account(new_acc)

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def list_benchmark_accounts(
        cls,
        platform: Optional[str] = None,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> List[BenchmarkAccountResponse]:
        """Lists all benchmark accounts tracked by the user."""
        def _execute(sess: Session) -> List[BenchmarkAccountResponse]:
            uid = _parse_uid(user_id)
            if not uid:
                user = CognitiveService.get_or_create_default_user(sess)
                uid = user.id

            q = select(BenchmarkAccount).where(BenchmarkAccount.user_id == uid)
            if platform:
                q = q.where(BenchmarkAccount.platform == platform.lower().strip())
            q = q.order_by(BenchmarkAccount.created_at.desc())

            accounts = sess.exec(q).all()
            return [cls.serialize_account(a) for a in accounts]

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

    @classmethod
    def delete_benchmark_account(
        cls,
        account_id: str | uuid.UUID,
        session: Optional[Session] = None,
    ) -> bool:
        """Deletes a tracked benchmark account."""
        p_id = _parse_uid(account_id)
        if not p_id:
            return False

        def _execute(sess: Session) -> bool:
            acc = sess.get(BenchmarkAccount, p_id)
            if not acc:
                acc = sess.exec(
                    select(BenchmarkAccount).where(
                        BenchmarkAccount.account_id == str(account_id).strip()
                    )
                ).first()
            if not acc:
                return False
            sess.delete(acc)
            sess.commit()
            return True

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

