# 简历材料说明（AI Agent 应用开发工程师）

> 中文（默认） | [English](resume-notes.en.md)

本文件用于提炼简历可用材料，严格区分**代码可证明的部分**与**只有本人才能确认的部分**。
仓库中不存在用户量、营收、延迟优化等证据，因此本文不做此类声明。

## 1. 项目背景（代码可证实的定位）

一个个人内容生产引擎：把用户自己的写作"DNA"反复投入一条固定的多阶段 LLM 流水线。

`选题 → A/B 发散大纲 → 全文初稿 → 人工修改 → 基于差异的思维 DNA 提取 → 画像演化 → 多平台排版`

代码所实现的价值点：

- **写作风格的可复用性**：同一套 DNA 跨多篇文章复用。
- **治理层**：权限门禁、Prompt 与代码分离、代码风格与文档覆盖的 CI 强制检查，保证流水线可维护。

代码可证实的项目形态：

- 单仓多模块：FastAPI 后端 + Vue 3 / TypeScript 前端 + Python `skills/`。
- 无头引擎 `backend/app/engine/cognitive_engine.py`，由薄 API 层驱动，同一流程可从 API、CLI 或测试调用。
- 存储：SQLModel，默认 SQLite，兼容 PostgreSQL。

## 2. 个人贡献边界

### 已由本人确认（2026-10-15）

- **需求分析与系统 / 架构设计：本人。**
- **Code Review：本人** —— 审查本仓库内的实现代码（含 AI 辅助产出部分）。
- **整体功能测试：本人** —— 运行并判断端到端行为，包括 `docs/demo.md` 记录的真实模型演示。
- **项目功能与规则管理：本人** —— 负责功能清单、编码标准（`docs/architecture/09_Coding_Standards.md`）、沙盒 / 权限模型文档，以及将上述规则落为强制门禁的文档覆盖 / 代码风格规则。
- **个人项目。** 本人是唯一的人类负责人；实现代码由 AI 辅助产出，本人负责审查。

因此本人角色准确表述为：**需求分析 + 系统 / 架构设计 + 功能与工程规则管理 + Code Review + 端到端功能验证**，而非"我写了每一个模块"。

由此产生的措辞规则：

- 使用 designed / defined / specified / owned / reviewed / verified 等动词。
- 对本人未亲自编写的模块，避免使用 implemented / developed / built。
- 不要删除下面第 3 节的第 2—5 条技术要点：审查并验证一个机制是真实工作，且每一条都能追溯到具体代码路径。

### 待本人确认

| 范围 | 状态 |
| --- | --- |
| 后端实现代码作者身份（agents / services / DB / auth / skill engine） | 待本人确认 |
| 前端实现代码作者身份（Vue views / services / router） | 待本人确认 |
| 测试代码是本人编写，还是仅审查 / 维护既有测试 | 待本人确认 |
| 发布 / 部署 / CI 运维 | 待本人确认 |
| 功能清单 / 编码标准 / 文档与风格门禁的所有权 | **已确认：本人** |
| 个人项目还是团队项目 | **已确认：个人项目** |

AI 辅助与第三方组件边界（可直接对外表述）：

- AI 辅助：AI 编码 Agent（`codex` 提交）在仓库内产出了代码与文档，本人对其做 Code Review。
- 参考与框架惯例：SQLModel CRUD 结构、FastAPI 路由结构、pytest fixture 遵循公开框架文档；未内嵌第三方源码仓库（见 `PROVENANCE.md`）。
- 第三方组件（非本人工作）：FastAPI、SQLModel/SQLAlchemy、Pydantic、Vue、Vite、Tailwind、Playwright、trafilatura、`openai` SDK、通过 `ctypes` 调用的 Windows 系统 API。

## 3. 关键技术难点与解决方式

以下每条都可追溯到代码，面试时按自身可辩护的范围选取。

1. **让 Agent 的读取在物理上只读，而不是"请你别写"。**
   - 问题：Agent 需要画像 / DNA / 记忆上下文，但同一条链路还要归档初稿、演化 DNA，这部分必须可写。
   - 做法：`backend/app/core/db.py` 中构建第二个独立引擎。SQLite 连接使用 `sqlite:///file:<abs>?mode=ro&uri=true`，并在每次 connect 时 `PRAGMA query_only=ON`；PostgreSQL 执行 `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` 与 `default_transaction_read_only = on`。不支持的后端与 `:memory:` 直接以 `UnsupportedReadOnlyBackendError` 失败关闭。
   - 诚实的范围：只读仅覆盖 Outline / Draft 的输入上下文装配；初稿归档与 DNA / 画像演化按设计保持可写。`tests/test_agent_db_readonly.py` 证明写入在驱动层失败，而非依赖约定。

