"""
Story Wiki - 分章分析管线
将长文本切分为章节，逐章 AI 分析，合并去重后生成最终结果。
"""
from src.analyzer import analyze_chapter
from src.splitter import Chapter, split_chapters, get_split_summary


def analyze_chaptered(text: str, title: str = None, chunk_size: int = 5000,
                      on_chapter_start=None, on_chapter_done=None) -> dict:
    """
    分章分析长文本。

    流程：
    1. splitter 切分章节
    2. 逐章调用 analyze_chapter（携带已知人物/设定上下文）
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
            )
        except (ValueError, RuntimeError) as e:
            print(f"  ⚠️ 第 {i+1} 章分析失败: {e}，跳过")
            continue

        # 收集本章结果
        new_chars = result.get("characters", [])
        new_settings = result.get("settings", [])
        ch_summary = result.get("chapter_summary", "")

        if ch_summary:
            chapter_summaries.append(ch_summary)

        print(f"  [OK] 新增: {len(new_chars)} 人物, {len(new_settings)} 设定")

        # Step 3: 增量合并（每章合并后更新已知列表，供下一章使用）
        all_characters = merge_characters(all_characters, new_chars)
        all_settings = merge_settings(all_settings, new_settings)

        if on_chapter_done:
            on_chapter_done(chapter, result)

    # Step 4: 构建最终结果
    summary = _build_summary(title, chapter_summaries, all_characters, all_settings)

    return {
        "title": title or "未命名作品",
        "characters": all_characters,
        "settings": all_settings,
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

    # aliases 合并
    old_aliases = set(merged.get("aliases") or [])
    new_aliases = set(new.get("aliases") or [])
    merged["aliases"] = list(old_aliases | new_aliases)

    # relationships 合并去重
    old_rels = merged.get("relationships") or []
    new_rels = new.get("relationships") or []
    rel_keys = set()
    all_rels = []
    for rel in old_rels + new_rels:
        key = (rel.get("target", ""), rel.get("nature", ""))
        if key not in rel_keys:
            rel_keys.add(key)
            all_rels.append(rel)
    merged["relationships"] = all_rels

    return merged


def merge_settings(existing: list, new_items: list) -> list:
    """
    合并设定列表，同名设定取更长的 description。
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
            by_name[name] = old
        else:
            by_name[name] = s.copy()

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
