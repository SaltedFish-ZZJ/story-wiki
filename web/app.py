"""
Story Wiki Web UI — FastAPI 后端。
直接读取 Obsidian .md 文件，提供 JSON API 给前端。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# ── 路径配置 ──────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
# 默认读取本地生成目录，也支持 Obsidian Vault
OUTPUT_DIR = BASE_DIR / "data" / "output"

# ── .md 文件解析器 ────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^|\]]+?)(?:\|([^\]]+?))?\]\]")


def _parse_fm(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _extract_section(text: str, header: str) -> str:
    pat = re.compile(
        rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=^##\s|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pat.search(text)
    return m.group(1).strip() if m else ""


def _parse_section_links(text: str, header: str) -> list[dict]:
    section = _extract_section(text, header)
    if not section:
        return []
    results = []
    for line in section.split("\n"):
        line = line.strip().lstrip("- ")
        m = _WIKILINK_RE.search(line)
        if m:
            path = m.group(1)
            display = m.group(2) or path.rsplit("/", 1)[-1]
            after = _WIKILINK_RE.sub("", line).strip().lstrip("—- ").strip()
            results.append({"path": path, "name": display, "description": after})
    return results


def _body_summary(text: str) -> str:
    """提取 frontmatter 之后、第一个 ## 之前的正文摘要。"""
    without_fm = _FRONTMATTER_RE.sub("", text, count=1)
    lines = []
    for line in without_fm.split("\n"):
        s = line.strip()
        if s.startswith("##"):
            break
        if s and not s.startswith("#") and not s.startswith(">") and "---" not in s:
            lines.append(s)
    return " ".join(lines)[:300]


def _extract_name(text: str, fallback: str) -> str:
    """从 .md 正文中提取 # 标题作为名称，跳过 frontmatter。"""
    # 跳过 frontmatter
    without_fm = _FRONTMATTER_RE.sub("", text, count=1)
    for line in without_fm.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _read_md(filepath: Path) -> str:
    try:
        return filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ── 作品目录发现 ──────────────────────────────────────────────


def _find_book_dir(title: str) -> Path | None:
    """在 OUTPUT_DIR 下查找作品目录。支持 title/title/ 和 title/ 两种结构。"""
    candidate = OUTPUT_DIR / title / title
    if (candidate / "_index.md").exists():
        return candidate
    candidate2 = OUTPUT_DIR / title
    if (candidate2 / "_index.md").exists():
        return candidate2
    return None


# ── 缓存 ─────────────────────────────────────────────────────

_cache: dict[str, dict] = {}


def _load_book(title: str) -> dict:
    if title in _cache:
        return _cache[title]

    book_dir = _find_book_dir(title)
    if not book_dir:
        raise HTTPException(404, f"作品 '{title}' 不存在")

    characters, events, settings = [], [], []

    for md_file in book_dir.rglob("*.md"):
        if md_file.name.startswith("_") or md_file.name == "timeline.md":
            continue
        rel = md_file.relative_to(book_dir)
        if not rel.parts:
            continue
        category = rel.parts[0]
        text = _read_md(md_file)
        if not text:
            continue
        fm = _parse_fm(text)

        if category == "characters" and fm.get("type") == "character":
            name = _extract_name(text, md_file.stem)
            status_m = re.search(r"[🟢⚫🔴🟡⚪]\s*(\S+)", text)
            characters.append({
                "name": name,
                "status": status_m.group(1) if status_m else "未知",
                "gender": fm.get("gender", "未知"),
                "faction": fm.get("faction", ""),
                "role_tags": fm.get("role_tags", []),
                "color": fm.get("color", "character-minor"),
                "identity": _extract_section(text, "身份"),
                "personality": _extract_section(text, "性格"),
                "relationships": _parse_section_links(text, "人际关系"),
                "related_settings": _parse_section_links(text, "关联设定"),
                "events": _parse_section_links(text, "参与事件"),
                "quotes": _extract_section(text, "经典语录"),
                "subfolder": md_file.parent.name,
            })

        elif category == "events" and fm.get("type") == "event":
            name = _extract_name(text, md_file.stem)
            events.append({
                "name": name,
                "time": fm.get("time", ""),
                "chapter": fm.get("chapter", ""),
                "importance": fm.get("importance", "中"),
                "color": fm.get("color", "event-normal"),
                "summary": _body_summary(text),
                "participants": _parse_section_links(text, "参与人物"),
                "location": _parse_section_links(text, "发生地点"),
                "cause": _parse_section_links(text, "前置事件"),
                "effect": _parse_section_links(text, "后续影响"),
                "subfolder": md_file.parent.name,
            })

        elif category == "settings" and fm.get("type") == "setting":
            name_line = text.split("\n")[0].lstrip("# ").strip()
            name = name_line if name_line else md_file.stem
            settings.append({
                "name": name,
                "setting_type": fm.get("setting_type", "概念"),
                "description": _extract_section(text, "描述")[:200],
                "characters": _parse_section_links(text, "出现人物"),
                "events": _parse_section_links(text, "关联事件"),
                "subfolder": md_file.parent.name,
            })

    data = {"characters": characters, "events": events, "settings": settings}
    _cache[title] = data
    return data


