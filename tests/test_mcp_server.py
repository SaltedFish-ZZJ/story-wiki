"""
Story Wiki - MCP 读侧 Server 测试
覆盖：9 个工具的业务逻辑（正常路径 + 错误分支 + 错误隔离）
与 FastMCP 注册冒烟。数据通过 monkeypatch web.app.OUTPUT_DIR
指向临时目录构造，不触碰真实知识库。
"""

import asyncio
import json

import pytest

pytest.importorskip("mcp")       # 未安装 mcp extra 则整体跳过
pytest.importorskip("fastapi")   # mcp_server 依赖 web.app

import web.app as webapp  # noqa: E402
import web.mcp_server as mcpsrv  # noqa: E402
from src import db as sdb  # noqa: E402


def _call(coro) -> dict:
    """同步执行工具协程并解析 JSON 结果。"""
    return json.loads(asyncio.run(coro))


def _unwrap(fn):
    """兼容 FastMCP 装饰器返回原函数或 Tool 对象两种实现。"""
    return getattr(fn, "fn", fn)


# ── 测试数据 ─────────────────────────────────────────────────

BOOK_MD = "---\ntitle: 测试之书\n---\n\n# 测试之书\n\n> 一本测试书\n"


def _make_vault(output_dir):
    """构造一本假书：2 人物 + 2 事件（因果链）+ 1 设定。"""
    book = output_dir / "测试之书" / "测试之书"
    book.mkdir(parents=True)
    (book / "_index.md").write_text(BOOK_MD, encoding="utf-8")

    chars = book / "characters" / "主要人物"
    chars.mkdir(parents=True)
    (chars / "孙大圣.md").write_text(
        "---\ntype: character\ngender: 男\nrole_tags: [主角]\ncolor: character-protagonist\n"
        "---\n\n# 孙大圣\n\n🟢 在世\n\n## 身份\n齐天大圣\n\n## 人际关系\n"
        "- [[characters/主要人物/猪二郎|猪二郎]] — 师弟\n\n## 参与事件\n"
        "- [[events/重大事件/蟠桃会|蟠桃会]] — 赴宴\n"
        "- [[events/重大事件/大闹天宫|大闹天宫]] — 率先动手\n",
        encoding="utf-8")
    (chars / "猪二郎.md").write_text(
        "---\ntype: character\ngender: 男\nrole_tags: [配角]\n"
        "---\n\n# 猪二郎\n\n⚫ 天蓬元帅\n\n## 身份\n天河水军统领\n",
        encoding="utf-8")

    evs = book / "events" / "重大事件"
    evs.mkdir(parents=True)
    (evs / "蟠桃会.md").write_text(
        "---\ntype: event\ntime: 上古\nchapter: 第三章\nimportance: 中\ncolor: event-normal\n"
        "---\n\n# 蟠桃会\n\n瑶池设宴，唯独没请孙大圣。\n\n## 参与人物\n"
        "- [[characters/主要人物/孙大圣|孙大圣]] — 不速之客\n\n## 后续影响\n"
        "- [[events/重大事件/大闹天宫|大闹天宫]] — 受辱后大闹\n",
        encoding="utf-8")
    (evs / "大闹天宫.md").write_text(
        "---\ntype: event\ntime: 上古\nchapter: 第三章\nimportance: 高\ncolor: event-climax\n"
        "---\n\n# 大闹天宫\n\n掀翻蟠桃宴，大战十万天兵。\n\n## 参与人物\n"
        "- [[characters/主要人物/孙大圣|孙大圣]] — 主角\n\n## 前置事件\n"
        "- [[events/重大事件/蟠桃会|蟠桃会]] — 因未受邀\n\n## 发生地点\n"
        "- [[settings/场所/天宫|天宫]]\n",
        encoding="utf-8")

    sets = book / "settings" / "场所"
    sets.mkdir(parents=True)
    (sets / "天宫.md").write_text(
        "---\ntype: setting\nsetting_type: 地点\n"
        "---\n\n# 天宫\n\n玉帝的地盘。\n\n## 关联人物\n"
        "- [[characters/主要人物/孙大圣|孙大圣]]\n",
        encoding="utf-8")
    return book


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _make_vault(output_dir)
    monkeypatch.setattr(webapp, "OUTPUT_DIR", output_dir)
    webapp._cache.clear()
    yield output_dir
    webapp._cache.clear()


