# AI 黑话 Check Sheet

访问地址：https://lq920320.github.io/ai-jargon-checklist/ 

![页面截图](https://github.com/user-attachments/assets/c6dd6eed-1561-41db-a383-dcd276c3f70f)

一个**定时巡检行业术语、可勾选自测**的 AI 黑话清单项目。

- 🕸️ 定时从公开术语源（首期：菜鸟教程 AI Agent 教程）抓取最新概念
- 📚 自动去重、分类，生成结构化术语库 `data/terms.json`
- ✅ 静态 Check Sheet 页面：分类、搜索、勾选、进度统计、导出
- 🔔 每次采集输出 diff，可接通知（新术语提醒）

## 目录结构
```
ai-jargon-checklist/
├── crawler/
│   ├── collect.py        # 采集器：抓取 + 解析 + 去重 + diff
│   ├── sources.yaml      # 术语源配置（可插拔）
│   ├── glossary.yaml     # 人工维护的核心术语释义（种子）
│   └── requirements.txt
├── data/
│   ├── terms.json        # 权威术语库（自动生成）
│   ├── candidates.json   # 候选新词（待人工确认）
│   └── diff.json         # 本次新增/失效/变更
├── public/
│   └── index.html        # 静态 Check Sheet 前端（无构建）
├── docs/
│   ├── 研发设计文档-AI黑话CheckSheet.md
│   └── ADR/
└── .github/workflows/crawl.yml   # 定时任务 + 部署
```

## 本地运行
```bash
# 1) 建环境
python -m venv .venv && source .venv/bin/activate
pip install -r crawler/requirements.txt

# 2) 抓取并生成术语库
python crawler/collect.py

# 3) 本地预览 Check Sheet
cp data/terms.json public/terms.json
cd public && python -m http.server 8080
# 浏览器打开 http://localhost:8080
```

## 定时更新
- **GitHub**：推到仓库后，`crawl.yml` 每周一自动抓取并更新 Pages。
- **本地**：用 `cron` / `launchd` 调用 `python crawler/collect.py` 即可。

## 扩展新术语源
编辑 `crawler/sources.yaml` 追加一项（含 `parser` 类型），在 `collect.py` 的 `PARSERS` 注册对应解析函数即可。多源、多语言可平滑扩展。

详见 [`docs/研发设计文档-AI黑话CheckSheet.md`](docs/研发设计文档-AI黑话CheckSheet.md)。
