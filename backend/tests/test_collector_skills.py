# -*- coding: utf-8 -*-
from pathlib import Path
import sys

# Ensure backend root is on sys.path
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest
from app.core.skill_engine.discovery import discover_skills
from app.core.skill_engine.windows_sandbox import WindowsSandboxRunner


@pytest.fixture(scope="module")
def skill_runner():
    return WindowsSandboxRunner(default_timeout=15.0)


@pytest.fixture(scope="module")
def all_skills():
    return discover_skills()


# ==============================================================================
# Trending Radar Skill Tests
# ==============================================================================

def test_trending_radar_skill_discovery(all_skills):
    """Verifies that trending_radar skill is correctly discovered with proper metadata."""
    assert "trending_radar" in all_skills, "trending_radar skill should be discovered"
    skill = all_skills["trending_radar"]
    assert skill.name == "trending_radar"
    assert skill.runner_mode == "restricted_token"
    assert skill.entrypoint_path.exists(), f"Entrypoint not found: {skill.entrypoint_path}"


def test_trending_radar_offline_fallback(skill_runner, all_skills):
    """Verifies that trending_radar aggregates topics with full metadata across platforms."""
    skill = all_skills["trending_radar"]
    result = skill_runner.run_skill_sync(skill, {"limit": 15})

    assert result.success is True, f"Execution failed: {result.error} | {result.stderr}"
    items = result.output
    assert isinstance(items, list), "Output should be a list of topic objects"
    assert len(items) > 0, "Should return trending items"
    assert len(items) <= 15, "Should respect limit parameter"

    # Verify structured schema for each item
    platforms_seen = set()
    for item in items:
        assert "title" in item and item["title"], "Item must have non-empty title"
        assert "hot_value" in item and isinstance(item["hot_value"], int), "hot_value must be int"
        assert "platform" in item and item["platform"], "platform must be non-empty"
        assert "category" in item, "category must be present"
        assert "summary" in item, "summary must be present"
        assert "url" in item and item["url"].startswith("http"), "url must be a valid web address"
        assert "score" in item and 0.0 <= item["score"] <= 1.0, "score must be between 0.0 and 1.0"
        platforms_seen.add(item["platform"])

    # Ensure multi-platform coverage
    assert len(platforms_seen) >= 2, f"Should cover multiple platforms, got: {platforms_seen}"


def test_trending_radar_keyword_filtering_and_scoring(skill_runner, all_skills):
    """Verifies keyword filtering, relevance scoring, and descending score sorting."""
    skill = all_skills["trending_radar"]
    keywords = ["AI", "商业", "独立开发", "效率"]
    result = skill_runner.run_skill_sync(
        skill,
        {"keywords": keywords, "limit": 6}
    )

    assert result.success is True
    items = result.output
    assert isinstance(items, list)
    assert len(items) > 0

    scores = [item["score"] for item in items]
    # Check that items are sorted in descending order of score
    assert scores == sorted(scores, reverse=True), "Items must be sorted by score descending"

    # Every item must match at least one keyword in title, summary, or category
    for item in items:
        text_corpus = f"{item['title']} {item['summary']} {item['category']}".lower()
        matched = any(kw.lower() in text_corpus for kw in keywords)
        assert matched, f"Item '{item['title']}' should match at least one keyword from {keywords}"
        assert item["score"] > 0.0, "Matched item should have positive score"


def test_trending_radar_platform_selection(skill_runner, all_skills):
    """Verifies that selecting specific platforms filters out all others."""
    skill = all_skills["trending_radar"]
    target_platforms = ["zhihu", "36kr"]
    result = skill_runner.run_skill_sync(
        skill,
        {"platforms": target_platforms, "limit": 10}
    )

    assert result.success is True
    items = result.output
    assert isinstance(items, list)
    assert len(items) > 0
    for item in items:
        assert item["platform"] in target_platforms, f"Item platform {item['platform']} not in {target_platforms}"