@pytest.fixture()
def index(tmp_path, monkeypatch):
    """临时 FTS5 索引：document「测试之书」+ 实体「孙大圣」。"""
    db_path = tmp_path / "wiki.db"
    monkeypatch.setattr(sdb, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(mcpsrv, "DEFAULT_DB_PATH", db_path)
    conn = sdb.connect(db_path)
    sdb.init_schema(conn)
    doc_id = sdb.upsert_document(conn, "测试之书", "测试之书/测试之书")
    sdb.upsert_entity(conn, doc_id, "character", "孙大圣",
                      md_path="测试之书/characters/孙大圣.md",
                      category="主要人物", summary="齐天大圣")
    conn.commit()
    conn.close()
    return db_path


# ── FastMCP 注册冒烟 ─────────────────────────────────────────


def test_nine_tools_registered():
    tools = asyncio.run(mcpsrv.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "list_books", "get_overview", "search", "list_characters",
        "get_character", "get_event", "get_setting", "get_timeline", "get_graph",
    }


# ── list_books ───────────────────────────────────────────────


def test_list_books(vault):
    books = _call(_unwrap(mcpsrv.list_books)())["books"]
    assert len(books) == 1
    b = books[0]
    assert b["title"] == "测试之书"
    assert b["characters"] == 2
    assert b["events"] == 2
    assert b["settings"] == 1


def test_list_books_empty(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(webapp, "OUTPUT_DIR", output_dir)
    webapp._cache.clear()
    assert _call(_unwrap(mcpsrv.list_books)()) == {"books": []}


def test_list_books_skips_dir_without_cards(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    (output_dir / "空目录").mkdir(parents=True)
    monkeypatch.setattr(webapp, "OUTPUT_DIR", output_dir)
    webapp._cache.clear()
    assert _call(_unwrap(mcpsrv.list_books)())["books"] == []


# ── get_overview ─────────────────────────────────────────────


def test_get_overview(vault):
    data = _call(_unwrap(mcpsrv.get_overview)("测试之书"))
    assert data["title"] == "测试之书"
    assert data["stats"] == {"characters": 2, "events": 2, "settings": 1}
    assert data["character_groups"]["核心人物"] == 1
    assert data["character_groups"]["重要配角"] == 1


def test_get_overview_unknown_book(vault):
    assert "error" in _call(_unwrap(mcpsrv.get_overview)("不存在的书"))


# ── list_characters ──────────────────────────────────────────


def test_list_characters_sorted_by_protagonist(vault):
    data = _call(_unwrap(mcpsrv.list_characters)("测试之书"))
    assert data["total"] == 2
    assert data["characters"][0]["name"] == "孙大圣"  # 主角排前


def test_list_characters_filter(vault):
    data = _call(_unwrap(mcpsrv.list_characters)("测试之书", q="大圣"))
    assert data["total"] == 1
    assert data["characters"][0]["name"] == "孙大圣"
    data = _call(_unwrap(mcpsrv.list_characters)("测试之书", q="不存在"))
    assert data["total"] == 0


# ── get_character ────────────────────────────────────────────


def test_get_character(vault):
    c = _call(_unwrap(mcpsrv.get_character)("测试之书", "孙大圣"))
    assert c["status"] == "在世"
    assert c["identity"] == "齐天大圣"
    assert [r["name"] for r in c["relationships"]] == ["猪二郎"]
    assert [e["name"] for e in c["events"]] == ["蟠桃会", "大闹天宫"]


def test_get_character_unknown(vault):
    data = _call(_unwrap(mcpsrv.get_character)("测试之书", "唐三藏"))
    assert data == {"error": "人物 '唐三藏' 不存在于《测试之书》"}


# ── get_event ────────────────────────────────────────────────


def test_get_event_cause_effect(vault):
    e = _call(_unwrap(mcpsrv.get_event)("测试之书", "大闹天宫"))
    assert e["chapter"] == "第三章"
    assert e["importance"] == "高"
    assert [c["name"] for c in e["cause"]] == ["蟠桃会"]
    assert [p["name"] for p in e["participants"]] == ["孙大圣"]


def test_get_event_unknown(vault):
    assert "error" in _call(_unwrap(mcpsrv.get_event)("测试之书", "不存在"))


# ── get_setting ──────────────────────────────────────────────


def test_get_setting(vault):
    s = _call(_unwrap(mcpsrv.get_setting)("测试之书", "天宫"))
    assert s["setting_type"] == "地点"
    assert [c["name"] for c in s["characters"]] == ["孙大圣"]


def test_get_setting_unknown(vault):
    assert "error" in _call(_unwrap(mcpsrv.get_setting)("测试之书", "不存在"))


# ── get_timeline ─────────────────────────────────────────────


def test_get_timeline(vault):
    data = _call(_unwrap(mcpsrv.get_timeline)("测试之书"))
    assert data["total"] == 2
    assert data["events"][0]["name"] == "大闹天宫"  # 重要度「高」排前


def test_get_timeline_filters(vault):
    data = _call(_unwrap(mcpsrv.get_timeline)("测试之书", importance="高"))
    assert data["total"] == 1
    assert data["events"][0]["name"] == "大闹天宫"
    data = _call(_unwrap(mcpsrv.get_timeline)("测试之书", character="猪二郎"))
    assert data["total"] == 0


# ── get_graph ────────────────────────────────────────────────


def test_get_graph_nodes_and_edges(vault):
    g = _call(_unwrap(mcpsrv.get_graph)("测试之书"))
    node_ids = {n["id"] for n in g["nodes"]}
    assert {"孙大圣", "猪二郎"} <= node_ids
    assert len(g["edges"]) >= 1


# ── search（FTS5 + LIKE 兜底） ───────────────────────────────


def test_search_full_token(index):
    results = _call(_unwrap(mcpsrv.search)("孙大圣"))["results"]
    assert "孙大圣" in [r["name"] for r in results]


def test_search_substring_fallback(index):
    # unicode61 不按字切中文，子串「大圣」FTS 零命中 → LIKE 兜底
    results = _call(_unwrap(mcpsrv.search)("大圣"))["results"]
    assert any(r["name"] == "孙大圣" for r in results)


def test_search_kind_filter(index):
    results = _call(_unwrap(mcpsrv.search)("孙大圣", kind="event"))["results"]
    assert results == []


def test_search_missing_index(tmp_path, monkeypatch):
    monkeypatch.setattr(mcpsrv, "DEFAULT_DB_PATH", tmp_path / "no" / "such.db")
    data = _call(_unwrap(mcpsrv.search)("孙大圣"))
    assert "索引不存在" in data["error"]
