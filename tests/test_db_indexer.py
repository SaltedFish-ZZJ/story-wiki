"""
Story Wiki - SQLite 元数据层与索引器测试
覆盖：建表幂等、upsert 幂等、FTS5 中文检索、关系解析、事件时间排序、
失效实体清理、--rebuild 重建、Web /api/search 接口。
"""
from pathlib import Path

import pytest

from src.db import (
    connect,
    init_schema,
    rebuild_schema,
    upsert_document,
    upsert_entity,
    delete_stale_entities,
    search_entities,
    document_stats,
)
from src.indexer import index_vault, index_book, _chapter_order


# ── 测试数据：构造一个迷你 vault ──────────────────────────────

_CHAR_CARD = """---
type: character
color: character-protagonist
source: analyzed
origin: 测试之书
gender: 男
faction: 测试阵营
role_tags: [男主, 主角]
tags: [character]
created: 2026-10-17
---
# 李主角

> 🟢 活跃 | 阵营：测试阵营 | 定位：男主 · 主角

## 身份
测试之书的男主角，靠种田发家

## 性格
坚韧不拔

## 人际关系
- [[characters/主要人物/王配角|王配角]] — 挚友
- [[characters/主要人物/赵反派|赵反派]] — 死敌
"""

_CHAR_CARD2 = """---
type: character
source: analyzed
origin: 测试之书
gender: 男
tags: [character]
created: 2026-10-17
---
# 王配角

> 🟢 活跃 | 定位：配角

## 身份
主角的挚友
"""

_EVENT_CARD = """---
type: event
color: event-major
source: analyzed
origin: 测试之书
time: 黄昏
chapter: 第十二章
importance: 高
tags: [event]
created: 2026-10-17
---
# 砖窑点火

> 🔴 高 | 👥 2人参与

**时间**：黄昏

李主角的砖窑第一次点火，全村围观。

## 参与人物
- [[characters/主要人物/李主角|李主角]]
"""

_SETTING_CARD = """---
type: setting
color: setting-concept
source: analyzed
origin: 测试之书
setting_type: 概念
tags: [setting]
created: 2026-10-17
---
# 砖窑技术

> 🟢 概念

## 描述
一项让主角发家的烧砖技术
"""


@pytest.fixture()
def mini_vault(tmp_path) -> Path:
    """构建迷你 vault：书名/书名/{characters,events,settings}/... 结构。"""
    book = tmp_path / "vault" / "测试之书" / "测试之书"
    (book / "characters" / "主要人物").mkdir(parents=True)
    (book / "events" / "重大事件").mkdir(parents=True)
    (book / "settings" / "概念").mkdir(parents=True)
    (book / "characters" / "主要人物" / "李主角.md").write_text(_CHAR_CARD, encoding="utf-8")
    (book / "characters" / "主要人物" / "王配角.md").write_text(_CHAR_CARD2, encoding="utf-8")
    (book / "events" / "重大事件" / "砖窑点火.md").write_text(_EVENT_CARD, encoding="utf-8")
    (book / "settings" / "概念" / "砖窑技术.md").write_text(_SETTING_CARD, encoding="utf-8")
    (book / "_index.md").write_text("---\ntype: book\ntags: [book]\n---\n# 测试之书\n", encoding="utf-8")
    return tmp_path / "vault"


# ── db.py 基础行为 ────────────────────────────────────────────


class TestDbBasics:
    def test_init_schema_idempotent(self, tmp_path):
        conn = connect(tmp_path / "t.db")
        init_schema(conn)
        init_schema(conn)  # 重复执行不报错
        conn.close()

    def test_upsert_document_idempotent(self, tmp_path):
        conn = connect(tmp_path / "t.db")
        init_schema(conn)
        id1 = upsert_document(conn, "书A", char_count=100)
        id2 = upsert_document(conn, "书A", char_count=200)
        assert id1 == id2
        assert conn.execute("SELECT COUNT(*) c FROM document").fetchone()["c"] == 1
        assert conn.execute("SELECT char_count FROM document").fetchone()["char_count"] == 200
        conn.close()

    def test_upsert_entity_rejects_bad_kind(self, tmp_path):
        conn = connect(tmp_path / "t.db")
        init_schema(conn)
        doc = upsert_document(conn, "书A")
        with pytest.raises(ValueError):
            upsert_entity(conn, doc, "novel", "x", "a/b.md")
        conn.close()

    def test_stale_delete_cascades(self, tmp_path):
        conn = connect(tmp_path / "t.db")
        init_schema(conn)
        doc = upsert_document(conn, "书A")
        eid = upsert_entity(conn, doc, "character", "甲", "书A/characters/甲.md")
        conn.execute(
            "INSERT INTO relation (from_id, to_id, label) VALUES (?, ?, ?)",
            (eid, eid, "自环"),
        )
        conn.commit()
        # 甲.md 已从磁盘消失 → 清理并级联删关系
        removed = delete_stale_entities(conn, doc, set())
        assert removed == 1
        assert conn.execute("SELECT COUNT(*) c FROM relation").fetchone()["c"] == 0
        conn.close()

    def test_rebuild_schema_drops_everything(self, tmp_path):
        conn = connect(tmp_path / "t.db")
        init_schema(conn)
        doc = upsert_document(conn, "书A")
        upsert_entity(conn, doc, "character", "甲", "书A/characters/甲.md")
        conn.commit()
        rebuild_schema(conn)
        assert conn.execute("SELECT COUNT(*) c FROM document").fetchone()["c"] == 0
        assert conn.execute("SELECT COUNT(*) c FROM entity").fetchone()["c"] == 0
        conn.close()


