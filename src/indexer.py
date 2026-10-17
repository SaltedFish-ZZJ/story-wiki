"""
Story Wiki - Vault 索引器
把已有 vault 的 Obsidian md 卡片扫描进 SQLite 元数据库（幂等：重复跑不重复插），
供 Web 端 /api/search 全文检索使用。

用法：
    python -m src.indexer --rebuild          # 清库重建全部索引
    python -m src.indexer                    # 增量入库（幂等）
    python -m src.indexer --stats            # 查看各作品实体统计

生成流程结束后也会自动调用增量入库（见 generator.py 的钩子）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from src.db import (
    connect,
    init_schema,
    rebuild_schema,
    upsert_document,
    upsert_entity,
    delete_stale_entities,
    replace_relations,
    upsert_event_time,
    document_stats,
    DEFAULT_DB_PATH,
)

# ── 解析用正则（与 web/app.py 的解析逻辑保持一致） ─────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^|\]]+?)(?:\|([^\]]+?))?\]\]")
_FM_SCALAR_RE = re.compile(r"^([A-Za-z_]\w*):\s*(.+)$")
_HEADING_RE = re.compile(r"^\s*#\s+(.+)$")
_CHINESE_NUM_RE = re.compile(r"[第\s]*([0-9０-９一二三四五六七八九十百零两]+)[章回节]")

# 顶层目录名 → 实体类型
_KIND_BY_DIR = {"characters": "character", "events": "event", "settings": "setting"}

# 跳过的非卡片文件
_SKIP_FILES = {"timeline.md"}


# ── md 卡片解析 ──────────────────────────────────────────────


def _read_md(filepath: Path) -> str:
    try:
        return filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _parse_frontmatter(text: str) -> dict:
    """解析 frontmatter 中的标量字段（不依赖 pyyaml，仅覆盖索引所需字段）。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split("\n"):
        sm = _FM_SCALAR_RE.match(line.strip())
        if sm:
            value = sm.group(2).strip().strip("\"'，")
            # 去掉行内注释与列表括号，仅保留标量
            if value.startswith("[") and value.endswith("]"):
                continue
            fm[sm.group(1)] = value
    return fm


def _extract_name(text: str, fallback: str) -> str:
    """提取 frontmatter 之后的 # 标题作为名称。"""
    without_fm = _FRONTMATTER_RE.sub("", text, count=1)
    for line in without_fm.split("\n"):
        m = _HEADING_RE.match(line)
        if m:
            return m.group(1).strip()
    return fallback


def _extract_summary(text: str, limit: int = 300) -> str:
    """提取 frontmatter 之后、第一个 ## 之前的正文摘要。"""
    without_fm = _FRONTMATTER_RE.sub("", text, count=1)
    lines = []
    for line in without_fm.split("\n"):
        s = line.strip()
        if s.startswith("##"):
            break
        if s.startswith("#"):
            continue
        # 跳过状态行（> 开头的 blockquote 与 🟢/🔴 徽标行）
        if s.startswith(">") or "🔴" in s or "🟢" in s or "⚫" in s:
            continue
        if s and "---" not in s:
            lines.append(s)
    if lines:
        return " ".join(lines)[:limit]
    # 回退：人物卡取「身份」小节，设定卡取「描述」小节（去掉 wikilink）
    for header in ("身份", "描述"):
        section = _extract_section(without_fm, header).strip()
        if section:
            clean = _WIKILINK_RE.sub(lambda m: m.group(2) or m.group(1), section)
            return " ".join(
                ln.strip() for ln in clean.split("\n") if ln.strip()
            )[:limit]
    return ""


