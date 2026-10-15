# 评测与测试证据

> 中文（默认） | [English](evaluation.en.md)

以下所有数字均来自 2026-10-15 在本地以仓库虚拟环境、单进程、无 CI 运行的测试：

```
cd backend
.\.venv\Scripts\python -m pytest -q
-> 18 failed, 992 passed, 3 skipped, 85 warnings in 66.88s
```

本目录中的脱敏副本用同样命令复测，结果与源仓库**一致**：`18 failed, 992 passed, 3 skipped`（70.64s）。

系统解释器（`python -m pytest`）因缺少 `pydantic_settings` 失败；这是环境错误，**不计入**项目测试结果。

## 1. 这些测试属于哪一层

| 层次 | 能证明什么 | **不能**证明什么 |
| --- | --- | --- |
| 单元 / 集成测试（pytest；`backend/tests` 下 55 个文件，另有 18 个 `backend/test_*.py`） | 代码路径可执行、契约成立 | 与真实 LLM、真实 PostgreSQL、真实网络出口、真实用户无关 |
| Mock 模型网关 | 提示装配、schema 解析、门控、归属、持久化 | 模型质量、延迟、成本、幻觉率 |
| 真实模型调用 | 本文件第 7 节流程运行**一次**（无语料、无质量指标） | 可靠性、质量、延迟、成本 |
| 真实 PostgreSQL | **本轮未运行**（默认 SQLite） | — |
| 真实多用户安全演练 | **未执行** | — |

多数 Agent 测试替换了模型网关，因此是确定性的、快速的。请把「992 passed」理解为「骨架可用」，而不是「产品已被验证」。

## 2. 失败项（真实缺陷，非环境问题）

| 测试 | 数量 | 根因 |
| --- | --- | --- |
| `test_blueprint_creation_and_distribution.py` | 15 | `skills/content-multi-distributor/scripts/_formatters_xhs.py` 与 `_formatters.py` 调用 `clean_title_text` 却未从 `_content` 导入。微信 / 小红书排版因此中断。 |
| `test_dna_conflict_and_management.py::test_viewpoint_conflict_detection` | 1 | `backend/app/services/memory_conflicts.py:124` 使用 `CognitiveTrait` 注解但未导入。 |
| `test_api_routes.py::test_generate_draft_error_handling` | 1 | `backend/app/api/draft_generation.py:68` 使用 `status.HTTP_422_UNPROCESSABLE_CONTENT`，但未导入 `status`。仅影响 ValueError 失败路径。 |
| `tests/test_api_auth_surface.py::test_public_endpoint_registry_matches_application` | 1 | pytest 从 `backend/` 运行时 `ModuleNotFoundError: No module named 'scripts'`。属于 sys.path / 运行位置问题，不是业务缺陷。 |

三个业务缺陷都是一行导入修复。本轮为文档工作，**刻意保留未修**。

## 3. 带真实数据集的基准

`backend/app/engine/rubrics/data/viral_rubric_benchmark_v1.json` 存放 **43 条人工标注样本**。`backend/app/engine/rubrics/viral_benchmark.py` 用以下指标对确定性规则实现评分：

- 误差不超过一级的准确率（within-one-level accuracy）
- 平均绝对误差（MAE）
- 精确匹配率（exact match）

代码中建议阈值：MAE <= 0.8，精确匹配率 >= 0.60。

**关键注意**：该基准衡量的是「规则实现能否复现人工标签」，**不衡量 LLM 生成质量**；且这 43 条标签由谁产出尚未确认（见 `docs/resume-notes.md`）。

## 4. 明确未测的指标

以下内容不要写进简历，本仓库没有证据：

- 检索召回率 / 准确率 / MRR / nDCG。混合检索器没有带标注的检索集。
- 人工评分得到的答案或初稿质量分。
- 端到端延迟、首字时间、吞吐、token 成本。
- 任何「提升 X%」或「降低 Y%」的说法。
- 用户量、活跃用户、发布篇数、GMV、节省工时。
- 真实模型下的可靠性、安全性或越狱率。

