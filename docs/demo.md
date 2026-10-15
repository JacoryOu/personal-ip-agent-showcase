# 演示说明（真实模型运行记录，2026-10-15）

> 中文（默认） | [English](demo.en.md)

本文件记录**一次**真实模型端到端运行。**这不是评测**：没有基准集，没有延迟 / 成本 / 质量指标。

引擎是**固定编排工作流**（`backend/app/engine/cognitive_engine.py`），不是自主规划 Agent。

| 项目 | 本轮状态 |
| --- | --- |
| 选题输入 → A/B 大纲 → 初稿生成 | **真实模型验证** |
| 初稿归档、观点反馈 → DNA 画像演化 | 此前曾验证，**非本轮运行记录** |
| 人工编辑全文 → `diff_agent` 双版本比对 → DNA 提取 | **仅 Mock 测试，本轮未在浏览器验证** |
| 受限令牌沙盒下的真实 Skill 执行 | **本轮未触发** |
| 微信记录导入、多平台真实发布 | **未实现 / 未验证** |

## 1. 使用的环境

- 后端：FastAPI，`http://127.0.0.1:8000`。
- 前端：Vue 3 + Vite 开发服务器，5173 端口被占用，本次运行在 `http://127.0.0.1:5177/`。
- 数据库：独立演示 SQLite 文件 `demo-data/job-demo.db`，**没有读写任何真实业务数据库**。该文件属于演示产物，已被 `.gitignore` 排除，不随仓库提交。
- 鉴权：`AUTH_REQUIRED=false`、`AUTH_LOCAL_DEV_MODE=true`（仅本地演示）。
- 模型：OpenAI 兼容端点，模型 `deepseek-v4-flash-0731`。凭据保存在本地 `.env` 中，**此处绝不呈现**。

## 2. 启动命令（本文件不含任何凭据）

后端：

```powershell
cd <repo-root>
$env:DATABASE_URL = "sqlite:///<repo-root>/demo-data/job-demo.db"
$env:AUTH_REQUIRED = "false"
$env:AUTH_LOCAL_DEV_MODE = "true"
<python> -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

前端：

```powershell
cd frontend
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev        # 本次运行在 http://127.0.0.1:5177/
```

可用的存活检查：`http://127.0.0.1:8000/api/openapi.json` 返回 HTTP 200。
注意：本项目**没有** `/api/health` 路由，早期文档中的该检查为错误描述，已删除。

注意：Windows 控制台对流式输出可能出现中文乱码；API 响应与本文件均为 UTF-8，内容正确。

## 3. UI 中的复现步骤

1. 打开开发服务器，进入「创作工坊」。
2. 输入合成选题
   `AI Agent 工作流的可评估性：如何把重复工作变成可追溯的自动化流程`
   并提交 → `POST /api/outlines/generate` → 截图 **01**（输入界面）。
3. 等待两份大纲返回 → 截图 **02**。两份大纲均来自 `OutlineAgent` 的真实模型调用。
4. 点击「选此方案 B」，再点「生成初稿并归档」→ `POST /api/drafts/generate` → 截图 **03**（初稿编辑器）。本次草稿生成耗时约 111 秒。

## 4. 实际观察结果（本轮唯一一轮运行）

| 项目 | 本次运行的值 |
| --- | --- |
| 草稿 id | `4a072bddea59432ca5f5a412118ee8ea`（仅演示数据库，不是业务指标） |
| 草稿标题 | `别急着"评估"AI工作流——先学会"听懂"它的身体语言` |
| 字数（API `metadata.word_count`） | **2908** |
| 原始草稿 Unicode 字符数（`len(original_ai_draft)`） | **3703** |
| 大纲来源 | `OutlineAgent` 真实模型调用（方案 A / B） |

**字数口径说明**：编辑器顶部「~2908 字」来自后端 `metadata.word_count`，是本文档的主口径；正文统计区显示的「3703 字符」是原始草稿字符串的 Unicode 字符数（含标点与空白），两者口径不同，不可混用。

标题、字数、草稿 id 与截图 **03** 完全一致，均取自本轮同一份真实结果。

## 5. 截图清单

| 文件 | 页面 | 体现内容 |
| --- | --- | --- |
| `docs/images/01-topic-input.png` | 创作工坊选题输入 | 真实 UI + 合成输入 |
| `docs/images/02-divergent-outlines.png` | 发散 A/B 大纲 | 真实模型输出 + 方案选择 |
| `docs/images/03-draft-generated.png` | 初稿编辑器 | 真实模型初稿、字数统计、归档 / 排版 / DNA / 观点动作 |

工具说明：内置浏览器工具初始化失败（`e.nodeRepl?.setResponseMeta is not a function`），因此截图由本地 Playwright + Chrome Headless Shell 针对运行中的开发服务器采集；临时脚本与页面文本已在采集后删除，未提交仓库。

## 6. 本次演示的诚实限制

1. 一次成功运行**不等于评测**：该流程没有基准集、延迟、成本、质量或可靠性数字。
2. 模型输出具有非确定性，**同样的输入不会保证得到同样的标题与正文**，本文档记录的是某一次真实结果，不应被视为可复现的固定输出。
3. 沙盒隔离**部分**（仅受限令牌；无 AppContainer、无文件系统 ACL、无网络隔离、无 `WindowsSandbox.exe`）。
4. 数据库只读隔离仅覆盖 Agent 读路径；初稿归档与 DNA 演化流为有意可写。
5. 真实模型运行只走到大纲与初稿生成；`diff_agent` 双版本比对仅由 Mock 测试覆盖。
6. 多平台分发与微信记录导入**未实现**；LoRA/QLoRA 仅了解原理与基本流程，**无训练与评测证据**。
7. 本轮 `AUTH_REQUIRED=false`，不构成任何鉴权隔离的证据。