def _extract_section(text: str, header: str) -> str:
    pat = re.compile(
        rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=^##\s|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pat.search(text)
    return m.group(1) if m else ""


def _parse_relations(text: str) -> list[tuple[str, str]]:
    """解析人物卡「人际关系」小节：返回 [(目标wikilink路径, 关系描述), ...]。"""
    section = _extract_section(text, "人际关系")
    results = []
    for line in section.split("\n"):
        line = line.strip().lstrip("- ").strip()
        m = _WIKILINK_RE.search(line)
        if not m:
            continue
        path = m.group(1).strip()
        after = _WIKILINK_RE.sub("", line).strip().lstrip("—- ").strip()
        results.append((path, after))
    return results


def _chapter_order(chapter_label: str) -> int:
    """从「第二十八章」这类标签提取章号，用于事件排序。"""
    if not chapter_label:
        return 0
    m = _CHINESE_NUM_RE.search(chapter_label)
    if not m:
        return 0
    raw = m.group(1)
    # 阿拉伯数字（含全角）
    digits = raw.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if digits.isdigit():
        return int(digits)
    return _cn_to_int(digits)


_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def _cn_to_int(s: str) -> int:
    """中文数字转 int（支持 十/百 量级，如 一百零七）。"""
    total, current = 0, 0
    for ch in s:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            total += (current or 1) * unit
            current = 0
    return total + current


# ── 作品目录发现（与 web/app.py 的 _find_book_dir 规则一致） ────


def _find_book_dir(vault_dir: Path, title: str) -> Path | None:
    candidate = vault_dir / title / title
    if (candidate / "_index.md").exists():
        return candidate
    candidate2 = vault_dir / title
    if (candidate2 / "_index.md").exists():
        return candidate2
    return None


def _iter_book_dirs(vault_dir: Path) -> list[tuple[str, Path]]:
    """返回 [(书名, 书目录), ...]。"""
    books = []
    if not vault_dir.exists():
        return books
    for child in sorted(vault_dir.iterdir()):
        if child.is_dir():
            book_dir = _find_book_dir(vault_dir, child.name)
            if book_dir:
                books.append((child.name, book_dir))
    return books


# ── 单本作品索引 ─────────────────────────────────────────────


def index_book(conn, vault_dir: Path, book_dir: Path) -> dict:
    """把单本作品的全部卡片索引入库（幂等）。"""
    title = book_dir.parent.name if book_dir.parent != vault_dir else book_dir.name
    rel_root = book_dir.relative_to(vault_dir).as_posix()

    cards: list[dict] = []
    char_count = 0
    chapters: set[str] = set()

    for md_file in sorted(book_dir.rglob("*.md")):
        if md_file.name.startswith("_") or md_file.name in _SKIP_FILES:
            continue
        rel = md_file.relative_to(book_dir)
        if len(rel.parts) < 2:
            continue
        kind = _KIND_BY_DIR.get(rel.parts[0])
        if not kind:
            continue
        text = _read_md(md_file)
        if not text:
            continue

        fm = _parse_frontmatter(text)
        name = _extract_name(text, md_file.stem)
        category = rel.parts[1] if len(rel.parts) > 2 else ""
        md_path = f"{rel_root}/{rel.as_posix()}"

        card = {
            "kind": kind,
            "name": name,
            "category": category,
            "summary": _extract_summary(text),
            "md_path": md_path,
            "fm": fm,
            "relations": _parse_relations(text) if kind == "character" else [],
            "chapter": fm.get("chapter", ""),
        }
        cards.append(card)
        char_count += len(text)
        if kind == "event" and card["chapter"]:
            chapters.add(card["chapter"])

    # 1. 作品记录
    doc_id = upsert_document(
        conn, title, source_path=str(book_dir),
        char_count=char_count, chapter_count=len(chapters),
    )

    # 2. 实体（md_path 唯一键，幂等 upsert）
    id_by_path: dict[str, int] = {}
    for card in cards:
        eid = upsert_entity(
            conn, doc_id, card["kind"], card["name"], card["md_path"],
            category=card["category"], summary=card["summary"],
        )
        id_by_path[card["md_path"]] = eid
    deleted = delete_stale_entities(conn, doc_id, set(id_by_path))

    # 3. 关系（两遍法：先建全量实体，再按 wikilink 路径精确解析目标）
    relations = []
    for card in cards:
        if card["kind"] != "character":
            continue
        src_id = id_by_path[card["md_path"]]
        for link_path, label in card["relations"]:
            target_path = f"{rel_root}/{link_path}.md"
            dst_id = id_by_path.get(target_path)
            if dst_id is None:
                # 退路：按显示名在同书内匹配
                dst_id = _find_by_name(conn, doc_id, link_path.rsplit("/", 1)[-1])
            if dst_id and dst_id != src_id:
                relations.append((src_id, dst_id, label[:50], card["md_path"]))
    replace_relations(conn, doc_id, relations)

    # 4. 事件时间（order_idx = 章号*1000 + 扫描序，保证章内稳定、章间有序）
    seq_in_chapter: dict[int, int] = {}
    events_with_time = 0
    for card in cards:
        if card["kind"] != "event":
            continue
        ch_num = _chapter_order(card["chapter"])
        seq = seq_in_chapter.get(ch_num, 0)
        seq_in_chapter[ch_num] = seq + 1
        time_label = card["fm"].get("time", "") or card["chapter"]
        upsert_event_time(conn, id_by_path[card["md_path"]],
                          ch_num * 1000 + seq, time_label)
        events_with_time += 1

    conn.commit()
    return {
        "title": title,
        "entities": len(cards),
        "relations": len(relations),
        "events_with_time": events_with_time,
        "deleted_stale": deleted,
    }


def _find_by_name(conn, doc_id: int, name: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM entity WHERE doc_id = ? AND name = ? LIMIT 1",
        (doc_id, name),
    ).fetchone()
    return int(row["id"]) if row else None


# ── 全库索引 ─────────────────────────────────────────────────


def index_vault(vault_dir: str | Path | None = None, db_path: str | Path | None = None,
                rebuild: bool = False) -> dict:
    """
    索引整个 vault（幂等）。rebuild=True 时先清空重建全部表。

    返回统计 dict，供 CLI 打印与生成流程钩子记录日志。
    """
    vault = Path(vault_dir) if vault_dir else DEFAULT_DB_PATH.parent / "output"
    conn = connect(db_path)
    try:
        if rebuild:
            rebuild_schema(conn)
        else:
            init_schema(conn)

        totals = {"books": 0, "entities": 0, "relations": 0,
                  "events_with_time": 0, "deleted_stale": 0}
        for _title, book_dir in _iter_book_dirs(vault):
            stats = index_book(conn, vault, book_dir)
            totals["books"] += 1
            for key in ("entities", "relations", "events_with_time", "deleted_stale"):
                totals[key] += stats[key]
        return totals
    finally:
        conn.close()


# ── 命令行入口 ───────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 vault 的 md 卡片索引进 SQLite")
    parser.add_argument("--db", default=None, help=f"数据库路径（默认 {DEFAULT_DB_PATH}）")
    parser.add_argument("--vault", default=None, help="vault 根目录（默认 data/output）")
    parser.add_argument("--rebuild", action="store_true", help="清库后全量重建索引")
    parser.add_argument("--stats", action="store_true", help="只显示统计信息")
    args = parser.parse_args(argv)

    if args.stats:
        conn = connect(args.db)
        try:
            init_schema(conn)
            for row in document_stats(conn):
                print(f"{row['title']}: 实体 {row['entity_count']} | "
                      f"字数 {row['char_count']} | 章节 {row['chapter_count']}")
        finally:
            conn.close()
        return 0

    totals = index_vault(args.vault, args.db, rebuild=args.rebuild)
    print(f"索引完成：{totals['books']} 本作品，"
          f"{totals['entities']} 个实体，{totals['relations']} 条关系，"
          f"{totals['events_with_time']} 条事件时间"
          + (f"，清理失效 {totals['deleted_stale']} 条" if totals["deleted_stale"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