## 5. 安全回归套件（当前均通过）

| 领域 | 测试 |
| --- | --- |
| 只读数据库强制 | `tests/test_agent_db_readonly.py` |
| 路由鉴权面 | `tests/test_api_auth_surface.py`（一处 sys.path 失败）、`tests/test_auth_and_ownership.py` |
| SSRF | `tests/test_net_guard.py`、`test_net_guard_image_service.py`、`test_settings_ssrf.py` |
| 凭据加密 | `tests/test_credential_encryption.py`、`test_secret_box.py` |
| 提示词 / 密钥泄漏 | `tests/test_security_*.py`、`test_error_contract.py` |
| 沙盒 | `tests/test_restricted_token.py`、`test_sandbox_mode_transparency.py`、`test_sandbox_acl_integration.py`、`test_os_network_boundary.py`、`test_job_object.py`、`test_sandbox_permission_gate.py` |
| 工作流权限 | `tests/test_workflow_permissions.py`、`test_workflow_permission_gate.py` |
| 治理门禁 | `tests/test_code_style.py`、`tests/test_doc_coverage.py` |

## 6. 复现治理门禁

```powershell
python scripts/check_doc_coverage.py --base main
python -m pytest backend/tests/test_doc_coverage.py -q
python scripts/check_code_style.py
python scripts/check_code_style.py --base main
python -m pytest backend/tests/test_code_style.py -q
```

## 7. 真实模型端到端运行（2026-10-15）

使用真实 OpenAI 兼容模型（`deepseek-v4-flash-0731`）与**独立演示 SQLite 数据库**，通过浏览器 UI 完成一次功能运行：

```
选题输入 -> A/B 大纲（真实模型）-> 选择大纲 B
-> 初稿生成（真实模型，1301 字）-> 初稿归档
-> POST /api/drafts/{id}/feedback/evolve -> 思维 DNA 特质持久化
-> GET /api/dna/profile 返回新增特质
```

**能证明**：接线的流水线可端到端执行；一个 `feedback/evolve` 判断会改变存储的画像。

**不能证明**：

- 答案 / 初稿质量、幻觉率、多次运行一致性（n = 1）。
- 延迟、token 成本、吞吐。
- 「人工编辑全文 → `diff_agent` 双版本比对」的完整路径（仅 Mock）。
- 真实 PostgreSQL 下的行为。
- 受限令牌沙盒下的 Skill 执行。
- 本次运行的任何多用户 / 鉴权隔离行为（`AUTH_REQUIRED=false`）。

`README.md` 中的截图 01-03 来自本次运行，输入为合成数据。演示数据库与服务日志在采集后已删除；上述草稿 id 不是业务指标。

## 8. 展示副本的独立验证运行

在独立导出目录（`Personal-IP-Agent-Showcase`）中，使用项目自身虚拟环境解释器、无网络凭据执行：

```powershell
python -m pytest -q --no-header -p no:cacheprovider
```

结果：

- 通过：992
- 跳过：3
- 失败：18
- 警告：97

这 18 个失败**未被隐藏或重新分类**，均属于 `README.md` 与 `docs/feature-status.md` 中已声明为损坏 / 部分实现的类别：

1. `skills/content-multi-distributor` 平台排版 `NameError`（`test_blueprint_creation_and_distribution.py`）。
2. 观点冲突检测 `NameError`（`test_dna_conflict_and_management.py::test_viewpoint_conflict_detection`）。
3. `test_api_routes.py::test_generate_draft_error_handling` `NameError`。
4. `tests/test_api_auth_surface.py::test_public_endpoint_registry_matches_application` 失败，本轮未进一步定位。

本轮未新增任何业务功能，也未修改源码让测试变绿。治理门禁（`scripts/check_code_style.py`、`scripts/check_doc_coverage.py`）在**原始工作树**中运行并通过；导出副本是子集快照，不是受门禁保护的工作树。
