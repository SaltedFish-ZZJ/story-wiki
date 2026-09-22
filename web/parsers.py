"""Obsidian .md 文件解析器 — 为 Web UI 提供结构化数据。"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


# ── frontmatter ───────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^|\]]+?)(?:\|([^\]]+?))?\]\]")
_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _parse_frontmatter(text: str) -> dict:
    """解析 YAML frontmatter。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _extract_wikilinks(text: str) -> list[dict]:
    """提取所有 wikilink，返回 [{path, display}]。"""
    return [
        {"path": m.group(1), "display": m.group(2) or m.group(1).rsplit("/", 1)[-1]}
        for m in _WIKILINK_RE.finditer(text)
    ]


def _extract_section(text: str, header: str) -> str:
    """提取某个 ## section 的正文内容（到下一个 ## 或文件末尾）。"""
    pattern = re.compile(
        rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=^##\s|\Z)", re.DOTALL | re.MULTILINE
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _parse_section_links(text: str, header: str) -> list[dict]:
    """提取某个 section 下的 wikilink 列表，带行内描述。"""
    section = _extract_section(text, header)
    if not section:
        return []
    results = []
    for line in section.split("\n"):
        line = line.strip().lstrip("- ")
        m = _WIKILINK_RE.search(line)
        if m:
            path = m.group(1)
            display = m.group(2) or path.rplit("/", 1)[-1]
            # 提取 wikilink 后面的描述
            after = _WIKILINK_RE.sub("", line).strip().lstrip("—- ").strip()
            results.append({"path": path, "display": display, "description": after})
    return results


def _status_from_line(text: str) -> str:
    """从状态栏行提取状态（🟢 活跃 / ⚫ 已故 等）。"""
    m = re.search(r"[🟢⚫🔴🟡⚪]\s*(\S+)", text)
    return m.group(1) if m else "未知"


# ── 公开 API ──────────────────────────────────────────────────

def parse_character(filepath: Path) -> dict | None:
    """解析人物卡片 .md，返回结构化 dict。"""
    try:
        text = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    fm = _parse_frontmatter(text)
    if fm.get("type") != "character":
        return None

    name = text.split("\n")[0].lstrip("# ").strip() if "#" in text else filepath.stem
    status = _status_from_line(text)

    return {
        "name": name,
        "status": status,
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
        "subfolder": filepath.parent.name,
    }


def parse_event(filepath: Path) -> dict | None:
    """解析事件卡片 .md。"""
    try:
        text = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    fm = _parse_frontmatter(text)
    if fm.get("type") != "event":
        return None

    name = text.split("\n")[0].lstrip("# ").strip() if "#" in text else filepath.stem
    body_lines = text.split("\n")
    summary = ""
    for line in body_lines:
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith(">") and not line.startswith("-") and "---" not in line and not line.startswith("type:") and not line.startswith("color:") and not line.startswith("source:") and not line.startswith("origin:") and not line.startswith("time:") and not line.startswith("chapter:") and not line.startswith("importance:") and not line.startswith("tags:") and not line.startswith("created:"):
            summary = line
            break

    return {
        "name": name,
        "time": fm.get("time", ""),
        "chapter": fm.get("chapter", ""),
        "importance": fm.get("importance", "中"),
        "color": fm.get("color", "event-normal"),
        "summary": summary[:200],
        "participants": _parse_section_links(text, "参与人物"),
        "location": _parse_section_links(text, "发生地点"),
        "cause": _parse_section_links(text, "前置事件"),
        "effect": _parse_section_links(text, "后续影响"),
        "subfolder": filepath.parent.name,
    }


def parse_setting(filepath: Path) -> dict | None:
    """解析设定卡片 .md。"""
    try:
        text = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    fm = _parse_frontmatter(text)
    if fm.get("type") != "setting":
        return None

    name = text.split("\n")[0].lstrip("# ").strip() if "#" in text else filepath.stem
    desc = _extract_section(text, "描述")

    return {
        "name": name,
        "setting_type": fm.get("setting_type", "概念"),
        "description": desc[:200],
        "characters": _parse_section_links(text, "出现人物"),
        "events": _parse_section_links(text, "关联事件"),
        "subfolder": filepath.parent.name,
    }


def parse_book_dir(book_dir: Path) -> dict:
    """扫描整个作品目录，返回所有解析结果。"""
    characters: list[dict] = []
    events: list[dict] = []
    settings: list[dict] = []

    for md_file in book_dir.rglob("*.md"):
        if md_file.name.startswith("_") or md_file.name == "timeline.md":
            continue
        rel = md_file.relative_to(book_dir)
        parts = rel.parts
        if not parts:
            continue
        category = parts[0]

        if category == "characters":
            c = parse_character(md_file)
            if c:
                characters.append(c)
        elif category == "events":
            e = parse_event(md_file)
            if e:
                events.append(e)
        elif category == "settings":
            s = parse_setting(md_file)
            if s:
                settings.append(s)

    return {"characters": characters, "events": events, "settings": settings}


def list_books(output_dir: Path) -> list[dict]:
    """列出 output_dir 下所有作品。"""
    books = []
    if not output_dir.exists():
        return books
    for child in sorted(output_dir.iterdir()):
        if child.is_dir():
            # 可能是 output_dir/title/title/ 或 output_dir/title/
            inner = child / child.name
            book_dir = inner if inner.exists() and inner.is_dir() else child
            index_file = book_dir / "_index.md"
            if index_file.exists():
                books.append({
                    "title": child.name,
                    "path": str(book_dir),
                })
    return books
