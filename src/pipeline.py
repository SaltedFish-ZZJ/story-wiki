"""
Story Wiki - 分章分析管线
将长文本切分为章节，逐章 AI 分析，合并去重后生成最终结果。
支持增量分析：追加新章节到已有笔记，不覆盖旧结果。
"""
import json
import os
from pathlib import Path

from src.analyzer import analyze_chapter
from src.splitter import Chapter, split_chapters, get_split_summary
from src.config import VAULT_DIR, INCREMENTAL_STATE_FILE


def analyze_chaptered(text: str, title: str = None, chunk_size: int = 5000,
                      on_chapter_start=None, on_chapter_done=None) -> dict:
    """
    分章分析长文本。

    流程：
    1. splitter 切分章节
    2. 逐章调用 analyze_chapter（携带已知人物/设定/事件上下文）
    3. 合并去重所有章节结果
    4. 返回与 analyze_text 兼容的最终 dict

    Args:
        text: 纯文本内容
        title: 作品名（可选）
        chunk_size: 无章节标记时每块的目标字数
        on_chapter_start: 回调函数 (chapter) -> None，每章开始分析前调用
        on_chapter_done: 回调函数 (chapter, result) -> None，每章分析完成后调用

    Returns:
        {
            "title": "作品名",
            "characters": [...],
            "settings": [...],
            "events": [...],
            "summary": "..."
        }
    """
    # Step 1: 切分章节
    chapters = split_chapters(text, chunk_size=chunk_size)
    if not chapters:
        raise ValueError("文本切分结果为空")

    print(f"[分章] {get_split_summary(chapters)}")

    # Step 2: 逐章分析
    all_characters = []   # 累积所有人物
    all_settings = []     # 累积所有设定
    all_events = []       # 累积所有事件
    chapter_summaries = []  # 每章摘要

    for i, chapter in enumerate(chapters):
        if on_chapter_start:
            on_chapter_start(chapter)

        print(f"[分析] 第 {i+1}/{len(chapters)} 章: {chapter.title} ({chapter.char_count} 字)")

        try:
            result = analyze_chapter(
                text=chapter.text,
                known_characters=all_characters,
                known_settings=all_settings,
                known_events=all_events,
                chapter_title=chapter.title,
            )
        except (ValueError, RuntimeError) as e:
            print(f"  ⚠️ 第 {i+1} 章分析失败: {e}，跳过")
            continue

        # 收集本章结果
        new_chars = result.get("characters", [])
        new_settings = result.get("settings", [])
        new_events = result.get("events", [])
        ch_summary = result.get("chapter_summary", "")

        if ch_summary:
            chapter_summaries.append(ch_summary)

        print(f"  [OK] 新增: {len(new_chars)} 人物, {len(new_settings)} 设定, {len(new_events)} 事件")

        # Step 3: 增量合并（每章合并后更新已知列表，供下一章使用）
        all_characters = merge_characters(all_characters, new_chars)
        all_settings = merge_settings(all_settings, new_settings)
        all_events = merge_events(all_events, new_events)

        if on_chapter_done:
            on_chapter_done(chapter, result)

    # Step 4: 构建最终结果
    summary = _build_summary(title, chapter_summaries, all_characters, all_settings)

    return {
        "title": title or "未命名作品",
        "characters": all_characters,
        "settings": all_settings,
        "events": all_events,
        "summary": summary,
    }


def merge_characters(existing: list, new_items: list) -> list:
    """
    合并人物列表，同名人物合并（取非空字段，合并关系）。
    """
    by_name = {}
    for c in existing:
        by_name[c["name"]] = c.copy()

    for c in new_items:
        name = c.get("name", "")
        if not name:
            continue

        if name in by_name:
            # 合并：取非空字段
            old = by_name[name]
            merged = _merge_single_character(old, c)
            by_name[name] = merged
        else:
            by_name[name] = c.copy()

    return list(by_name.values())


def _merge_single_character(old: dict, new: dict) -> dict:
    """合并同一个人物的两条记录。"""
    merged = old.copy()

    # 对于文本字段，取更长的（通常更详细）
    for key in ["identity", "personality", "faction", "gender"]:
        old_val = merged.get(key) or ""
        new_val = new.get(key) or ""
        if new_val and (not old_val or len(new_val) > len(old_val)):
            merged[key] = new_val

    # 集合类字段合并
    merged["aliases"] = _merge_set_list(merged, new, "aliases")
    merged["related_settings"] = _merge_set_list(merged, new, "related_settings")

    # relationships 合并去重（按 target+nature 去重）
    merged["relationships"] = _merge_rel_list(merged, new, "relationships")

    return merged


