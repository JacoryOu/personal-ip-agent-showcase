# 评测与测试证据

> 中文（默认） | [English](evaluation.en.md)

## 0. 当前结果（2026-10-15，展示副本内复跑）

在独立导出目录 `Personal-IP-Agent-Showcase` 中，使用原项目虚拟环境解释器、无网络凭据执行：

```powershell
cd <repo-root>
<python> -m pytest -q --no-header -p no:cacheprovider
```

结果：

```
1010 passed, 3 skipped, 86 warnings in 67.89s
```

## 1. 旧的“18 项失败”是什么，为什么当时还有失败

早期版本的本文件记录过 `992 passed / 18 failed / 3 skipped / 97 warnings`。需要说明清楚：

1. **那是本地保存的历史快照，不是 GitHub Actions 的 CI 报告**，也不是最终状态。
2. 公开导出快照形成之后代码又发生了变化，所以本轮第一次复跑时是 **17 项失败**（比旧快照少 1 项），并非 18 项原样重现。
3. 本轮把这 17 项全部定位并修复，过程中失败数变化为：**17 → 12 → 0**。

根因共五类，全部是确定性缺陷，不是环境抖动：

| 类别 | 位置 | 表现 |
| --- | --- | --- |
| helper 在调用点使用但 formatter 未定义／未导入 | `skills/content-multi-distributor/scripts/_formatters.py`、`_formatters_xhs.py` | 微信／小红书排版中断；`extract_footnotes` 同样缺失 |
| API 使用 `status` 但未导入 | `backend/app/api/draft_generation.py` | 仅影响 ValueError 的 422 失败路径 |
| Service 使用 `CognitiveTrait` 但未导入 | `backend/app/services/memory_conflicts.py` | 观点冲突检测抛 `NameError` |
| 集成测试在鉴权开启时未传 API Key header | `backend/test_blueprint_creation_and_distribution.py` | 请求被 401 拦截；**未削弱生产鉴权** |
| Skill 子进程测试中的异常包装 | 上述 formatter 相关用例 | 一个根因表现为多条表面失败 |

修复均为最小改动：补齐缺失的 import／helper 定义，或补齐测试请求头。**未新增任何业务功能，未为了让测试变绿而修改生产鉴权或放宽断言。**

## 2. 3 项 skip 与 86 项 warning 的范围

- **3 项 skip**：与运行环境条件相关（例如需要特定平台能力或外部依赖），不是失败，也不是被隐藏的用例。
- **86 项 warning**：以弃用告警为主，另有 FastAPI／OpenAPI `operation_id` 重复等提示。它们不影响断言结果。

## 3. 这些测试属于哪一层

| 层次 | 能证明什么 | **不能**证明什么 |
| --- | --- | --- |
| 单元 / 集成测试（pytest） | 代码路径可执行、契约成立 | 与真实 LLM、真实 PostgreSQL、真实网络出口、真实用户无关 |
| Mock 模型网关 | 提示装配、schema 解析、门控、归属、持久化 | 模型质量、延迟、成本、幻觉率 |
| 治理门禁脚本 | 代码风格与文档覆盖的机械约束 | 功能正确性 |
| 真实模型调用 | `docs/demo.md` 记录的一次端到端运行 | 可靠性、质量、延迟、成本 |
| 真实 PostgreSQL | **未运行**（默认 SQLite） | — |
| 真实多用户安全演练 | **未执行** | — |

请把「1010 passed」理解为「当前自动化覆盖的代码路径全部通过」，而不是「产品已被验证」。

## 4. 带真实数据集的基准

`backend/app/engine/rubrics/data/viral_rubric_benchmark_v1.json` 存放 **43 条人工标注样本**。`backend/app/engine/rubrics/viral_benchmark.py` 用以下指标对确定性规则实现评分：

- 误差不超过一级的准确率（within-one-level accuracy）
- 平均绝对误差（MAE）
- 精确匹配率（exact match）

代码中建议阈值：MAE <= 0.8，精确匹配率 >= 0.60。

**关键注意**：该基准衡量的是「规则实现能否复现人工标签」，**不衡量 LLM 生成质量**；且这 43 条标签由谁产出尚未确认（见 `docs/resume-notes.md`）。

## 5. 明确未测的指标

以下内容不要写进简历，本仓库没有证据：

- 检索召回率 / 准确率 / MRR / nDCG。混合检索器没有带标注的检索集。
- 人工评分得到的答案或初稿质量分。
- 端到端延迟、首字时间、吞吐、token 成本。
- 任何「提升 X%」或「降低 Y%」的说法。
- 用户量、活跃用户、发布篇数、GMV、节省工时。
- 真实模型下的可靠性、安全性或越狱率。
- LoRA/QLoRA 微调效果（无任何训练与评测）。

## 6. 安全回归套件（当前均通过）

| 领域 | 测试 |
| --- | --- |
| 只读数据库强制 | `tests/test_agent_db_readonly.py` |
| 路由鉴权面 | `tests/test_api_auth_surface.py`、`tests/test_auth_and_ownership.py` |
| SSRF | `tests/test_net_guard.py`、`test_net_guard_image_service.py`、`test_settings_ssrf.py` |
| 凭据加密 | `tests/test_credential_encryption.py`、`test_secret_box.py` |
| 提示词 / 密钥泄漏 | `tests/test_security_*.py`、`test_error_contract.py` |
| 沙盒 | `tests/test_restricted_token.py`、`test_sandbox_mode_transparency.py`、`test_sandbox_acl_integration.py`、`test_os_network_boundary.py`、`test_job_object.py`、`test_sandbox_permission_gate.py` |
| 工作流权限 | `tests/test_workflow_permissions.py`、`test_workflow_permission_gate.py` |
| 治理门禁 | `tests/test_code_style.py`、`tests/test_doc_coverage.py` |

## 7. 复现方式

全量测试：

```powershell
<python> -m pytest -q --no-header -p no:cacheprovider
```

治理门禁：

```powershell
<python> scripts/check_doc_coverage.py --base main
<python> -m pytest backend/tests/test_doc_coverage.py -q
<python> scripts/check_code_style.py
<python> scripts/check_code_style.py --base main
<python> -m pytest backend/tests/test_code_style.py -q
```

规则基准：

```powershell
<python> -m pytest backend/tests -q -k rubric
```

## 8. 真实模型端到端运行（2026-10-15）

详见 `docs/demo.md`。使用真实 OpenAI 兼容模型（`deepseek-v4-flash-0731`）与**独立演示 SQLite 数据库**，通过浏览器 UI 完成：

```
选题输入 -> A/B 大纲（真实模型）-> 选择大纲 B
-> 初稿生成（真实模型，metadata.word_count = 2908）-> 初稿编辑器
```

**能证明**：接线的流水线可端到端执行到初稿生成。

**不能证明**：

- 初稿质量、幻觉率、多次运行一致性（n = 1，且模型输出非确定性）。
- 延迟、token 成本、吞吐。
- 「人工编辑全文 → `diff_agent` 双版本比对」的完整路径（仅 Mock）。
- 真实 PostgreSQL 下的行为。
- 受限令牌沙盒下的 Skill 执行。
- 本次运行的任何多用户 / 鉴权隔离行为（`AUTH_REQUIRED=false`）。

截图 01–03 来自该次运行，输入为合成数据；草稿 id 不是业务指标。
