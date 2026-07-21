# 研发设计文档：AI 黑话 Check Sheet（行业术语定时巡检清单）

> 版本：v0.1 (MVP)
> 作者：Software Architect
> 日期：2026-07-18
> 状态：Proposed

---

## 1. 背景与目标

### 1.1 问题陈述
AI 领域术语（黑话）更新极快：Agent、RAG、Tool Calling、Handoff、Orchestration、Multi-Agent…… 新人/业务同学很难系统掌握，且「今天刚学会、明天又出新词」。

菜鸟教程等站点会持续更新 AI 概念教程（如 https://www.runoob.com/ai-agent/ai-agent-tutorial.html）。我们希望把分散的术语源**定期**聚合成一份**可勾选的自测清单（Check Sheet）**，帮助个人或团队：

1. 系统性地列出 AI 黑话及其解释；
2. 标记「已掌握 / 待学」；
3. 定时巡检各术语源，**自动发现新增术语**并提示。

### 1.2 目标（MVP 范围）
- **G1 采集**：定时从配置化的术语源（首期 = 菜鸟教程 AI Agent 教程）抓取内容。
- **G2 归一**：解析、去重、分类，生成结构化术语库 `terms.json`。
- **G3 展示**：静态 Check Sheet 页面，支持分类、搜索、勾选、进度统计。
- **G4 巡检**：每次采集输出「新增术语」diff，触发通知（webhook / 日志）。
- **G5 零运维**：个人/小团队可用，部署成本低，架构可演进。

### 1.3 非目标（本期不做）
- 多用户账号体系 / 云端共享勾选状态（MVP 用 localStorage）。
- 术语自动 AI 释义生成（首期用人工维护的释义 + 页面证据）。
- 商业化 / 付费墙。

---

## 2. 领域建模（Bounded Context）

```
┌─────────────┐   采集    ┌──────────────┐   归一    ┌──────────────┐
│  术语源       │ ───────▶ │  采集上下文    │ ───────▶ │  术语库        │
│ Sources      │          │ Ingestion    │          │ Term Store   │
└─────────────┘          └──────────────┘          └──────┬───────┘
                                                              │ 读取
                                                              ▼
┌─────────────┐   调度    ┌──────────────┐          ┌──────────────┐
│  调度器       │ ───────▶ │ 巡检/Diff     │          │  展示上下文    │
│ Scheduler    │          │ Diff          │          │ Presentation │
└─────────────┘          └──────────────┘          └──────┬───────┘
                                                              │ 渲染
                                                              ▼
                                                    ┌──────────────┐
                                                    │  Check Sheet  │
                                                    │  (前端)        │
                                                    └──────────────┘
```

**限界上下文（Bounded Context）划分：**

| 上下文 | 职责 | 关键概念 |
|--------|------|----------|
| Term Source（术语源） | 定义可插拔的数据源 | `Source{id, name, url, parser, enabled}` |
| Ingestion（采集） | 抓取 + 解析 + 去重 | `RawPage`, `Extractor`, `DedupKey` |
| Term Store（术语库） | 维护权威术语表 | `Term{id, term, termZh, category, definition, source, firstSeen, lastSeen, status}` |
| Diff / Notify（巡检） | 比对历史、发现新词 | `DiffReport{added[], removed[], changed[]}`, `Notifier` |
| Presentation（展示） | 渲染 Check Sheet | `CheckState{termId, checked, checkedAt, note}` |

**聚合根（Aggregate Root）：** `Term`（术语库内以 `dedupKey` 去重，保证同一术语唯一）。
**领域事件：** `TermAdded`、`TermDeprecated`、`SourceFetchFailed`。

---

## 3. 架构方案与权衡

### 3.1 候选方案

