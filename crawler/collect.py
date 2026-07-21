#!/usr/bin/env python3
"""
AI 黑话 Check Sheet —— 术语采集器
==================================
从 sources.yaml 配置化的术语源抓取内容，与 glossary.yaml 人工释义库合并，
生成 data/terms.json（权威术语库）。同时：
  - 从源页表格提取真实框架/项目词条（如菜鸟教程的框架列表）
  - 把页面出现但库里没有的词放进 data/candidates.json 供人工 review
  - 输出 data/diff.json（本次新增/失效/变更），供通知使用

运行:
    python crawler/collect.py
"""
from __future__ import annotations
import json
import re
import sys
import datetime
from pathlib import Path

import yaml
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CRAWLER = Path(__file__).resolve().parent
DATA = ROOT / "data"
SOURCES = CRAWLER / "sources.yaml"
GLOSSARY = CRAWLER / "glossary.yaml"

DATA.mkdir(parents=True, exist_ok=True)
TODAY = datetime.date.today().isoformat()


# ---------- 工具函数 ----------
def norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def log(msg: str) -> None:
    print(f"[collect] {msg}", flush=True)


def fetch(url: str, timeout: int = 20) -> str:
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (AI-Jargon-Checklist bot)"},
            )
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            last_err = e
            log(f"fetch 失败({attempt+1}/3): {url} -> {e}")
    raise RuntimeError(f"无法抓取 {url}: {last_err}")


# ---------- 解析器 ----------
def parse_runoob_ai_agent(html: str, source: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    # 1) 从表格提取框架/项目词条（项目名 + 定位说明）
    frameworks = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for tr in rows[1:]:
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            a = tds[0].find("a")
            name = (a.get_text(strip=True) if a else tds[0].get_text(strip=True))
            desc = tds[1].get_text(" ", strip=True)
            url = a.get("href") if (a and a.get("href")) else ""
            if name:
                frameworks.append({"name": name, "desc": desc, "url": url})

    # 2) 候选标题（页面小节，可能含新术语）
    headings = []
    for h in soup.find_all(["h2", "h3"]):
        t = h.get_text(" ", strip=True)
        if t and 2 <= len(t) <= 40:
            headings.append(t)

    return {"frameworks": frameworks, "headings": headings, "text": text}


PARSERS = {"runoob_ai_agent": parse_runoob_ai_agent}


# ---------- 主流程 ----------
def main() -> int:
    sources = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))["sources"]
    glossary = yaml.safe_load(GLOSSARY.read_text(encoding="utf-8"))["terms"]

    # 构建术语字典（以 norm_key 去重）
    terms: dict[str, dict] = {}
    order: list[str] = []

    def add_term(term: str, term_zh: str, category: str, definition: str,
                 source_id: str, source_url: str, status: str = "active") -> None:
        key = norm_key(term)
        if key in terms:
            return
        terms[key] = {
            "id": key,
            "term": term,
            "termZh": term_zh,
            "category": category,
            "definition": definition,
            "source": source_id,
            "sourceUrl": source_url,
            "firstSeen": TODAY,
            "lastSeen": TODAY,
            "status": status,
        }
        order.append(key)

    # 1) 先放入人工释义库（保证核心术语始终存在）
    for g in glossary:
        add_term(g["term"], g.get("termZh", ""), g["category"],
                 g["definition"], "glossary-seed", "", "active")

    candidates: list[dict] = []
    seen_headings: set[str] = set()

    # 2) 遍历每个源
    for src in sources:
        if not src.get("enabled", True):
            continue
        log(f"处理源: {src['name']} ({src['url']})")
        try:
            html = fetch(src["url"])
        except Exception as e:  # noqa: BLE001
            log(f"源抓取失败，跳过: {e}")
            continue
        parser = PARSERS.get(src["parser"])
        if parser is None:
            log(f"无对应 parser: {src['parser']}，跳过")
            continue
        parsed = parser(html, src)
        page_text = parsed["text"]

        # 2a) 标记 glossary 术语是否在本页出现（作为证据）
        for key in order:
            t = terms[key]
            if t["source"] != "glossary-seed":
                continue
            hit = (t["term"].lower() in page_text.lower()) or \
                  (t.get("termZh") and t["termZh"] in page_text)
            if hit:
                t["source"] = src["id"]
                t["sourceUrl"] = src["url"]
                t["lastSeen"] = TODAY

        # 2b) 框架/项目词条（真实提取自页面表格）
        # 过滤：只保留「含英文字母 + 有真实链接」的项目名，剔除过短/泛化词与空值，
        # 让术语库聚焦真正的 AI 黑话（多为英文术语）。
        GENERIC = {"ai", "agent", "llm", "rag"}
        for fw in parsed["frameworks"]:
            name = fw["name"]
            if not name:
                continue
            key = norm_key(name)
            if len(key) < 3 or not re.search(r"[a-z]", key):
                continue
            if key in GENERIC:
                continue
            if not fw.get("url"):
                continue
            if key in terms:
                continue
            url = fw["url"] or src["url"]
            terms[key] = {
                "id": key,
                "term": fw["name"],
                "termZh": "",
                "category": "框架 Frameworks",
                "definition": fw["desc"] or "（待补充释义）",
                "source": src["id"],
                "sourceUrl": url,
                "firstSeen": TODAY,
                "lastSeen": TODAY,
                "status": "active",
            }
            order.append(key)

        # 2c) 候选新词（页面标题不在库里）
        for h in parsed["headings"]:
            key = norm_key(h)
            if key in seen_headings:
                continue
            seen_headings.add(key)
            if key in terms:
                continue
            candidates.append({
                "term": h,
                "source": src["id"],
                "sourceUrl": src["url"],
                "foundAt": TODAY,
                "note": "页面小节标题，待人工确认是否纳入术语库",
            })

    # 3) 与历史 terms.json 做 diff
    prev_ids: set[str] = set()
    prev_map: dict[str, dict] = {}
    prev_path = DATA / "terms.json"
    if prev_path.exists():
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
        for t in prev.get("terms", []):
            prev_ids.add(t["id"])
            prev_map[t["id"]] = t

    new_terms = [terms[k] for k in order]
    new_ids = {t["id"] for t in new_terms}

    added, removed, changed = [], [], []
    for t in new_terms:
        pid = t["id"]
        if pid not in prev_ids:
            added.append(pid)
        else:
            old = prev_map[pid]
            # 保留历史 firstSeen
            t["firstSeen"] = old.get("firstSeen", TODAY)
            if (old.get("definition") != t["definition"]) or \
               (old.get("category") != t["category"]):
                changed.append(pid)
    for pid in prev_ids - new_ids:
        removed.append(pid)

    # 4) 写出数据
    categories = sorted({t["category"] for t in new_terms})
    out = {
        "schemaVersion": 1,
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sources": [{"id": s["id"], "name": s["name"], "url": s["url"]} for s in sources],
        "categories": categories,
        "terms": new_terms,
    }
    prev_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    cand_path = DATA / "candidates.json"
    cand_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")

    diff = {
        "generatedAt": out["generatedAt"],
        "added": added,
        "removed": removed,
        "changed": changed,
        "candidateCount": len(candidates),
        "totalTerms": len(new_terms),
    }
    (DATA / "diff.json").write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"术语总数: {len(new_terms)} | 新增: {len(added)} | 失效: {len(removed)} | 变更: {len(changed)} | 候选: {len(candidates)}")
    if added:
        log("新增术语: " + ", ".join(added))
    return 0


if __name__ == "__main__":
    sys.exit(main())
