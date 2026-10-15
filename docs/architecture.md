# 架构说明（代码核实，2026-10-15）

> 中文（默认） | [English](architecture.en.md)

本文件描述代码**实际**的行为。当代码与原始设计文档不一致时，以代码为准。

## 1. 分层

```
frontend/（Vue 3 + TS + Vite）
   |  HTTP（src/services/api/*.ts 中的 fetch 封装）
   v
backend/app/api/          FastAPI 路由
   - public_router：显式 PUBLIC_ENDPOINTS 白名单（health、鉴权入口）
   - private_router：每条路由依赖 get_current_user
   v
backend/app/engine/       无头核心（不导入 FastAPI）
   - CognitiveEngine（外观层，通过 get_cognitive_engine 单例）
   - agents/{outline,draft,diff}_agent.py
   - model_gateway.py（角色 -> 模型、结构化输出、回退）
   - prompts/（所有提示词文本都在这里，由代码风格门禁强制）
   v
backend/app/services/     业务逻辑（记忆、认知、风格、爬虫、凭据）
backend/app/core/         db（+ 只读引擎）、auth、net_guard、crypto、
                          vault_path_guard、skill_engine
skills/<name>/SKILL.md    声明式 Skill 定义 + python 脚本
```

关键边界：`CognitiveEngine` 不导入 FastAPI。API 层是薄适配层，引擎可被测试或 CLI 直接调用。

## 2. 核心循环（固定编排，**不是**自主规划 Agent）

本代码库**没有** planner、router、reflection 循环，也没有 LLM function-calling。流水线是 `cognitive_engine.py` 中的显式序列：

```
POST /api/outlines/generate
  -> OutlineAgent.generate_outlines()
       - ModelGateway(role=outline) -> 结构化 OutlineOutput
       - lexical_filter.clean()
       -> 大纲 A / 大纲 B

POST /api/drafts/generate
  -> 归属校验（_get_owned_draft、_reject_body_user_id）
  -> DraftAgent
       - 在**只读会话**上装配 IP bundle：
           Persona、ThinkingDNA 2.0、认知特质、情节记忆、
           蓝图、观点冲突、风格指纹
       - ModelGateway(role=draft)
       - lexical_filter.clean()
       - 在**独立可写会话**归档初稿 + 血缘记录

用户在 UI 中编辑初稿，提交最终文本

POST /api/dna/extract
  -> DiffAgent
       - 零差异门控：若 AI 文本 == 人工文本且未提供观点判断，
         在调用 LLM 之前中止
       - ModelGateway(role=diff)
       - 回写 DNA 记录 / 认知画像（可写路径）

（可选）POST /api/drafts/distribute
  -> skills/content-multi-distributor
       -> 微信 / 小红书 / X / 短视频排版
```

Agent 之间通过 Pydantic 对象、数据库行与服务调用传递数据。它们**不互相通信**、没有共享黑板、不会互相评审输出。

## 3. 模型网关

`backend/app/engine/model_gateway.py`：

- 将逻辑角色（outline / draft / diff / image 等）按配置映射到模型名与温度。
- 使用 `AsyncOpenAI` 对接 OpenAI 兼容端点（支持 `OPENAI_BASE_URL`，因此 DeepSeek / OneAPI / Azure 均可）。
- 通过 Pydantic schema 解析结构化输出，并有回退路径。

## 4. 提示词管理

所有类提示词字符串字面量都位于 `backend/app/engine/prompts/`。代码风格门禁（`scripts/check_code_style.py`）会在 `.py` 文件的该目录之外出现提示词字面量时失败。这是**真实强制**，不是约定。

## 5. 记忆与检索

- `memory_service.py` 是多个职责模块的门面（`memory_retrieval`、`memory_dna_retrieval`、`memory_blueprints`、`memory_conflicts`、`memory_evolution`、`memory_lifecycle`、`memory_similarity`）。
- 情节记忆检索（`memory_retrieval.retrieve_relevant_stories`）是**混合**打分：`0.5 * 词法重合 + 0.5 * cos(embedding) + confidence*0.1`。词法一侧对中文做关键词 / bigram / trigram 匹配。
- **没有**学习式重排器，**没有**向量数据库；相似度是存储 embedding 上的普通余弦。
- 上下文装配在只读会话上进行；写入路径独立。