# ── FastAPI 应用 ──────────────────────────────────────────────

app = FastAPI(title="Story Wiki Web UI")

# 挂载静态文件
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


@app.get("/api/books")
async def api_books():
    """列出所有作品。"""
    books = []
    if not OUTPUT_DIR.exists():
        return {"books": []}
    for child in sorted(OUTPUT_DIR.iterdir()):
        if child.is_dir():
            book_dir = _find_book_dir(child.name)
            if book_dir:
                books.append({"title": child.name})
    return {"books": books}


@app.get("/api/books/{title}/overview")
async def api_overview(title: str):
    """作品概览：统计 + 核心人物 + 摘要。"""
    data = _load_book(title)
    index_file = _find_book_dir(title) / "_index.md"
    index_text = _read_md(index_file) if index_file else ""
    summary = ""
    if index_text:
        # 提取 blockquote 摘要
        for line in index_text.split("\n"):
            line = line.strip()
            if line.startswith("> "):
                summary = line[2:]
                break

    # 核心人物（role_tags 含"主角"或"男主/女主"）
    top_chars = [
        c for c in data["characters"]
        if any(t in (c.get("role_tags") or []) for t in ["主角", "男主", "女主"])
    ][:12]

    # 按角色分组统计
    groups = {"核心人物": 0, "重要配角": 0, "其他人物": 0}
    for c in data["characters"]:
        tags = set(c.get("role_tags") or [])
        if "主角" in tags or "男主" in tags or "女主" in tags:
            groups["核心人物"] += 1
        elif tags - {"路人"}:
            groups["重要配角"] += 1
        else:
            groups["其他人物"] += 1

    return {
        "title": title,
        "summary": summary,
        "stats": {
            "characters": len(data["characters"]),
            "events": len(data["events"]),
            "settings": len(data["settings"]),
        },
        "character_groups": groups,
        "top_characters": [
            {"name": c["name"], "identity": c["identity"], "role_tags": c["role_tags"], "color": c["color"]}
            for c in top_chars
        ],
    }


@app.get("/api/books/{title}/characters")
async def api_characters(title: str, q: str = ""):
    """人物列表，支持搜索。"""
    data = _load_book(title)
    chars = data["characters"]
    if q:
        q_lower = q.lower()
        chars = [
            c for c in chars
            if q_lower in c["name"].lower()
            or q_lower in (c.get("identity") or "").lower()
            or any(q_lower in t.lower() for t in (c.get("role_tags") or []))
        ]
    # 按角色分组
    result = {"核心人物": [], "重要配角": [], "其他人物": []}
    for c in chars:
        tags = set(c.get("role_tags") or [])
        if "主角" in tags or "男主" in tags or "女主" in tags:
            result["核心人物"].append(c)
        elif tags - {"路人"}:
            result["重要配角"].append(c)
        else:
            result["其他人物"].append(c)
    return {"characters": result, "total": len(chars)}


