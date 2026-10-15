# 功能状态清单（代码核实，2026-10-15）

> 中文（默认） | [English](feature-status.en.md)

图例：
**A** = 已实现并有通过测试覆盖
**B** = 已实现，但本轮未对真实依赖运行验证
**C** = 开发中或存在已知缺陷
**P** = 仅规划，未实现

## 核心内容循环

| # | 功能 | 状态 | 代码证据 |
| --- | --- | --- | --- |
| 1 | 发散 A/B 大纲生成 | A | `engine/agents/outline_agent.py`、`api/outlines.py`、`tests/test_outline_agent_mock.py` |
| 2 | 带 IP 上下文的初稿生成 | A | `engine/agents/draft_agent.py`、`api/draft_generation.py` |
| 3 | 初稿失败路径错误契约 | C | `api/draft_generation.py:68` 的 `status` NameError |
| 4 | 初稿归档 + 血缘 | A | `api/draft_archive.py`、`api/draft_lineage.py`、`tests/test_drafts_archive_api.py` |
| 5 | 初稿反馈 | A | `api/draft_feedback.py`、`tests/test_feedback_and_evolution.py` |
| 6 | 基于差异的思维 DNA 提取 | A | `engine/agents/diff_agent.py`、`tests/test_diff_agent.py` |
| 7 | 零差异基线门控（跳过 LLM） | A | `diff_agent.py`、`tests/test_diff_agent.py` |
| 8 | DNA v2 + 时间线 + 取代 | A | `api/dna_v2*.py`、`tests/test_dna_v2_and_timeline.py` |
| 9 | Persona 提取 / 认知访谈 | A | `api/dna_v2_persona_extract*.py`、`tests/test_persona_extraction_and_interview.py` |
| 10 | 观点冲突检测 | C | `services/memory_conflicts.py:124` NameError |
| 11 | 闭环画像演化 | A | `services/cognitive_evolution_service.py`、`tests/test_closed_loop_and_profile.py` |
| 12 | DNA 可移植（导出 / 导入） | A | `api/dna_portability.py`、`services/cognitive_portability_service.py` |
| 13 | 初稿风格指纹选择 | A | `services/style_selection_service.py`、`tests/test_style_selection_service.py` |
| 14 | 爆款语义分析（风格指纹） | A | `api/viral_analysis.py`、`tests/test_viral_semantic_analysis.py` |
| 15 | 爆款评分基准（43 条样本） | B | `engine/rubrics/`、`tests/test_viral_rubric_benchmark.py`（标签来源未确认） |
| 16 | 聊天休息室（会话 + 结晶） | B | `api/chat_lounge*.py`、`tests/test_chat_lounge.py` |
| 17 | 微信聊天记录导入 | P | 代码中未找到导入路径 |
| 18 | 图片生成 | B | `services/image_service.py`、`tests/test_image_generation.py` |
| 19 | 产品保险库 | B | `models/product.py`、`tests/test_product_image_vault.py`、`test_product_vault_extraction.py` |
| 20 | 素材保险库 + Obsidian 桥接 | B | `services/material_service.py`、`obsidian_service.py`、`tests/test_materials_and_lineage.py`、`test_obsidian_bridge.py` |
| 21 | 私域界面（朋友圈 / 社区） | B | `api/private_domain*.py`、`tests/test_private_domain.py` |

## 记忆

| # | 功能 | 状态 | 代码证据 |
| --- | --- | --- | --- |
| 22 | 情节记忆 CRUD | A | `services/memory_service.py`、`models/story.py` |
| 23 | 混合检索（词法 + 余弦 embedding） | A | `services/memory_retrieval.py`、`memory_dna_retrieval.py`、`memory_similarity.py` |
| 24 | 从基准文章提取蓝图骨架 | A | `services/memory_blueprints.py`、`api/blueprints.py`、`tests/test_blueprint_extraction_api.py` |
| 25 | DNA embedding + 相似度检索 | A | `memory_dna_retrieval.py` |
| 26 | 记忆基准辅助工具 | B | `services/memory_benchmarks.py` |

## 平台 / 分发