def test_trending_radar_min_score_threshold(skill_runner, all_skills):
    """Verifies that min_score filters out topics with lower relevance scores."""
    skill = all_skills["trending_radar"]
    threshold = 0.5
    result = skill_runner.run_skill_sync(
        skill,
        {"keywords": ["AI"], "min_score": threshold, "limit": 10}
    )

    assert result.success is True
    items = result.output
    assert isinstance(items, list)
    for item in items:
        assert item["score"] >= threshold, f"Item score {item['score']} must be >= {threshold}"


# ==============================================================================
# Content Collector Skill Tests
# ==============================================================================

def test_content_collector_skill_discovery(all_skills):
    """Verifies content_collector skill discovery and metadata."""
    assert "content_collector" in all_skills, "content_collector skill should be discovered"
    skill = all_skills["content_collector"]
    assert skill.name == "content_collector"
    assert skill.runner_mode == "restricted_token"
    assert skill.entrypoint_path.exists()


def test_content_collector_raw_text_deconstruction(skill_runner, all_skills):
    """Verifies content skeleton (BenchmarkBlueprint) extraction from raw markdown text."""
    skill = all_skills["content_collector"]
    raw_article = """# 为什么说千篇一律的AI工具没有未来？

很多人以为只要接入了API，就能自动躺赚，真相往往是残酷的。真正的商业壁垒不是代码本身，而是独特的思考DNA与交付价值。

## 一、同质化危机与破局痛点
当所有人都在调用相同的大模型时，生成的文章千篇一律。核心逻辑在于建立不可替代的个人认知IP。

## 二、超级个体的一人公司实战框架
本质上，高净值用户买单的永远不是碎片信息，而是笃定的解决方案。我们必须把注意力聚焦在终局价值交付上。

## 三、终局推演：人机协同认知进化
未来的超级个体必然与智能体深度共生，从单纯的内容消费者蜕变为认知系统架构师。
"""

    result = skill_runner.run_skill_sync(skill, {"content": raw_article})

    assert result.success is True, f"Failed: {result.error} | {result.stderr}"
    data = result.output
    assert isinstance(data, dict)
    assert data["success"] is True
    assert "千篇一律" in data["title"]
    assert data["word_count"] > 100
    assert "cleaned_markdown" in data and len(data["cleaned_markdown"]) > 0

    blueprint = data.get("blueprint", {})
    assert "title_formula" in blueprint
    assert "颠覆" in blueprint["title_formula"] or "反直觉" in blueprint["title_formula"]
    assert "opening_hook" in blueprint and len(blueprint["opening_hook"]) > 5
    assert "key_stages" in blueprint and len(blueprint["key_stages"]) >= 3
    assert "emotional_arc" in blueprint and len(blueprint["emotional_arc"]) > 0
    assert "golden_quotes" in blueprint and isinstance(blueprint["golden_quotes"], list)
    assert len(blueprint["golden_quotes"]) >= 2
    assert "pacing" in blueprint and len(blueprint["pacing"]) > 0