@app.get("/api/books/{title}/characters/{name}")
async def api_character_detail(title: str, name: str):
    """单个人物详情。"""
    data = _load_book(title)
    for c in data["characters"]:
        if c["name"] == name:
            return c
    raise HTTPException(404, f"人物 '{name}' 不存在")


@app.get("/api/books/{title}/graph")
async def api_graph(title: str, depth: int = 1, center: str = ""):
    """关系图数据：nodes + edges。"""
    data = _load_book(title)

    # 角色标签 → 颜色映射（苹果色系）
    color_map = {
        "character-protagonist": "#ff3b30",
        "character-supporting": "#007aff",
        "character-minor": "#8e8e93",
    }

    nodes = []
    node_set = set()
    edges = []
    edge_set = set()

    def add_node(char: dict):
        if char["name"] in node_set:
            return
        node_set.add(char["name"])
        nodes.append({
            "id": char["name"],
            "symbolSize": 20 if "主角" in (char.get("role_tags") or []) else 12,
            "itemStyle": {"color": color_map.get(char["color"], "#8e8e93")},
            "role_tags": char.get("role_tags", []),
            "subfolder": char.get("subfolder", ""),
        })

    # 如果指定了 center，只显示该人物的邻居
    if center:
        center_char = None
        for c in data["characters"]:
            if c["name"] == center:
                center_char = c
                break
        if center_char:
            add_node(center_char)
            neighbor_names = set()
            for r in center_char.get("relationships", []):
                neighbor_names.add(r["name"])
            for nc in data["characters"]:
                if nc["name"] in neighbor_names:
                    add_node(nc)
                    ekey = (center_char["name"], nc["name"])
                    if ekey not in edge_set:
                        edge_set.add(ekey)
                        rel_desc = ""
                        for r in center_char["relationships"]:
                            if r["name"] == nc["name"]:
                                rel_desc = r.get("description", "")
                                break
                        edges.append({
                            "source": center_char["name"],
                            "target": nc["name"],
                            "label": rel_desc[:10],
                        })
    else:
        # 全量：只显示有 ≥1 条关系的人物
        char_names = {c["name"] for c in data["characters"]}
        rel_count: dict[str, int] = {}
        for c in data["characters"]:
            for r in c.get("relationships", []):
                if r["name"] in char_names:
                    rel_count[c["name"]] = rel_count.get(c["name"], 0) + 1
                    rel_count[r["name"]] = rel_count.get(r["name"], 0) + 1

        for c in data["characters"]:
            if rel_count.get(c["name"], 0) >= 1:
                add_node(c)

        for c in data["characters"]:
            for r in c.get("relationships", []):
                if r["name"] in node_set and c["name"] in node_set:
                    ekey = tuple(sorted([c["name"], r["name"]]))
                    if ekey not in edge_set:
                        edge_set.add(ekey)
                        edges.append({
                            "source": c["name"],
                            "target": r["name"],
                            "label": r.get("description", "")[:10],
                        })

    return {"nodes": nodes, "edges": edges}


@app.get("/api/books/{title}/timeline")
async def api_timeline(title: str, importance: str = "", character: str = ""):
    """时间线数据。"""
    data = _load_book(title)
    events = data["events"]

    if importance:
        events = [e for e in events if e["importance"] == importance]

    if character:
        events = [
            e for e in events
            if any(p["name"] == character for p in e.get("participants", []))
        ]

    # 按 importance 排序（高 > 中 > 低）
    imp_order = {"高": 0, "中": 1, "低": 2}
    events.sort(key=lambda e: imp_order.get(e["importance"], 1))

    return {"events": events, "total": len(events)}
