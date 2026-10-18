"""
Story Wiki MCP 读侧 Server。

把小说知识库（data/output/ 下的卡片）以 MCP 工具形式暴露给任意 MCP 客户端
（Trae、Claude Desktop、WorkBuddy 等），全部为只读查询，不触发 LLM 调用。

启动方式（stdio 传输，客户端在 mcp 配置里指向本文件）：
    python -m web.mcp_server

复用 web.app 的解析层（_load_book 带内存缓存）与 src.db 的 FTS5 搜索。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# 保证 `python -m web.mcp_server` 能找到项目根下的 src / web 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web.app import (  # noqa: E402
    HTTPException,
    _load_book,
    api_graph,
    api_overview,
    api_timeline,
)
from src.db import connect, search_entities  # noqa: E402
from src.db import DEFAULT_DB_PATH  # noqa: E402

mcp = FastMCP(
    "story-wiki",
    instructions=(
        "小说知识库只读查询：列出作品、查人物/事件/设定卡片、"
        "取章节时间线与关系图谱、全文搜索。"
        "所有工具的第一个参数 book 是作品名（先用 list_books 获取）。"
    ),
)


def _ok(data) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _err(e: Exception) -> str:
    if isinstance(e, HTTPException):
        return _ok({"error": e.detail})
    return _ok({"error": f"{type(e).__name__}: {e}"})


def _find(items: list[dict], name: str) -> dict | None:
    for it in items:
        if it.get("name") == name:
            return it
    return None


@mcp.tool()
async def list_books() -> str:
    """列出知识库中的全部作品及各类实体数量。"""
    try:
        from web.app import OUTPUT_DIR

        if not OUTPUT_DIR.exists():
            return _ok({"books": []})
        books = []
        for child in sorted(OUTPUT_DIR.iterdir()):
            if not child.is_dir():
                continue
            try:
                d = _load_book(child.name)
            except HTTPException:
                continue
            books.append({
                "title": child.name,
                "characters": len(d["characters"]),
                "events": len(d["events"]),
                "settings": len(d["settings"]),
            })
        return _ok({"books": books})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_overview(book: str) -> str:
    """作品概览：摘要、实体统计、人物分组与核心人物名单。"""
    try:
        return _ok(await api_overview(book))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def search(query: str, kind: str = "", limit: int = 20) -> str:
    """跨作品全文搜索实体。

    Args:
        query: 关键词（支持中文子串，如「少安」）
        kind: 可选过滤 character / event / setting，留空查全部
        limit: 返回条数上限，默认 20
    """
    try:
        if not DEFAULT_DB_PATH.exists():
            return _ok({"error": f"索引不存在（{DEFAULT_DB_PATH}），请先运行一次分析或重建索引"})
        with connect() as conn:
            rows = search_entities(conn, query, kind=kind or None, limit=limit)
        return _ok({"results": [
            {"kind": r.get("kind"), "name": r.get("name"), "book": r.get("book"),
             "summary": (r.get("summary") or "")[:120]}
            for r in rows
        ]})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def list_characters(book: str, q: str = "") -> str:
    """人物名单（按核心/重要配角/其他分组），q 可按名字或身份过滤。

    Args:
        book: 作品名
        q: 过滤关键词，留空返回全部
    """
    try:
        d = _load_book(book)
        chars = d["characters"]
        if q:
            ql = q.lower()
            chars = [c for c in chars if ql in c["name"].lower()
                     or ql in (c.get("identity") or "").lower()]
        chars.sort(key=lambda c: 0 if "主角" in (c.get("role_tags") or [])
                   or "男主" in (c.get("role_tags") or [])
                   or "女主" in (c.get("role_tags") or []) else 1)
        return _ok({"total": len(chars), "characters": [
            {"name": c["name"], "status": c.get("status"), "gender": c.get("gender"),
             "identity": (c.get("identity") or "")[:80], "role_tags": c.get("role_tags")}
            for c in chars
        ]})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_character(book: str, name: str) -> str:
    """人物卡详情：身份、性格、人际关系、参与事件、关联设定、语录。

    Args:
        book: 作品名
        name: 人物名（精确匹配，先 list_characters 获取）
    """
    try:
        c = _find(_load_book(book)["characters"], name)
        if not c:
            return _ok({"error": f"人物 '{name}' 不存在于《{book}》"})
        return _ok(c)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_event(book: str, name: str) -> str:
    """事件卡详情：时间、章节、重要度、参与人物、因果链。

    Args:
        book: 作品名
        name: 事件名（精确匹配）
    """
    try:
        e = _find(_load_book(book)["events"], name)
        if not e:
            return _ok({"error": f"事件 '{name}' 不存在于《{book}》"})
        return _ok(e)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_setting(book: str, name: str) -> str:
    """设定卡详情：类型、描述、关联人物与事件。

    Args:
        book: 作品名
        name: 设定名（精确匹配）
    """
    try:
        s = _find(_load_book(book)["settings"], name)
        if not s:
            return _ok({"error": f"设定 '{name}' 不存在于《{book}》"})
        return _ok(s)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_timeline(book: str, importance: str = "", character: str = "") -> str:
    """按章节分组的事件时间线。

    Args:
        book: 作品名
        importance: 重要度过滤（高/中/低），留空返回全部
        character: 只看该人物参与的事件
    """
    try:
        return _ok(await api_timeline(book, importance=importance, character=character))
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def get_graph(book: str) -> str:
    """关系图谱数据：人物节点 + 人际关系边（可直接喂给图可视化）。"""
    try:
        return _ok(await api_graph(book))
    except Exception as e:  # noqa: BLE001
        return _err(e)


if __name__ == "__main__":
    mcp.run(transport="stdio")
