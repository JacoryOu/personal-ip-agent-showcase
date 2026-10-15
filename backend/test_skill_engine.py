import pytest
from app.core.skill_engine import (
    discover_skills,
    get_skill_manager,
    SkillDefinition,
)


def test_skill_discovery():
    """Verifies that all built-in skills are discovered and parsed accurately."""
    skills = discover_skills()
    assert "media_article_extractor" in skills
    assert "viewpoint_insight_miner" in skills
    
    extractor = skills["media_article_extractor"]
    assert extractor.runner_mode == "restricted_token"
    assert "network:read" in extractor.permissions
    assert extractor.entrypoint_path.exists()
    
    miner = skills["viewpoint_insight_miner"]
    assert miner.runner_mode == "restricted_token"
    assert miner.entrypoint_path.exists()


def test_openai_tool_definition_conversion():
    """Verifies conversion to standard OpenAI tool call function schema."""
    sm = get_skill_manager()
    skill = sm.get_skill("media_article_extractor")
    assert skill is not None
    
    tool_def = skill.to_tool_definition()
    assert tool_def["type"] == "function"
    assert tool_def["function"]["name"] == "media_article_extractor"
    assert "parameters" in tool_def["function"]
    assert "properties" in tool_def["function"]["parameters"]


def test_media_article_extractor_execution():
    """Verifies execution of media-article-extractor in isolated sandbox."""
    sm = get_skill_manager()
    sample_html = """
    <html>
        <head><title>Sandboxed Architecture Report</title></head>
        <body>
            <article>
                <h1>Sandboxed Architecture Report</h1>
                <p>Windows AppContainer and Hyper-V isolation guarantees complete host protection.</p>
            </article>
        </body>
    </html>
    """
    result = sm.execute_skill_sync(
        "media_article_extractor",
        {"html_content": sample_html},
    )
    assert result.success is True
    assert isinstance(result.output, dict)
    assert "Sandboxed Architecture Report" in result.output.get("title", "")
    assert "Windows AppContainer" in result.output.get("text", "")


def test_viewpoint_insight_miner_execution():
    """Verifies execution of viewpoint-insight-miner in isolated sandbox with genuine content."""
    sm = get_skill_manager()
    content = "我们在系统架构演进中必须坚决反对盲目重构。底层逻辑在于，最稳健的代码往往是自底向上演进而非一次性颠覆出来的。坚持工程落地与测试覆盖永远高于一切口号。"
    
    # Test own_work mode
    res_own = sm.execute_skill_sync(
        "viewpoint_insight_miner",
        {"content": content, "analysis_type": "own_work"},
    )
    assert res_own.success is True
    assert isinstance(res_own.output, dict)
    assert len(res_own.output.get("vocabulary_habits", [])) >= 1
    assert len(res_own.output.get("logic_preferences", [])) >= 1
    assert len(res_own.output.get("core_values", [])) >= 1
    
    # Test benchmark mode
    bench_content = "未来五年传统单体架构将彻底死亡！所有企业都必须在今年全面淘汰旧技术。唯一可行的出路是拥抱分布式智能体集群。毫无疑问，这是唯一的未来。"
    res_bench = sm.execute_skill_sync(
        "viewpoint_insight_miner",
        {"content": bench_content, "analysis_type": "benchmark"},
    )
    assert res_bench.success is True
    assert "blueprint" in res_bench.output
    assert len(res_bench.output.get("clash_points", [])) >= 1
    assert any("彻底死亡" in cp.get("claim", "") or "必须" in cp.get("claim", "") for cp in res_bench.output["clash_points"])


def test_large_article_payload_avoids_win32_command_length_limit():
    """CRITICAL WIN32 TEST: Verifies that large articles (>35KB) avoid Win32 CreateProcess command length limit ([WinError 206])."""
    sm = get_skill_manager()
    paragraph = "在大型软件系统重构过程中，工程师必须深刻理解边界条件与状态机流转。底层逻辑永远是代码的健壮性与可维护性。" * 800
    assert len(paragraph) > 35000  # Exceeds Win32 32767 chars limit

    res = sm.execute_skill_sync(
        "viewpoint_insight_miner",
        {"content": paragraph, "analysis_type": "own_work"},
    )
    assert res.success is True
    assert isinstance(res.output, dict)
    assert len(res.output.get("core_values", [])) >= 1


def test_skill_not_found_handling():
    """Verifies non-existent skill execution fails gracefully."""
    sm = get_skill_manager()
    res = sm.execute_skill_sync("non_existent_skill", {"foo": "bar"})
    assert res.success is False
    assert "not found" in (res.error or "").lower()
