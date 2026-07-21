# ADR-003: 术语源配置化（sources.yaml 可插拔）

## Status
Accepted

## Context
首期只有一个术语源（菜鸟教程）。但「定时获取最新行业术语」本质要求多源、可扩展，否则很快过时。

## Decision
术语源在 `crawler/sources.yaml` 中声明（id/name/url/parser/enabled），`collect.py` 通过 `PARSERS` 注册表按 `parser` 类型分派解析函数。新增源 = 追加配置 + 实现解析器。

## Consequences
- **更易**：加新源（OpenAI Glossary、HuggingFace 术语、维基百科等）不改主流程。
- **更易测试**：单源失败不影响其它源（隔离 + 失败继续）。
- **更难**：每个新源需写对应解析器（不同站点结构不同），无法完全零成本。
- **放弃**：不追求「通用万能解析器」——那会引入过度抽象，违背 KISS。

## 复核触发条件
当源站大规模改版导致解析失效时，应优先修复对应 parser 并加解析失败告警。