# ── FTS5 检索 ────────────────────────────────────────────────


class TestFtsSearch:
    def _seed(self, tmp_path):
        conn = connect(tmp_path / "t.db")
        init_schema(conn)
        doc = upsert_document(conn, "书A")
        upsert_entity(conn, doc, "character", "孙少安", "书A/characters/孙少安.md",
                      category="主要人物", summary="双水村农民")
        upsert_entity(conn, doc, "event", "砖窑点火", "书A/events/砖窑点火.md",
                      category="重大事件", summary="孙少安点火")
        conn.commit()
        return conn

    def test_chinese_phrase_match(self, tmp_path):
        conn = self._seed(tmp_path)
        results = search_entities(conn, "孙少安")
        assert len(results) == 1
        assert results[0]["md_path"] == "书A/characters/孙少安.md"
        assert results[0]["book"] == "书A"
        conn.close()

    def test_kind_filter(self, tmp_path):
        conn = self._seed(tmp_path)
        assert len(search_entities(conn, "孙少安", kind="character")) == 1
        assert search_entities(conn, "孙少安", kind="event") == []
        conn.close()

    def test_empty_and_bad_query(self, tmp_path):
        conn = self._seed(tmp_path)
        assert search_entities(conn, "") == []
        assert search_entities(conn, "   ") == []
        # 纯标点不应抛异常
        assert isinstance(search_entities(conn, "***"), list)
        conn.close()

    def test_summary_content_searchable(self, tmp_path):
        conn = self._seed(tmp_path)
        results = search_entities(conn, "双水村农民")
        assert results and results[0]["name"] == "孙少安"
        conn.close()


# ── indexer.py ───────────────────────────────────────────────


class TestIndexer:
    def test_index_counts(self, mini_vault, tmp_path):
        db = tmp_path / "wiki.db"
        totals = index_vault(mini_vault, db)
        assert totals["books"] == 1
        assert totals["entities"] == 4
        assert totals["relations"] == 1  # 王配角可解析；赵反派卡片不存在，被丢弃
        assert totals["events_with_time"] == 1

    def test_idempotent(self, mini_vault, tmp_path):
        db = tmp_path / "wiki.db"
        first = index_vault(mini_vault, db)
        second = index_vault(mini_vault, db)
        assert second["entities"] == first["entities"]
        conn = connect(db)
        assert conn.execute("SELECT COUNT(*) c FROM entity").fetchone()["c"] == 4
        conn.close()

    def test_stale_removal(self, mini_vault, tmp_path):
        db = tmp_path / "wiki.db"
        index_vault(mini_vault, db)
        # 删掉一张卡片后再索引 → 实体数减少
        (mini_vault / "测试之书" / "测试之书" / "settings" / "概念" / "砖窑技术.md").unlink()
        totals = index_vault(mini_vault, db)
        assert totals["entities"] == 3
        assert totals["deleted_stale"] == 1

    def test_search_after_index(self, mini_vault, tmp_path):
        db = tmp_path / "wiki.db"
        index_vault(mini_vault, db)
        conn = connect(db)
        results = search_entities(conn, "李主角")
        assert len(results) == 1
        assert results[0]["md_path"] == "测试之书/测试之书/characters/主要人物/李主角.md"
        conn.close()

    def test_event_time_order(self, mini_vault, tmp_path):
        db = tmp_path / "wiki.db"
        index_vault(mini_vault, db)
        conn = connect(db)
        row = conn.execute(
            """
            SELECT et.order_idx, et.time_label FROM event_time et
            JOIN entity e ON e.id = et.entity_id WHERE e.name = '砖窑点火'
            """
        ).fetchone()
        assert row["order_idx"] == 12 * 1000  # 第十二章 → 12*1000 + 0
        assert row["time_label"] == "黄昏"
        conn.close()

    def test_chapter_order_parser(self):
        assert _chapter_order("第十二章") == 12
        assert _chapter_order("第一百零七章") == 107
        assert _chapter_order("第28章") == 28
        assert _chapter_order("") == 0

    def test_document_stats(self, mini_vault, tmp_path):
        db = tmp_path / "wiki.db"
        index_vault(mini_vault, db)
        conn = connect(db)
        stats = document_stats(conn)
        assert stats[0]["title"] == "测试之书"
        assert stats[0]["entity_count"] == 4
        conn.close()

    def test_index_book_via_hook_target(self, mini_vault, tmp_path):
        """generator._auto_index 使用的 index_book 单本入口也可用。"""
        from src.db import connect as _connect

        db = tmp_path / "wiki.db"
        conn = _connect(db)
        init_schema(conn)
        book_dir = mini_vault / "测试之书" / "测试之书"
        stats = index_book(conn, mini_vault, book_dir)
        assert stats["entities"] == 4
        conn.close()


# ── Web /api/search 接口 ─────────────────────────────────────


class TestSearchApi:
    def test_api_search(self, mini_vault, tmp_path, monkeypatch):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        import web.app as webapp

        db = tmp_path / "wiki.db"
        index_vault(mini_vault, db)
        monkeypatch.setattr(webapp, "OUTPUT_DIR", tmp_path / "output")
        monkeypatch.setattr("src.db.DEFAULT_DB_PATH", db)

        client = TestClient(webapp.app)
        resp = client.get("/api/search", params={"q": "李主角"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["md_path"].endswith("李主角.md")

        resp2 = client.get("/api/search", params={"q": "李主角", "kind": "event"})
        assert resp2.json()["total"] == 0

        resp3 = client.get("/api/search", params={"q": ""})
        assert resp3.json() == {"results": [], "total": 0}