| 方案 | 描述 | 优点 | 缺点 | 适用 |
|------|------|------|------|------|
| **A. 静态生成 + 定时爬虫（推荐）** | Python 爬虫定时抓取 → 生成 `terms.json` + 静态 `index.html` → 静态托管 | 零运维、零数据库、可逆、改造成本低 | 勾选状态只能存 localStorage（单人）；协作需升级 | 个人/小团队/内部知识库 |
| B. 全栈应用 | 后端 API + DB + 前端框架 + 调度（Celery/Airflow） | 多用户协作、勾选可共享、可扩展 | 运维重、MVP 过度设计 | 中大型团队/产品化 |
| C. 低代码 + 多维表 | 爬虫写飞书/Notion 多维表，前端用低代码读 | 业务同学友好 | 绑定平台、定制化弱 | 纯业务驱动、无研发 |

### 3.2 决策（见 ADR-001）
**采用方案 A（静态生成 + 定时爬虫）。**
理由：本期目标是「个人/小团队可用的定时术语巡检清单」。方案 A 把复杂度降到最低（无 DB、无后端、无容器），且数据采集层与展示层解耦——未来若需协作，只需把 `terms.json` 的写入替换为数据库 + 暴露 API，前端几乎不变（见演进路线 §7）。符合「可逆性优先」与「不为未知需求提前抽象」。

### 3.3 定时抓取的实现选型
- **托管场景（推荐）：** GitHub Actions `schedule` cron（如每周一 09:00 UTC）运行爬虫 → commit `terms.json` → 触发 Pages/静态部署。免费、无需常驻进程、可追溯每次 diff。
- **本地场景：** macOS `launchd` / Linux `cron` 调用 `python crawler/collect.py`，适合无 GitHub 的环境。
- **备选：** `APScheduler` 长驻脚本（仅当需要近实时或内网数据源时）。

---

## 4. 数据模型

### 4.1 `terms.json`（术语库，权威数据）
```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-07-18T09:00:00Z",
  "sources": [
    { "id": "runoob-ai-agent", "name": "菜鸟教程 AI Agent 教程",
      "url": "https://www.runoob.com/ai-agent/ai-agent-tutorial.html" }
  ],
  "categories": ["Agent 基础", "规划 Planning", "工具 Tool", "记忆 Memory",
                  "多智能体 Multi-Agent", "检索增强 RAG", "框架 Frameworks"],
  "terms": [
    {
      "id": "agent",
      "term": "AI Agent",
      "termZh": "智能体",
      "category": "Agent 基础",
      "definition": "能感知环境、决策并执行动作以达成目标的智能程序。Agent = LLM(大脑)+Planning+Tool use+Memory。",
      "source": "runoob-ai-agent",
      "sourceUrl": "https://www.runoob.com/ai-agent/ai-agent-tutorial.html",
      "firstSeen": "2026-07-18",
      "lastSeen": "2026-07-18",
      "status": "active"
    }
  ]
}
```

### 4.2 前端勾选状态（用户态，不入库）
浏览器 `localStorage` 键 `ai-jargon-checks`，结构：
```json
{ "agent": { "checked": true, "checkedAt": "2026-07-20T10:00:00Z", "note": "理解了 Planning 闭环" } }
```
> 设计取舍（见 ADR-002）：勾选状态不放后端，避免引入账号体系；若未来需要跨设备/多人共享，再加一层可选同步。

### 4.3 去重与 diff 策略
- **dedupKey**：`term` 小写去空格 + 归一化（如 `tool calling` ≡ `tool-calling`）。
- **新增判定**：本次解析到的 term 在 `terms.json` 中不存在 → `TermAdded`。
- **失效判定**：上次存在、本次源中不再出现且超过 `graceRuns` 次 → 标记 `deprecated`（不直接删，保留历史）。
- **候选新词**：页面标题/列表项命中但不在人工释义库 → 进 `candidates.json` 供人工 review。

---

## 5. 技术方案

