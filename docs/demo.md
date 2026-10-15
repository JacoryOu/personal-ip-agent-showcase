# 演示说明（真实模型运行，2026-10-15）

> 中文（默认） | [English](demo.en.md)

本文件记录**一次**真实模型端到端运行。**这不是评测**：没有基准集，没有延迟 / 成本 / 质量指标。

引擎是**固定编排工作流**（`backend/app/engine/cognitive_engine.py`），不是自主规划 Agent。

| 项目 | 本轮状态 |
| --- | --- |
| 选题输入 → A/B 大纲 → 初稿生成 | **真实模型验证** |
| 归档 + 观点反馈 → DNA 画像更新 | **真实模型验证** |
| 人工编辑全文 → `diff_agent` 比对双版本 → DNA 提取 | **仅 Mock 测试，未在本轮浏览器验证** |
| 受限令牌沙盒下的真实 Skill 执行 | **本轮未触发** |
| 微信记录导入、多平台发布 | **未实现 / 未验证** |

## 1. 使用的环境

- 后端：项目 venv，FastAPI 运行在 `http://127.0.0.1:8000`。
- 前端：Vue 3 + Vite 开发服务器。5173 端口被占用，因此演示运行在 `http://127.0.0.1:5176/`。
- 数据库：独立演示 SQLite 文件 `demo-data/job-demo.db`，即**没有读写任何真实业务数据库**。该文件与服务日志在采集后已删除。
- 鉴权：`AUTH_REQUIRED=false`、`AUTH_LOCAL_DEV_MODE=true`（仅本地演示）。
- 模型：OpenAI 兼容端点，模型 `deepseek-v4-flash-0731`。API Key 保存在本地根目录 `.env` 中，**此处绝不呈现**。

## 2. 启动命令（本文件不含任何凭据）

后端：

```powershell
cd <repo-root>
$env:DATABASE_URL = "sqlite:///<repo-root>/demo-data/job-demo.db"
$env:AUTH_REQUIRED = "false"
$env:AUTH_LOCAL_DEV_MODE = "true"
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

前端：

```powershell
cd frontend
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev        # 本次运行在 http://127.0.0.1:5176/
```

本次运行返回 HTTP 200 的健康检查：`http://127.0.0.1:8000/api/health` 与 Vite 开发服务器根路径。

注意：Windows 控制台对流式输出可能出现中文乱码；API 响应与本文件均为 UTF-8，内容正确。

本次观察到一个非阻塞启动告警，**刻意未修改**（本轮业务代码不在范围内）：`StyleFingerprint.register` 遮蔽了 `BaseModel` 的属性名。

## 3. UI 中的复现步骤

1. 打开 Vite 开发服务器，进入工作台。
2. 输入合成选题
   `AI Agent 工作流的可评估性：如何把重复工作变成可追溯的自动化流程`
   并提交 → `POST /api/outlines/generate` → 截图 **01**（输入界面）。
3. 等待两份大纲返回 → 截图 **02**。两份大纲均来自 `OutlineAgent` 的真实模型调用。
4. 点击「选此方案 B」，再点「生成初稿并归档」→ `POST /api/drafts/generate` → 截图 **03**（初稿编辑器）。
5. （可选，本轮通过 API 而非 UI 验证）通过 `POST /api/drafts/{draft_id}/feedback/evolve` 提交观点判断，然后读取 `GET /api/dna/profile`。

## 4. 实际观察结果

| 项目 | 本次运行的值 |
| --- | --- |
| 草稿 id | `d856099c-1c6b-43ae-9fe2-5cd9cc97fe26`（仅演示数据库，不是业务指标） |
| 草稿标题 | `把「效率工具」讲成「思考系统」：AI Agent 应该怎么用` |
| 草稿长度 | 1301 字 |
| `feedback/evolve` | HTTP 成功 |
| 持久化的 DNA 特质 | `core_value`，置信度 `1.5`，状态 `active`，`evolution_boost_count = 1` |
| 回读 | `GET /api/dna/profile` 返回新增特质，`source_draft_id` 与演示草稿一致 |

本次验证了 **`feedback/evolve` → 画像演化** 路径。本轮**没有**在浏览器中验证「人工编辑全文 → `diff_agent` 双版本比对」路径，该路径仅由 Mock 测试覆盖。

## 5. 截图清单

| 文件 | 页面 | 体现内容 |
| --- | --- | --- |
| `docs/images/01-topic-input.png` | 工作台选题输入 | 真实 UI + 合成输入 |
| `docs/images/02-divergent-outlines.png` | 发散 A/B 大纲 | 真实模型输出 + 方案选择 |
| `docs/images/03-draft-generated.png` | 初稿编辑器 | 真实模型初稿、精修 diff、归档 / 排版 / DNA / 观点动作 |

工具说明：内置浏览器工具初始化失败（`e.nodeRepl?.setResponseMeta is not a function`），因此截图由本地 Playwright 1.64.1 + Chrome Headless Shell 156 针对运行中的开发服务器采集；临时脚本目录已在采集后移除。

## 6. 本次演示的诚实限制

1. 一次成功运行**不等于评测**：该流程没有基准集、延迟、成本、质量或可靠性数字。
2. 沙盒隔离**部分**（仅受限令牌；无 AppContainer、无文件系统 ACL、无网络隔离、无 `WindowsSandbox.exe`）。
3. 数据库只读隔离仅覆盖 Agent 读路径；初稿归档与 DNA 演化流为有意可写。
4. 微信 / 小红书排版与观点冲突检测当前含已知的一行导入缺陷（`NameError`），见 `docs/evaluation.md`。
5. 多平台分发、微信记录导入与 LoRA/QLoRA 微调**未实现**；不得当作功能展示。
