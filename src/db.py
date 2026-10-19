"""
Story Wiki - SQLite 元数据层
存储作品(document)/实体(entity)/关系(relation)/事件时间(event_time)的结构化元数据，
并提供 FTS5 全文检索能力。只用标准库 sqlite3，不引入 ORM。

库文件默认位于 data/wiki.db；FTS5 使用 unicode61 分词器（中文按字切分），
查询时用短语包裹避免按字 OR 拆分造成误召回。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "wiki.db"

# ── 表结构 ───────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS document (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL UNIQUE,
    source_path   TEXT NOT NULL DEFAULT '',
    char_count    INTEGER NOT NULL DEFAULT 0,
    chapter_count INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS entity (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id   INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    kind     TEXT NOT NULL CHECK (kind IN ('character', 'event', 'setting')),
    name     TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    summary  TEXT NOT NULL DEFAULT '',
    md_path  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS relation (
    from_id  INTEGER NOT NULL REFERENCES entity(id) ON DELETE CASCADE,
    to_id    INTEGER NOT NULL REFERENCES entity(id) ON DELETE CASCADE,
    label    TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (from_id, to_id, label)
);

CREATE TABLE IF NOT EXISTS event_time (
    entity_id  INTEGER PRIMARY KEY REFERENCES entity(id) ON DELETE CASCADE,
    order_idx  INTEGER NOT NULL DEFAULT 0,
    time_label TEXT NOT NULL DEFAULT ''
);

-- FTS5 外部内容表：内容跟随 entity 表，由触发器同步
CREATE VIRTUAL TABLE IF NOT EXISTS entity_fts USING fts5(
    name, summary, content='entity', content_rowid='id', tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS entity_fts_ai AFTER INSERT ON entity BEGIN
    INSERT INTO entity_fts(rowid, name, summary) VALUES (new.id, new.name, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS entity_fts_ad AFTER DELETE ON entity BEGIN
    INSERT INTO entity_fts(entity_fts, rowid, name, summary)
    VALUES ('delete', old.id, old.name, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS entity_fts_au AFTER UPDATE ON entity BEGIN
    INSERT INTO entity_fts(entity_fts, rowid, name, summary)
    VALUES ('delete', old.id, old.name, old.summary);
    INSERT INTO entity_fts(rowid, name, summary) VALUES (new.id, new.name, new.summary);
END;
"""

# 允许的实体类型
VALID_KINDS = ("character", "event", "setting")


# ── 连接与建表 ───────────────────────────────────────────────


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """打开数据库连接。check_same_thread=False 允许后台线程复用（Web 场景）。"""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """建表（幂等，可重复执行）。"""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def rebuild_schema(conn: sqlite3.Connection) -> None:
    """删掉所有表后重建（--rebuild 用）。"""
    conn.executescript("""
        DROP TRIGGER IF EXISTS entity_fts_ai;
        DROP TRIGGER IF EXISTS entity_fts_ad;
        DROP TRIGGER IF EXISTS entity_fts_au;
        DROP TABLE IF EXISTS entity_fts;
        DROP TABLE IF EXISTS relation;
        DROP TABLE IF EXISTS event_time;
        DROP TABLE IF EXISTS entity;
        DROP TABLE IF EXISTS document;
    """)
    conn.commit()
    init_schema(conn)


# ── 常用写操作 ───────────────────────────────────────────────


def upsert_document(conn: sqlite3.Connection, title: str, source_path: str = "",
                    char_count: int = 0, chapter_count: int = 0) -> int:
    """按 title 幂等写入/更新作品记录，返回 document.id。"""
    conn.execute(
        """
        INSERT INTO document (title, source_path, char_count, chapter_count)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(title) DO UPDATE SET
            source_path = excluded.source_path,
            char_count = excluded.char_count,
            chapter_count = excluded.chapter_count
        """,
        (title, source_path, char_count, chapter_count),
    )
    row = conn.execute("SELECT id FROM document WHERE title = ?", (title,)).fetchone()
    return int(row["id"])


def upsert_entity(conn: sqlite3.Connection, doc_id: int, kind: str, name: str,
                  md_path: str, category: str = "", summary: str = "") -> int:
    """按 md_path 幂等写入/更新实体，返回 entity.id。"""
    if kind not in VALID_KINDS:
        raise ValueError(f"非法实体类型: {kind!r}，应为 {VALID_KINDS} 之一")
    conn.execute(
        """
        INSERT INTO entity (doc_id, kind, name, category, summary, md_path)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(md_path) DO UPDATE SET
            doc_id = excluded.doc_id,
            kind = excluded.kind,
            name = excluded.name,
            category = excluded.category,
            summary = excluded.summary
        """,
        (doc_id, kind, name, category, summary, md_path),
    )
    row = conn.execute(
        "SELECT id FROM entity WHERE md_path = ?", (md_path,)
    ).fetchone()
    return int(row["id"])