## 6. 只读数据库引擎（仅 Agent 读路径）

`backend/app/core/db.py` 构建第二个引擎 `readonly_engine`：

- SQLite：以 `?mode=ro&uri=true` 打开，并在 connect 时 `PRAGMA query_only=ON`。
- PostgreSQL：`SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` 与 `default_transaction_read_only = on`。
- 不支持的后端（MySQL）与 `:memory:` SQLite **失败即关闭**，抛出 `UnsupportedReadOnlyBackendError`。

回归证据：`backend/tests/test_agent_db_readonly.py` 证明通过只读会话的写入在**驱动层**失败，而不是靠约定。

范围（面试时请精确表述）：只读会话覆盖输入上下文装配。初稿归档与 DNA / 画像演化为有意可写。

## 7. 安全边界

| 边界 | 实现 | 说明 |
| --- | --- | --- |
| 路由鉴权 | 公开端点白名单 + 其余路由依赖 `get_current_user` | `tests/test_api_auth_surface.py`、`tests/test_auth_and_ownership.py` |
| 数据归属 | 草稿等资源按 `user_id` 校验归属 | `tests/test_auth_and_ownership.py` |
| SSRF | `core/net_guard.py`：协议白名单 -> 拒绝带凭据 URL -> 主机白名单 -> 解析 DNS 并校验每个 IP -> 端口白名单 -> 逐跳重定向复检 -> 超时 -> 响应体积上限 | `tests/test_net_guard*.py` |
| 凭据存储 | `core/crypto/secret_box.py`（基于 `cryptography` 的 Fernet 风格） | `tests/test_credential_encryption.py` |
| 提示注入 / 密钥泄漏 | 测试断言提示词不回显原始用户密钥、堆栈信息或他人数据 | `tests/test_security_*.py` |

## 8. Skill 引擎与沙盒（部分隔离）

`backend/app/core/skill_engine/`：

- 发现阶段读取 `skills/*/SKILL.md`（name、description、`permissions`）。
- 策略门控决定是否允许无人值守（调度器驱动）运行。
- 执行器如实报告：`requested_runner_mode`、`runner_mode`、`sandbox_enforced`、`warnings`。
- `restricted_token`：创建真实的 Windows 受限令牌（`CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)` + 标记为 deny-only 的限制 SID 列表），并用 `CreateProcessAsUserW` 启动子进程。成功时 `sandbox_enforced=True`。
- 若无法创建受限令牌，**失败即关闭**（`runner_mode="restricted_token_unavailable"`、`success=False`），绝不静默降级为普通子进程。
- `wsb` 失败即关闭（`wsb_unsupported`）；**从不启动** `WindowsSandbox.exe`。

**不保证**：AppContainer、文件系统 ACL 隔离、网络隔离、注册表 / 剪贴板 / COM 隔离、子进程 job 策略。

回归：`tests/test_restricted_token.py`、`tests/test_sandbox_mode_transparency.py`、`tests/test_sandbox_acl_integration.py`、`tests/test_os_network_boundary.py`、`tests/test_job_object.py`。

## 9. 无人值守调度

`api/scheduler.py` + `services/inspection_scheduler_*.py` 定时运行 Skill 并持久化状态，使重启不会重复执行（`tests/test_scheduler_state_persistence.py`）。调度器驱动的运行必须通过权限策略门控（`tests/test_workflow_permission_gate.py`）。

## 10. 代码实际做出的设计取舍

以下是代码事实，不是主观评价；是否属于有意的产品决策需你本人确认。

1. **固定序列而非 planner。** 更易推理、成本更低，但无法自主从中间失败中恢复。
2. **调用 LLM 前做零差异门控。** 无改动时省下一次付费调用；代价是不产生「无变化」的分析记录。
3. **代码级词法过滤而非仅靠提示词。** 让保证不依赖模型是否遵守提示。
4. **为读取构建第二个物理数据库引擎。** 比会话标志更强，但连接管理翻倍，且让 SQLite 文件处理更复杂。
5. **安全层一律失败即关闭。** 更安全，但缺失 Windows 原语时是硬失败而非降级模式。
