# 来源与公开状态说明（Provenance）

> 中文（默认） | [English](PROVENANCE.en.md)

本目录是私有工作仓库的**脱敏展示副本**，仅通过文件筛选生成，**未修改任何业务逻辑**。

## 有意移除的内容

- `.env`、`app.db`、`.git/`、`.venv/`、`node_modules/`、`__pycache__/`、`screenshots/`、`test_renders/`、`backend/data/`、模型缓存、日志。
- `backend/pyproject.toml` 中的作者姓名 / 邮箱（已替换为占位值）。
- 解释核心流程不需要的文档目录：`docs/legacy`、`docs/product`、`docs/audit`。
- `docs/design/*` **保留**：仓库治理测试（`backend/tests/test_doc_coverage.py`）会断言这些设计文档的存在与内容，删除会导致展示副本中的治理门禁无法运行。

## 公开前仍需确认

| 项目 | 位置 | 说明 |
| --- | --- | --- |
| 第三方 / 参考代码 | `backend/app/**`、`frontend/src/**` | 主要为自研，但部分结构（如 SQLModel CRUD 布局、FastAPI 路由布局）遵循公开框架惯例，尚未逐项审计许可证来源。 |
| 公司 / 客户资料 | 未复制 | 未复制任何客户文档；若后续文件引用内部主机名，请在公开前移除。 |
| 合成测试数据 | `backend/tests/test_security_*.py`、`test_materials_and_lineage.py`、`test_live_qr_login.py` | 含明显虚构的凭据、内部主机名与 Windows 示例路径，用于验证脱敏 / 防护逻辑；公开材料中不要打印其字面值。`test_live_qr_login.py` 与 `test_materials_and_lineage.py` 仍含类似姓名的字符串，公开前需确认为合成数据。 |
| 评分基准标签 | `backend/app/engine/rubrics/data/viral_rubric_benchmark_v1.json` | 43 条人工标注样本，**作者与授权未确认**，公开前需确认来源与发表权利。 |
| 截图权利 | 未复制原 `screenshots/` | 本仓库 `docs/images/` 为本次用合成数据真实运行后新采集。 |
| Skill 定义 | `skills/*/SKILL.md` | 自研 Skill 定义，需确认是否内嵌第三方片段。 |
| 公开许可证 | 无 | 未添加 LICENSE 文件，公开前需自行选择（例如 MIT）。 |

## 未验证项

- 本说明不主张「每一行都可公开」。任何远程发布前仍需人工复核。

## 演示运行补充（2026-10-15）

- `docs/images/01-03*.png` 来自运行中的本地 UI，使用合成输入 + 真实模型调用采集；不含凭据、真实用户记录、客户文档或微信日志。
- 演示使用独立 SQLite 文件（`demo-data/job-demo.db`），采集后已删除；未读写任何真实业务数据库。
- `docs/demo.md` 使用 `<repo-root>` 占位符，不含本地绝对路径。
- 扫描残留的 `sk-…` / `C:\Users\…` 命中位于 `backend/tests/test_security_*.py`，是**负向测试夹具**（用于验证脱敏代码的虚构字符串），不是真实凭据。