2. **不为"学不到东西"的 LLM 调用付费。**
   - `backend/app/engine/agents/diff_agent.py` 会比较 AI 初稿与用户终稿，当文本完全相同且未提供观点判断时，在**模型调用之前**中止。
   - 这是用 Python 实现的成本 / 延迟守卫，而不是 prompt 指令。

3. **Prompt 无法解决的"AI 腔"与风格漂移。**
   - `backend/app/utils/lexical_filter.py` 以 RegEx 移除填充词与替换模式。
   - `draft_agent.py` 与 `diff_agent.py` 都在代码中调用它，因此过滤不依赖模型是否"听话"。

4. **不引入向量库的混合检索。**
   - `backend/app/services/memory_retrieval.py` 与 `memory_dna_retrieval.py` 以
     `0.5 * 词法 + 0.5 * 余弦(embedding) + 置信度 * 0.1` 对故事 / DNA 特征排序。
   - 诚实的限制：无重排、无向量库、无检索指标评测，见 `docs/evaluation.md`。

5. **把 Prompt 治理做成构建门禁。**
   - 所有 prompt 文本位于 `backend/app/engine/prompts/`。
   - `scripts/check_code_style.py` 阻断该目录之外的 prompt 字符串字面量，并以"只允许下降"的基线强制文件体积上限。把约定变成了 CI 门禁。

6. **对用户提供的 URL 做 SSRF 防护。**
   - `backend/app/core/net_guard.py` 在采集器或图片服务抓取前校验协议 / DNS 解析 / 内网与保留地址段。
   - 覆盖于 `tests/test_net_guard*.py`、`tests/test_settings_ssrf.py`。

7. **拒绝假装沙盒存在。**
   - `backend/app/core/skill_engine/restricted_token.py` 真实调用
     `CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)`，并以 `CreateProcessAsUserW` 启动子进程。
   - `SandboxExecutionResult` 报告 `requested_runner_mode`、实际生效的 `runner_mode`、`sandbox_enforced` 与 `warnings`。
   - 受限令牌创建失败时**失败关闭**，不会降级为普通子进程执行；`wsb` 模式直接拒绝，绝不启动 `WindowsSandbox.exe`。
   - 未实现、不可声明：AppContainer、文件系统 ACL 隔离、网络隔离、注册表 / 剪贴板 / COM 隔离、子进程 job object 策略、`SKILL.md` `permissions` 强制执行。

8. **凭据处理。**
   - API 凭据静态加密存储（`backend/app/core/crypto/`），配置示例仅保留变量名与占位值。

## 4. 可验证结果

真实模型端到端运行（2026-10-15）：

- 合成选题经由真实模型完成：选题 → 大纲 A/B → 选择大纲 B → 初稿（1301 字）→ 归档 → `feedback/evolve` → 持久化 DNA 特征（`core_value`，confidence 1.5，status active）。
- 使用独立演示数据库 `demo-data/job-demo.db`，未读写真实业务数据库。
- 截图：`docs/images/01-topic-input.png`、`02-divergent-outlines.png`、`03-draft-generated.png`。
- 边界：这是**功能演示**，不是质量或性能评测。人工修改全文 → `diff_agent` 双版本对比 → DNA 提取这条路径**尚未在浏览器真实验证**，仅由 Mock 测试覆盖。

测试现状（如实记录，不粉饰）：

- 导出目录全量测试：`992 passed / 18 failed / 3 skipped`。
- 18 项失败的真实原因：多平台排版 formatter 与草稿错误处理、观点冲突检测中的缺失 import（`NameError`），以及一项公共端点注册表测试的 `ModuleNotFoundError`。多平台排版当前不可用。
- 治理检查（源项目）：`59 passed`，文档覆盖与代码风格门禁通过，前端构建成功。

## 5. 简历候选表述（选 3—5 条）

第 1—5 条按第 2 节已确认的"需求 / 设计 + 审查 + 验证"角度撰写；只有当本人确认亲自实现了对应部分时，才可改用"implemented"。