def delete_stale_entities(conn: sqlite3.Connection, doc_id: int, live_md_paths: set[str]) -> int:
    """删除某作品下已不存在于磁盘的实体（级联清掉 relation/event_time）。"""
    rows = conn.execute(
        "SELECT id, md_path FROM entity WHERE doc_id = ?", (doc_id,)
    ).fetchall()
    stale = [r["id"] for r in rows if r["md_path"] not in live_md_paths]
    for eid in stale:
        conn.execute("DELETE FROM entity WHERE id = ?", (eid,))
    return len(stale)


def replace_relations(conn: sqlite3.Connection, doc_id: int,
                      relations: list[tuple[int, int, str, str]]) -> None:
    """清空并重写某作品下所有关系（INSERT OR IGNORE 防同键重复）。"""
    conn.execute(
        "DELETE FROM relation WHERE from_id IN (SELECT id FROM entity WHERE doc_id = ?)",
        (doc_id,),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO relation (from_id, to_id, label, evidence) VALUES (?, ?, ?, ?)",
        relations,
    )


def upsert_event_time(conn: sqlite3.Connection, entity_id: int,
                      order_idx: int, time_label: str) -> None:
    """幂等写入事件时间信息。"""
    conn.execute(
        """
        INSERT INTO event_time (entity_id, order_idx, time_label)
        VALUES (?, ?, ?)
        ON CONFLICT(entity_id) DO UPDATE SET
            order_idx = excluded.order_idx,
            time_label = excluded.time_label
        """,
        (entity_id, order_idx, time_label),
    )


# ── 查询 ─────────────────────────────────────────────────────


def search_entities(conn: sqlite3.Connection, query: str, kind: str | None = None,
                    limit: int = 20) -> list[dict]:
    """
    FTS5 全文检索实体。

    - query 用双引号包裹为短语查询，先走 bm25 相关度排序
    - kind 可选 'character' / 'event' / 'setting' 过滤
    - unicode61 分词器不会按字切分中文（「孙少安」是单个 token），
      短关键词如「少安」匹配不到长 token —— FTS 零命中时回退 name LIKE 子串扫描保证召回
    - 返回字段带 md_path 与所属书名
    """
    if not query or not query.strip():
        return []
    phrase = '"' + query.strip().replace('"', '""') + '"'
    sql = """
        SELECT e.id, e.kind, e.name, e.category, e.summary, e.md_path,
               d.title AS book,
               bm25(entity_fts) AS rank
        FROM entity_fts f
        JOIN entity e ON e.id = f.rowid
        JOIN document d ON d.id = e.doc_id
        WHERE entity_fts MATCH ?
    """
    params: list = [phrase]
    if kind:
        if kind not in VALID_KINDS:
            return []
        sql += " AND e.kind = ?"
        params.append(kind)
    sql += " ORDER BY rank LIMIT ?"
    params.append(max(1, min(int(limit), 100)))

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        # 查询语法异常（如纯标点）时安全降级为空结果
        rows = []
    if rows:
        return [dict(r) for r in rows]

    # LIKE 兜底：仅扫 name，避免 summary 子串误召回（与 kind 过滤语义一致）
    like = f"%{query.strip()}%"
    fallback_sql = """
        SELECT e.id, e.kind, e.name, e.category, e.summary, e.md_path,
               d.title AS book, 0 AS rank
        FROM entity e
        JOIN document d ON d.id = e.doc_id
        WHERE e.name LIKE ?
    """
    fallback_params: list = [like]
    if kind:
        fallback_sql += " AND e.kind = ?"
        fallback_params.append(kind)
    fallback_sql += " ORDER BY LENGTH(e.name) LIMIT ?"
    fallback_params.append(max(1, min(int(limit), 100)))
    try:
        rows = conn.execute(fallback_sql, fallback_params).fetchall()
    except sqlite3.OperationalError:
        # 空库（未建索引）等表缺失场景，与上方 FTS 兜底语义一致
        rows = []
    return [dict(r) for r in rows]


def document_stats(conn: sqlite3.Connection) -> list[dict]:
    """按作品统计实体数，用于自检。"""
    rows = conn.execute(
        """
        SELECT d.title, d.char_count, d.chapter_count,
               COUNT(e.id) AS entity_count
        FROM document d LEFT JOIN entity e ON e.doc_id = d.id
        GROUP BY d.id ORDER BY d.title
        """
    ).fetchall()
    return [dict(r) for r in rows]