### 5.1 采集层（Python）
- 依赖：`requests`（HTTP）+ `beautifulsoup4`（解析）。
- 配置化源：`crawler/sources.yaml`，每个源含 `parser` 类型（`runoob-ai-agent` 等）。
- 解析器职责：取页面标题/章节/列表 → 与人工释义库（`crawler/glossary.yaml`）交叉印证 → 输出 terms。
- 健壮性：超时、重试（3 次指数退避）、失败发 `SourceFetchFailed` 事件并继续其它源。

### 5.2 展示层（静态前端）
- 单文件 `public/index.html`（原生 HTML + CSS + JS，**无构建步骤**），最大化简部署摩擦。
- 功能：分类树、搜索过滤、勾选（持久化到 localStorage）、进度条（已掌握 / 总数）、「导出我的黑话图谱（JSON/Markdown）」。
- 数据加载：`fetch('./terms.json')`，本地直接打开文件时需起一个静态服务器（已提供 `npm/python -m http.server` 说明）。

### 5.3 调度层
- `.github/workflows/crawl.yml`：`on.schedule` cron + 手动 `workflow_dispatch`。
- 步骤：checkout → setup-python → install → `python crawler/collect.py` → `git commit` + push → 部署。
- 通知：diff 非空时调用 `Notifier`（首期支持 webhook / GitHub Issue 自动建单；飞书/邮件可后续接）。

---

## 6. 实现步骤（Roadmap）

| # | 步骤 | 产出 | 备注 |
|---|------|------|------|
| 1 | 初始化项目结构 | `ai-jargon-checklist/` 目录树 | 已完成骨架 |
| 2 | 编写术语源配置 `sources.yaml` | 可插拔源列表 | 首期 1 个源 |
| 3 | 编写人工释义库 `glossary.yaml` | 已知术语 + 释义 + 分类 | 种子数据 |
| 4 | 编写爬虫 `collect.py`（抓取/解析/去重/diff） | `terms.json` + `diff.json` | 核心 |
| 5 | 编写静态 Check Sheet `public/index.html` | 可勾选前端 | 无构建 |
| 6 | 配置定时任务 `crawl.yml` | 自动巡检 | 每周 |
| 7 | 配置部署（GitHub Pages / CloudStudio 静态） | 在线访问 | 零成本 |
| 8 | 配置通知（webhook / Issue） | 新术语提醒 | 可演进 |
| 9 | 写 README + ADR | 文档 | 见 `docs/` |

---

## 7. 演进路线（不重写）
1. **单人 → 多人**：把 `terms.json` 读写换为 SQLite/Postgres + 轻量 API；前端勾选状态上传到 `/api/checks`。
2. **人工释义 → 半自动**：新增术语进 `candidates.json` 后，用 LLM 生成初稿释义，人工确认入库。
3. **单源 → 多源**：在 `sources.yaml` 增加 OpenAI Glossary、HuggingFace 术语、维基百科 AI 词条等，parser 插件化。
4. **静态 → 可观测**：加采集成功率、新增速率等 metric，进 Grafana。

---

## 8. 风险与缓解
| 风险 | 影响 | 缓解 |
|------|------|------|
| 源站改版导致解析失效 | 抓取为空 | parser 隔离 + 解析失败告警 + 保留上一版 `terms.json` |
| 术语爆炸式增长 | 清单臃肿 | 分类 + 必学/进阶标签 + 搜索 |
| 前端 localStorage 被清 | 勾选丢失 | 提供「导出/导入」JSON |
| 定时任务被平台限流 | 更新滞后 | 支持手动 `workflow_dispatch` 触发 |

---

## 9. 关键决策记录（ADR 索引）
- **ADR-001**：采用「静态生成 + 定时爬虫」架构（而非全栈）。理由：零运维、可逆、MVP 最简。
- **ADR-002**：勾选状态存 `localStorage` 而非后端。理由：避免账号体系，单人场景足够。
- **ADR-003**：术语源配置化（`sources.yaml` 可插拔）。理由：未来可加多源，parser 插件化。

详见 `docs/ADR/`。