def _merge_set_list(old: dict, new: dict, key: str) -> list:
    """合并两个 dict 中同名 key 的列表，去重返回。"""
    old_vals = set(old.get(key) or [])
    new_vals = set(new.get(key) or [])
    return list(old_vals | new_vals)


def _merge_rel_list(old: dict, new: dict, key: str) -> list:
    """合并关系列表，按 (target, nature) 去重。"""
    seen = set()
    result = []
    for rel in (old.get(key) or []) + (new.get(key) or []):
        k = (rel.get("target", ""), rel.get("nature", ""))
        if k not in seen:
            seen.add(k)
            result.append(rel)
    return result


def merge_settings(existing: list, new_items: list) -> list:
    """
    合并设定列表，同名设定取更长的 description，合并关联关系。
    """
    by_name = {}
    for s in existing:
        by_name[s["name"]] = s.copy()

    for s in new_items:
        name = s.get("name", "")
        if not name:
            continue

        if name in by_name:
            old = by_name[name]
            # 取更长的描述
            old_desc = old.get("description") or ""
            new_desc = s.get("description") or ""
            if len(new_desc) > len(old_desc):
                old["description"] = new_desc
            # 取更具体的类型
            old_type = old.get("type") or ""
            new_type = s.get("type") or ""
            if new_type and not old_type:
                old["type"] = new_type
            # 合并关联关系
            old["related_characters"] = _merge_set_list(old, s, "related_characters")
            old["related_settings"] = _merge_set_list(old, s, "related_settings")
            by_name[name] = old
        else:
            by_name[name] = s.copy()

    return list(by_name.values())


def merge_events(existing: list, new_items: list) -> list:
    """
    合并事件列表，同名事件合并 participants 和 cause。
    """
    by_name = {}
    for e in existing:
        by_name[e["name"]] = e.copy()

    for e in new_items:
        name = e.get("name", "")
        if not name:
            continue

        if name in by_name:
            old = by_name[name]
            # 合并 participants（并集）
            old["participants"] = list(set(
                (old.get("participants") or []) + (e.get("participants") or [])
            ))
            # 取更长的 description
            old_desc = old.get("description") or ""
            new_desc = e.get("description") or ""
            if len(new_desc) > len(old_desc):
                old["description"] = new_desc
            # 合并 cause（并集）
            old["cause"] = list(set(
                (old.get("cause") or []) + (e.get("cause") or [])
            ))
            # 取 time（如果原来没有）
            if not old.get("time") and e.get("time"):
                old["time"] = e["time"]
            # 取 location（如果原来没有）
            if not old.get("location") and e.get("location"):
                old["location"] = e["location"]
        else:
            by_name[name] = e.copy()

    return list(by_name.values())


def _build_summary(title: str, chapter_summaries: list, characters: list, settings: list) -> str:
    """从各章摘要构建全书摘要。"""
    parts = []
    if title:
        parts.append(f"《{title}》")
    parts.append(f"共提取 {len(characters)} 个人物、{len(settings)} 个设定。")

    if chapter_summaries:
        # 合并各章摘要（限制总长度）
        combined = "；".join(chapter_summaries[:10])
        if len(chapter_summaries) > 10:
            combined += f"（共 {len(chapter_summaries)} 章）"
        parts.append(combined)

    return "".join(parts)


# ── 增量分析功能 ──────────────────────────────────────────────────

def detect_existing_analysis(title: str) -> dict:
    """
    检测 vault 中是否已有该书的分析结果。

    Args:
        title: 作品名

    Returns:
        {
            "exists": True/False,
            "chapters_analyzed": ["第1章", "第2章", ...],
            "characters": [...],
            "settings": [...],
            "events": [...]
        }
    """
    book_dir = VAULT_DIR / _safe_filename(title)

    if not book_dir.exists():
        return {
            "exists": False,
            "chapters_analyzed": [],
            "characters": [],
            "settings": [],
            "events": []
        }

    # 读取增量状态文件
    state = _load_incremental_state(title)

    # 从 vault 读取已有的人物/设定/事件
    characters = _read_existing_cards(book_dir / "characters", "character")
    settings = _read_existing_cards(book_dir / "settings", "setting")
    events = _read_existing_cards(book_dir / "events", "event")

    return {
        "exists": True,
        "chapters_analyzed": state.get("chapters_analyzed", []),
        "characters": characters,
        "settings": settings,
        "events": events
    }