def test_content_collector_wechat_html_cleaning_and_metadata(skill_runner, all_skills):
    """Verifies WeChat Official Accounts HTML parsing, boilerplate stripping, and metadata extraction."""
    skill = all_skills["content_collector"]
    sample_wechat_html = """<!DOCTYPE html>
<html>
<head>
  <title>别再死记硬背了：构建个人思考DNA的认知体系 - 微信公众平台</title>
  <meta name="author" content="认知工坊" />
  <meta property="article:published_time" content="2026-09-18T08:30:00Z" />
  <meta property="og:image" content="https://mmbiz.qpic.cn/cover123.jpg" />
</head>
<body>
  <div class="ad_top_banner">广告赞助商信息：点击领取优惠</div>
  <div id="js_content">
    <h1 id="activity-name">别再死记硬背了：构建个人思考DNA的认知体系</h1>
    <span id="js_name">认知工坊</span>
    <p>在这个信息过载的时代，为什么你收藏了上千篇干货依然无法解决实际问题？本质上是因为缺少了自己的认知骨架。</p>
    <h2>第一阶段：打破信息囤积陷阱</h2>
    <p>知识不是资产，提取与应用的能力才是资产。<strong>必须建立高频反馈闭环</strong>。</p>
    <h2>第二阶段：提炼属于你的思考DNA</h2>
    <p>真正的壁垒在于独特的逻辑偏好与价值判断。永远不要依赖千篇一律的通用模板。</p>
    <blockquote>
      核心在于：每一次人机交互，都应当沉淀为数字资产。
    </blockquote>
    <h2>第三阶段：落地实践与超级个体跃迁</h2>
    <p>用工程化方法打造个人第二大脑，实现从工匠到认知架构师的跃迁。</p>
  </div>
  <div class="share_bottom">关注微信公众号，获取更多精彩干货</div>
  <script>console.log("analytics script");</script>
</body>
</html>"""

    result = skill_runner.run_skill_sync(
        skill,
        {
            "html_content": sample_wechat_html,
            "url": "https://mp.weixin.qq.com/s/sample_article_uuid"
        }
    )

    assert result.success is True
    data = result.output
    assert data["success"] is True

    # Check cleaned title (site suffix stripped)
    assert "别再死记硬背了" in data["title"]
    assert "微信公众平台" not in data["title"]

    # Check author & metadata
    assert "认知工坊" in data["author"]
    assert data["publish_time"] == "2026-09-18T08:30:00Z"
    assert "cover123.jpg" in data["cover_image_url"]

    # Check boilerplate stripping
    cleaned_md = data["cleaned_markdown"]
    assert "广告赞助商信息" not in cleaned_md
    assert "analytics script" not in cleaned_md
    assert "关注微信公众号" not in cleaned_md

    # Check markdown elements
    assert "## 第一阶段：打破信息囤积陷阱" in cleaned_md
    assert "**必须建立高频反馈闭环**" in cleaned_md
    assert "> 核心在于" in cleaned_md

    # Check Blueprint extraction
    bp = data["blueprint"]
    assert "title_formula" in bp
    assert len(bp["key_stages"]) >= 3
    assert len(bp["golden_quotes"]) >= 2


def test_content_collector_zhihu_html_cleaning(skill_runner, all_skills):
    """Verifies Zhihu post HTML parsing with rich formatting conversion."""
    skill = all_skills["content_collector"]
    sample_zhihu_html = """<!DOCTYPE html>
<html>
<head>
  <title>独立开发者出海从零到月入一万刀全复盘 - 知乎</title>
</head>
<body>
  <div class="Post-Main">
    <h1 class="Post-Title">独立开发者出海从零到月入一万刀全复盘</h1>
    <span class="AuthorInfo-name">出海极客</span>
    <div class="Post-RichText">
      <p>很多人问我：普通开发者如何才能出海做出正向现金流产品？答案其实并不复杂。</p>
      <h2>一、痛点挖掘与海外选品</h2>
      <p>不要试图做一个所有人都喜欢的平台，<em>先解决一个微小但痛彻心扉的刚需</em>。核心逻辑在于快速构建MVP。</p>
      <h2>二、冷启动与增长黑客实操</h2>
      <p>海外流量并不神秘，真正的壁垒在于高质量的交付与持续的迭代。必须学会用自动化工具武装自己。</p>
    </div>
  </div>
</body>
</html>"""

    result = skill_runner.run_skill_sync(
        skill,
        {
            "html_content": sample_zhihu_html,
            "url": "https://zhuanlan.zhihu.com/p/123456"
        }
    )

    assert result.success is True
    data = result.output
    assert data["success"] is True
    assert "全复盘" in data["title"]
    assert "知乎" not in data["title"]
    assert data["author"] == "出海极客"

    cleaned_md = data["cleaned_markdown"]
    assert "## 一、痛点挖掘与海外选品" in cleaned_md
    assert "*先解决一个微小但痛彻心扉的刚需*" in cleaned_md

    bp = data["blueprint"]
    assert "复盘" in bp["title_formula"] or "指南" in bp["title_formula"] or "跃迁" in bp["title_formula"]
    assert len(bp["golden_quotes"]) >= 1


def test_content_collector_empty_input_handling(skill_runner, all_skills):
    """Verifies that collector gracefully handles missing/empty input without crashing."""
    skill = all_skills["content_collector"]
    result = skill_runner.run_skill_sync(skill, {})

    # Process shouldn't crash; should return error status or dict
    assert result.output.get("success") is False
    assert "error" in result.output