| # | 功能 | 状态 | 代码证据 |
| --- | --- | --- | --- |
| 27 | 平台账号管理 | A | `services/platform_crawler_account_service.py`、`tests/test_platform_accounts_and_ingestion.py` |
| 28 | 平台信息采集（爬虫） | B | `services/platform_crawler_*.py`、`tests/test_platform_accounts_and_ingestion.py`（无真实网络运行） |
| 29 | 实时扫码登录 | B | `tests/test_live_qr_login.py`（需真实账号） |
| 30 | 多平台排版（微信 / 小红书 / X / 短视频） | C | `skills/content-multi-distributor/scripts/_formatters*.py` NameError |
| 31 | 平台自动发布 | P | 无发布 API；仅排版 + 预览 |
| 32 | 热点雷达 Skill | B | `skills/trending-radar/` |

## Skill 引擎与沙盒

| # | 功能 | 状态 | 代码证据 |
| --- | --- | --- | --- |
| 33 | SKILL.md 发现 + 策略 | A | `core/skill_engine/`、`tests/test_skill_engine.py`、`test_skill_permission_policy.py` |
| 34 | Windows 受限令牌执行 | B | `core/skill_engine/restricted_token.py`、`tests/test_restricted_token.py`（真实运行需 Windows 主机） |
| 35 | 子进程 Job Object | B | `core/skill_engine/job_object.py`、`tests/test_job_object.py` |
| 36 | ACL 路径守卫 | A | `core/skill_engine/acl_guard.py`、`tests/test_acl_guard.py`、`test_path_containment.py` |
| 37 | 失败即关闭的模式透明度 | A | `core/skill_engine/windows_sandbox.py`、`tests/test_sandbox_mode_transparency.py` |
| 38 | Windows Sandbox（`.wsb`）执行 | P | `runner_mode="wsb_unsupported"`，从不启动 |
| 39 | AppContainer / 文件系统 / 网络隔离 | P | 未实现 |
| 40 | OS 级网络边界 | B | `core/skill_engine/os_network_boundary.py`、`tests/test_os_network_boundary.py` |

## 平台关注点

| # | 功能 | 状态 | 代码证据 |
| --- | --- | --- | --- |
| 41 | 公开 / 私有路由边界 | A | `api/auth_boundary.py`、`tests/test_api_auth_surface.py` |
| 42 | 归属强制 | A | `tests/test_auth_and_ownership.py`、`test_security_private_surfaces.py` |
| 43 | SSRF 防护 | A | `core/net_guard.py`、`tests/test_net_guard*.py` |
| 44 | 静态凭据加密 | A | `core/crypto/secret_box.py`、`tests/test_credential_encryption.py` |
| 45 | 保险库路径包含 | A | `core/vault_path_guard.py`、`tests/test_path_containment.py`、`test_sec_path_quota.py` |
| 46 | 驱动级只读数据库引擎 | A | `core/db.py`、`tests/test_agent_db_readonly.py` |
| 47 | 错误契约（不泄漏堆栈） | A | `core/errors.py`、`tests/test_error_contract.py` |
| 48 | 限流 / 检查配额 | B | `services/inspection_quota_service.py`、`tests/test_inspection_quota*.py` |

## 治理

| # | 功能 | 状态 | 代码证据 |
| --- | --- | --- | --- |
| 49 | 代码风格门禁（行数上限、命名、提示词位置） | A | `scripts/check_code_style.py`、`scripts/code_style_baseline.txt`、`tests/test_code_style.py` |
| 50 | 文档覆盖门禁（提交需声明文档影响） | A | `scripts/check_doc_coverage.py`、`tests/test_doc_coverage.py` |
| 51 | 共享 git hooks（pre-commit / commit-msg / post-merge） | A | `scripts/install_git_hooks.ps1`、`scripts/install_git_hooks.sh` |
| 52 | CI 流水线 | P | 仓库中无 CI 配置 |
| 53 | 部署配置 | P | 未找到 |
| 54 | 微调（LoRA / QLoRA） | P | 未实现；仅有概念性了解 |
| 55 | 带引用 / 重排 / 答案评分的 RAG 问答 | P | 混合检索存在，但无带证据的 QA 流水线、无重排器、无答案质量评测 |

## 未测 / 未知

- 真实模型端到端运行（本轮已有一次，见 `docs/demo.md`；除此之外未测）。
- 真实 PostgreSQL 运行。
- 真实外网采集。
- 延迟 / 成本 / 吞吐。
- 43 条评分标签的作者。