def _load_incremental_state(title: str) -> dict:
    """加载增量分析状态文件。"""
    state_file = _get_state_file_path(title)
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_incremental_state(title: str, state: dict):
    """保存增量分析状态文件。"""
    state_file = _get_state_file_path(title)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _get_state_file_path(title: str) -> Path:
    """获取增量状态文件路径。"""
    return VAULT_DIR / _safe_filename(title) / ".incremental_state.json"


def _read_existing_cards(cards_dir: Path, card_type: str) -> list:
    """从 vault 目录读取已有的卡片数据。"""
    if not cards_dir.exists():
        return []

    cards = []
    for md_file in cards_dir.glob("*.md"):
        try:
            content = md_file.read_text(encoding='utf-8')
            card = _parse_card_md(content, card_type)
            if card:
                cards.append(card)
        except Exception:
            continue

    return cards


def _parse_card_md(content: str, card_type: str) -> dict:
    """解析卡片 .md 文件，提取结构化数据。"""
    lines = content.strip().split('\n')
    if not lines:
        return None

    # 简单解析：从文件名和内容中提取信息
    card = {"type": card_type}

    # 提取标题（第一行 # 开头）
    for line in lines:
        if line.startswith('# '):
            card["name"] = line[2:].strip()
            break

    if not card.get("name"):
        return None

    # 提取各部分内容
    current_section = None
    section_content = []

    for line in lines[1:]:
        if line.startswith('## '):
            if current_section and section_content:
                _assign_section(card, current_section, section_content)
            current_section = line[3:].strip()
            section_content = []
        elif line.startswith('- '):
            section_content.append(line[2:].strip())
        elif current_section:
            section_content.append(line.strip())

    if current_section and section_content:
        _assign_section(card, current_section, section_content)

    return card


def _assign_section(card: dict, section: str, content: list):
    """将解析的内容分配到卡片的对应字段。"""
    section_lower = section.lower()

    if '身份' in section_lower:
        card["identity"] = '\n'.join(content)
    elif '性格' in section_lower:
        card["personality"] = '\n'.join(content)
    elif '关系' in section_lower:
        # 解析关系链接
        relationships = []
        for item in content:
            if '|' in item:
                # wikilink 格式：[[path|name]] — nature
                parts = item.split('—')
                if len(parts) == 2:
                    target = parts[0].split('|')[-1].strip().rstrip(']').strip('[')
                    relationships.append({
                        "target": target,
                        "nature": parts[1].strip()
                    })
        card["relationships"] = relationships
    elif '类型' in section_lower:
        card["type"] = content[0] if content else "其他"
    elif '描述' in section_lower or '简介' in section_lower:
        card["description"] = '\n'.join(content)


def build_initial_context_for_incremental(existing_data: dict) -> tuple[list, list, list]:
    """
    从已有数据构建初始上下文，用于增量分析。

    Args:
        existing_data: detect_existing_analysis() 的返回值

    Returns:
        (known_characters, known_settings, known_events)
    """
    return (
        existing_data.get("characters", []),
        existing_data.get("settings", []),
        existing_data.get("events", [])
    )


