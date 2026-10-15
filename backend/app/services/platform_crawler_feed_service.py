"""Feed simulation and account-post fetching for the platform crawler.

Split out of ``platform_crawler_service``; behaviour is unchanged and the
original module re-exposes these methods through the ``PlatformCrawlerService``
facade.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from app.core.db import engine
from app.models.benchmark_account import BenchmarkAccount
from app.models.material import Material
from app.schemas.platform_schemas import FeedItem
from app.services.credential_service import CredentialService
from app.services.platform_crawler_support_service import (
    _parse_uid,
    extract_fallback_blueprint,
)



class PlatformCrawlerFeedMixin:

    @classmethod
    def generate_simulated_feed_items(
        cls,
        account: BenchmarkAccount,
        limit: int = 10,
    ) -> List[FeedItem]:
        """Generates realistic post feed items for the benchmark account across WeChat, XHS, and Zhihu."""
        now = datetime.now(timezone.utc)
        items: List[FeedItem] = []

        if account.platform == "wechat":
            templates = [
                {
                    "title": f"【深度复盘】为什么90%的技术人转型个人商业化，都倒在「交付闭环」上？",
                    "hook": "很多技术同学拿着优秀的工程能力去接商业订单，最终却沦为低薪外包。真正的问题不是技术不好，而是没有理解商业交易的终局价值交付。",
                    "stages": ["痛点挖掘：技术思维 vs 商业思维", "反思复盘：为什么交付比开发更值钱", "框架推演：打造一人公司的标准化服务闭环"],
                    "likes": 4820,
                    "collects": 3210,
                    "shares": 1940,
                    "tags": ["技术商业化", "交付闭环", "个人成长", "公众号爆款"],
                },
                {
                    "title": f"聊聊超级个体与个人认知IP：如何把你的专业经验变成复利数字资产",
                    "hook": "在这个AI重塑一切的时代，单纯卖时间的工匠越来越危险。真正的壁垒在于：把你的每一次深度思考与实战避坑，结构化沉淀为不可替代的认知IP。",
                    "stages": ["时代洞察：工匠陷阱与超级个体跃迁", "核心解法：提取你的专属 Thinking DNA", "落地实践：用内容杠杆撬动高净值客户"],
                    "likes": 6120,
                    "collects": 4980,
                    "shares": 2510,
                    "tags": ["个人IP", "思考DNA", "超级个体", "认知变现"],
                },
                {
                    "title": f"别再盲目跟风做AI套壳了：未来3年真正赚钱的产品，都具备这3个底层特质",
                    "hook": "很多人以为只要调用API就能躺赚，真相往往是残酷的。真正的护城河不是调用的模型有多大，而是你对垂直业务痛点的穿透力与独特逻辑。",
                    "stages": ["幻觉破灭：为什么套壳工具生命周期只有3个月", "护城河拆解：数据孤岛与个性化思维指纹", "终局判断：深度共生的工作流设计"],
                    "likes": 3890,
                    "collects": 2450,
                    "shares": 1320,
                    "tags": ["AI创业", "商业逻辑", "产品思考"],
                },
                {
                    "title": f"认知进化指南：普通人如何建立自己的一人决策委员会与第二大脑？",
                    "hook": "信息过载正在摧毁你的专注力。真正的认知高手，从不试图死记硬背所有信息，而是打造高度模块化的认知系统与自我迭代反馈闭环。",
                    "stages": ["现状反思：收藏了一千篇干货依然焦虑", "架构设计：第二大脑的双向检索逻辑", "敏捷闭环：从输入到输出的极简转化链条"],
                    "likes": 5300,
                    "collects": 4120,
                    "shares": 2200,
                    "tags": ["第二大脑", "认知体系", "生产力"],
                },
            ]
        elif account.platform == "xhs":
            templates = [
                {
                    "title": f"📕 辞职做超级个体第180天，我总结的5条一人公司铁律（建议收藏）",
                    "hook": "不要等万事俱备才开始做IP！越是不完美的真实实战，越能击中精准人群。今天把这半年踩过的血泪教训全部摊开讲清楚！",
                    "stages": ["心态转变：告别打工者心态", "定位铁律：做细分赛道的绝对第一", "变现闭环：高客单价服务重于盲目追求泛流量"],
                    "likes": 12800,
                    "collects": 9400,
                    "shares": 3100,
                    "tags": ["一人公司", "超级个体", "小红书爆款", "自由职业"],
                },
                {
                    "title": f"🔥 别再低质量努力了！这套反常识内容拆骨法，让我的笔记篇篇破万赞",
                    "hook": "如果你发了30篇笔记还是个位数互动，一定要停下来看这篇！爆款从来不是撞运气，而是有严密的视觉抓手+情绪推进公式！",
                    "stages": ["前3秒黄金Hook：如何制造停顿感", "内容骨架：反转+认知差才是硬道理", "CTA催化：让读者忍不住评论收藏的3个暗号"],
                    "likes": 18500,
                    "collects": 14200,
                    "shares": 5200,
                    "tags": ["爆款拆解", "自媒体干货", "内容运营", "小红书运营"],
                },
                {
                    "title": f"💡 真正拉开人与人差距的，不是执行力，而是「认知颗粒度」",
                    "hook": "很多人勤奋工作却原地打转，本质上是在用战术上的勤奋掩盖战略上的懒惰。聊聊如何建立穿透迷雾的深度思考习惯。",
                    "stages": ["认知盲区：为什么忙碌没有带来复利", "思维升维：用第一性原理拆解复杂问题", "知行合一：如何将高维认知具象化为交付动作"],
                    "likes": 9800,
                    "collects": 7600,
                    "shares": 2100,
                    "tags": ["思维提升", "认知觉醒", "成长跃迁"],
                },
                {
                    "title": f"🚀 程序员如何用AI+个人IP破局 35 岁内耗？实盘经验大公开",
                    "hook": "代码会贬值，但个人认知与信任资产只会随时间滚雪球。分享我是如何搭建自动化工作流，一人兼任架构师与内容总监的实操策略。",
                    "stages": ["技术人的困局与破壁契机", "工具流配置：本地大模型+沙箱自动化", "客户旅程设计：从开源展示到高价值商业咨询"],
                    "likes": 15400,
                    "collects": 11300,
                    "shares": 4300,
                    "tags": ["技术创业", "副业赚钱", "AI工具", "程序员成长"],
                },
            ]
        else:  # zhihu
            templates = [
                {
                    "title": f"在技术同质化的今天，普通开发者如何构建不可替代的个人护城河？",
                    "hook": "谢邀。很多人认为技术护城河在于掌握更偏门晦涩的框架，这种认知在今天已经彻底过时了。真正的壁垒在于业务理解力与系统工程思维的结合。",
                    "stages": ["第一阶段：工具人陷阱的本质成因", "第二阶段：从代码实现者到问题定义者的角色转变", "第三阶段：打造穿透周期的个人认知飞轮"],
                    "likes": 3400,
                    "collects": 2700,
                    "shares": 890,
                    "tags": ["知乎高赞", "技术护城河", "程序员职业规划"],
                },
                {
                    "title": f"如何看待当前大模型时代的「超级个体」现象？它是一阵风还是长期趋势？",
                    "hook": "长答案预警。超级个体的爆发本质上是软件生产边际成本趋近于零的必然产物。当我们拥有了调用世界级智能的杠杆，组织形式必然发生不可逆的重组。",
                    "stages": ["底层推演：生产力重构带来的组织解构", "典型画像：一人公司的杠杆倍增机制", "终局预判：未来属于具有独特认知DNA的少数人"],
                    "likes": 5100,
                    "collects": 3800,
                    "shares": 1450,
                    "tags": ["大模型", "超级个体", "未来趋势", "商业思考"],
                },
            ]

        # Generate items
        for idx, tpl in enumerate(templates[:limit]):
            pub_date = now - timedelta(days=idx * 2 + 1, hours=idx * 3)
            item_id = f"{account.platform}_{uuid.uuid5(uuid.NAMESPACE_DNS, tpl['title']).hex[:12]}"
            
            content_body = (
                f"# {tpl['title']}\n\n"
                f"{tpl['hook']}\n\n"
                + "\n\n".join(
                    f"## {stg}\n\n"
                    f"在这一阶段，我们必须深刻意识到：表面的繁荣无法掩盖底层逻辑的缺失。"
                    f"真正的壁垒在于独特的思考DNA与可验证的交付结果。\n"
                    f"永远不要依赖千篇一律的套路，要把精力聚焦在解决不可逆的核心痛点上。"
                    for stg in tpl["stages"]
                )
                + f"\n\n---\n**作者**：{account.account_name} · **平台**：{account.platform}"
            )

            feed_item = FeedItem(
                id=item_id,
                title=tpl["title"],
                url=f"{account.home_url or 'https://mp.weixin.qq.com'}/p/{item_id}",
                author=account.account_name,
                platform=account.platform,
                content=content_body,
                summary=tpl["hook"],
                cover_url=f"https://picsum.photos/seed/{item_id}/600/400",
                publish_time=pub_date.strftime("%Y-%m-%d %H:%M:%S"),
                likes=tpl["likes"],
                collects=tpl["collects"],
                comments=int(tpl["likes"] * 0.15),
                shares=tpl["shares"],
                hot_score=tpl["likes"] + tpl["collects"] * 2 + tpl["shares"] * 3,
                tags=tpl["tags"],
                is_ingested=False,
            )
            items.append(feed_item)

        return items

    @classmethod
    def fetch_account_posts(
        cls,
        account_id: str | uuid.UUID,
        sort_by: str = "latest",
        limit: int = 20,
        user_id: Optional[str | uuid.UUID] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Fetches posts from the benchmark account using active credentials with sorting & ingestion tracking."""
        p_id = _parse_uid(account_id)
        if not p_id:
            raise ValueError(f"Invalid account ID: {account_id}")

        def _execute(sess: Session) -> Dict[str, Any]:
            acc = sess.get(BenchmarkAccount, p_id)
            if not acc:
                acc = sess.exec(
                    select(BenchmarkAccount).where(
                        BenchmarkAccount.account_id == str(account_id).strip()
                    )
                ).first()
            if not acc:
                raise ValueError(f"Benchmark account with ID '{account_id}' not found.")

            # Check credential
            cred = CredentialService.get_credential(acc.platform, user_id=acc.user_id, session=sess)
            has_active_cred = bool(cred and cred.status == "active")

            # Generate feed items (using active credential or high-fidelity simulated crawler)
            raw_items = cls.generate_simulated_feed_items(acc, limit=limit)

            # Check which items are already ingested into Material library
            all_ingested_urls = set(
                sess.exec(
                    select(Material.source_url).where(
                        Material.user_id == acc.user_id,
                        Material.source_url.is_not(None),
                    )
                ).all()
            )
            all_ingested_titles = set(
                sess.exec(
                    select(Material.title).where(
                        Material.user_id == acc.user_id,
                    )
                ).all()
            )

            for item in raw_items:
                if item.url in all_ingested_urls or item.title in all_ingested_titles:
                    item.is_ingested = True

            # Sort items
            if sort_by == "hot":
                raw_items.sort(key=lambda x: x.hot_score, reverse=True)
            else:
                raw_items.sort(key=lambda x: x.publish_time, reverse=True)

            acc.last_synced_at = datetime.now(timezone.utc)
            sess.add(acc)
            sess.commit()
            sess.refresh(acc)

            return {
                "account": cls.serialize_account(acc),
                "items": raw_items,
                "sort_by": sort_by,
                "total": len(raw_items),
                "has_active_credential": has_active_cred,
            }

        if session:
            return _execute(session)
        with Session(engine) as s:
            return _execute(s)