1. **（岗位匹配）** 为一套 FastAPI + Vue 3 的个人内容引擎做需求分析、系统架构与工程规则设计：把用户提取出的写作"DNA"投入固定四阶段 LLM 流水线（发散大纲 A/B → 初稿 → 人工修改 → 差异比对 DNA 提取），模型网关与全部 Prompt 分离，使角色、模型与 Prompt 版本可独立配置与测试。
2. 审查并验证了驱动级 Agent 读取隔离（SQLite `mode=ro` + `query_only`，PostgreSQL 只读事务），而非依赖 Prompt 或代码约定，并用回归测试确认写入失败路径。
3. 验证了风格控制从 Prompt 提示改为代码级确定性 RegEx 词法过滤（初稿与差异两条链路均生效），以及在人工终稿与初稿逐字节相同时于模型调用前跳过的零差异门控。
4. **（审查）** 审查并界定了基于真实 Restricted Token（`CreateRestrictedToken` + `CreateProcessAsUserW`）的 Windows Skill 沙盒：失败即关闭，并如实报告实际生效的隔离级别；同时明确记录尚未隔离的部分（无 AppContainer、无文件系统 ACL 与网络边界）。
5. **（规则所有权）** 制定并落地了仓库治理门禁的执行规则（Prompt 字面量位置约束、体积基线只降不升、提交时文档覆盖门禁），并在独立演示数据库上以真实模型跑通端到端链路，确认流水线确实可执行，而不只是单元测试通过。
6. 负责本仓库的功能范围与工程规则：维护以代码为准的功能清单、编码标准（体积基线只降不升、Prompt 字面量限定在 `engine/prompts/`）、沙盒 / 权限现状文档与提交期文档覆盖门禁，把约定变成强制检查而不是评审意见。
7. **（角色诚实版，可直接使用）** 负责该引擎的需求分析与系统设计，审查 AI 辅助产出的实现代码，并在独立演示数据库上用真实模型验证完整内容流水线（大纲 → 初稿 → 反馈 → DNA 持久化），采集三张核心界面证据。

刻意回避的表述："自主规划 Agent"、"多 Agent 协作"、"完整沙盒"、"多平台自动分发"、"LoRA 微调"，以及任何百分比提升或用户量指标。

## 6. 目前不应写进简历的说法

- "构建了自主 / 自我规划 Agent" —— 这是固定编排流水线。没有 planner、router、reflection 循环、LLM function calling，也没有 Agent 间协商。
- "用 LoRA/QLoRA 微调了模型" —— 未实现。最多只能说了解其原理与基本流程。
- "多平台内容分发" —— 目前只有排版 / 预览，且因缺失 import 当前不可用。
- 不加限定地说"Skill 沙盒执行" —— 仅 Windows 受限令牌，无操作系统级文件与网络隔离。
- "转化率提升 X%" 或任何业务收益 —— 未测。

## 7. 仍需补充的信息（按优先级，最多三项）

1. **个人贡献的窄口径确认。** 后端 / 前端模块是否有本人亲自编写的部分、测试代码是编写还是仅审查、CI / 部署是否由本人负责。这三项不影响以设计 / 审查 / 验证为主线的表述，保持"待确认"是诚实的。
2. **若需要更强的展示证据。** 目前已有一次真实模型端到端运行与三张界面截图（`docs/demo.md`、`docs/images/`），使用合成输入与一次性 SQLite 文件，属于功能演示；质量与性能评测尚未做。
3. **环境与数据来源的真实性。** 是否曾在真实 PostgreSQL、真实外网采集环境下运行；评测集中的 43 条评分标签由本人、同事还是外部来源提供。这决定哪些环境声明与基准声明可以写。

## 8. 简历使用建议

- 面向 **AI Agent 应用开发工程师**：优先第 1、7 条作为定位句，配第 2 或第 3 条作为技术深度证据，再配第 5 条体现工程治理能力。
- 面试展开时，选一条技术要点（建议第 2 条只读隔离或第 4 条沙盒边界）深入讲，因为这两条都能直接打开对应源码文件当场验证，最能体现"审查过、验证过"的分量。
- 切勿把 18 项失败说成"全部通过"；被问到测试时，如实说明失败集中在缺失 import 的三处及一项注册表测试。