def analyze_chaptered_incremental(text: str, title: str = None,
                                   chunk_size: int = 5000,
                                   start_chapter: int = None,
                                   end_chapter: int = None,
                                   on_chapter_start=None,
                                   on_chapter_done=None) -> dict:
    """
    增量分章分析长文本。

    流程：
    1. 检测已有分析结果
    2. 切分章节（可指定范围）
    3. 逐章分析，携带已知上下文
    4. 合并新旧结果
    5. 更新状态文件

    Args:
        text: 纯文本内容
        title: 作品名
        chunk_size: 无章节标记时每块的目标字数
        start_chapter: 起始章节编号（从 1 开始，None 表示从头开始）
        end_chapter: 结束章节编号（None 表示到末尾）
        on_chapter_start: 回调函数
        on_chapter_done: 回调函数

    Returns:
        合并后的分析结果 dict
    """
    # Step 1: 检测已有分析结果
    existing = detect_existing_analysis(title)
    existing_chapters = set(existing.get("chapters_analyzed", []))

    if existing["exists"]:
        print(f"[增量] 检测到已有分析结果：{len(existing_chapters)} 章已分析")
        print(f"       人物: {len(existing['characters'])} 个 | 设定: {len(existing['settings'])} 个 | 事件: {len(existing['events'])} 个")
    else:
        print("[增量] 无已有分析结果，将从头开始")

    # Step 2: 切分章节
    chapters = split_chapters(text, chunk_size=chunk_size)
    if not chapters:
        raise ValueError("文本切分结果为空")

    print(f"[分章] {get_split_summary(chapters)}")

    # 筛选需要分析的章节
    chapters_to_analyze = _filter_chapters(
        chapters, existing_chapters, start_chapter, end_chapter
    )

    if not chapters_to_analyze:
        print("[增量] 所有章节已分析，无需重复分析")
        return _build_result_from_existing(existing, title)

    print(f"[增量] 需分析 {len(chapters_to_analyze)} 个新章节")

    # Step 3: 构建初始上下文
    known_characters, known_settings, known_events = build_initial_context_for_incremental(existing)

    # Step 4: 逐章分析
    new_characters = []
    new_settings = []
    new_events = []
    new_chapter_summaries = []

    for i, chapter in enumerate(chapters_to_analyze):
        if on_chapter_start:
            on_chapter_start(chapter)

        print(f"[分析] 第 {i+1}/{len(chapters_to_analyze)} 章: {chapter.title} ({chapter.char_count} 字)")

        try:
            result = analyze_chapter(
                text=chapter.text,
                known_characters=known_characters + new_characters,
                known_settings=known_settings + new_settings,
                known_events=known_events + new_events,
                chapter_title=chapter.title,
            )
        except (ValueError, RuntimeError) as e:
            print(f"  ⚠️ 第 {i+1} 章分析失败: {e}，跳过")
            continue

        # 收集本章结果
        chapter_chars = result.get("characters", [])
        chapter_settings = result.get("settings", [])
        chapter_events = result.get("events", [])
        ch_summary = result.get("chapter_summary", "")

        if ch_summary:
            new_chapter_summaries.append({
                "title": chapter.title,
                "summary": ch_summary
            })

        print(f"  [OK] 新增: {len(chapter_chars)} 人物, {len(chapter_settings)} 设定, {len(chapter_events)} 事件")

        # 合并到新数据列表
        new_characters = merge_characters(new_characters, chapter_chars)
        new_settings = merge_settings(new_settings, chapter_settings)
        new_events = merge_events(new_events, chapter_events)

        # 标记本章已分析
        existing_chapters.add(chapter.title)

        if on_chapter_done:
            on_chapter_done(chapter, result)

    # Step 5: 合并新旧结果
    all_characters = merge_characters(existing["characters"], new_characters)
    all_settings = merge_settings(existing["settings"], new_settings)
    all_events = merge_events(existing["events"], new_events)

    # 构建章节摘要（合并新旧）
    all_chapter_summaries = existing.get("chapters", []) + new_chapter_summaries

    # Step 6: 更新状态文件
    state = {
        "chapters_analyzed": list(existing_chapters),
        "total_chapters": len(chapters),
        "last_analyzed": _get_timestamp()
    }
    _save_incremental_state(title, state)

    # Step 7: 构建最终结果
    summary = _build_summary(title, [s["summary"] for s in all_chapter_summaries],
                            all_characters, all_settings)

    return {
        "title": title or "未命名作品",
        "characters": all_characters,
        "settings": all_settings,
        "events": all_events,
        "summary": summary,
        "chapters": all_chapter_summaries,
        "incremental": True
    }


def _filter_chapters(chapters: list, existing_chapters: set,
                     start_chapter: int = None, end_chapter: int = None) -> list:
    """筛选需要分析的章节。"""
    filtered = []

    for i, chapter in enumerate(chapters):
        chapter_num = i + 1

        # 检查是否在指定范围内
        if start_chapter and chapter_num < start_chapter:
            continue
        if end_chapter and chapter_num > end_chapter:
            continue

        # 检查是否已分析过
        if chapter.title in existing_chapters:
            continue

        filtered.append(chapter)

    return filtered


def _build_result_from_existing(existing: dict, title: str) -> dict:
    """从已有数据构建结果。"""
    chapter_summaries = [{"title": ch, "summary": ""} for ch in existing.get("chapters_analyzed", [])]

    summary = _build_summary(title, [s["summary"] for s in chapter_summaries],
                            existing.get("characters", []),
                            existing.get("settings", []))

    return {
        "title": title or "未命名作品",
        "characters": existing.get("characters", []),
        "settings": existing.get("settings", []),
        "events": existing.get("events", []),
        "summary": summary,
        "chapters": chapter_summaries,
        "incremental": True
    }


def _get_timestamp() -> str:
    """获取当前时间戳。"""
    from datetime import datetime
    return datetime.now().isoformat()


def _safe_filename(name: str) -> str:
    """将名称转为安全的文件名（去除非法字符）。"""
    illegal = '<>:"/\\|?*'
    safe = name
    for ch in illegal:
        safe = safe.replace(ch, "_")
    return safe.strip()
