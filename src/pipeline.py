"""
Story Wiki - 分章分析管线
将长文本切分为章节，逐章 AI 分析，合并去重后生成最终结果。
支持增量分析：追加新章节到已有笔记，不覆盖旧结果。
支持进度显示和分析结果缓存。

优化：
- 复用 src.name_matcher 统一名称匹配与合并
- 修复 _read_existing_cards 缺少 return 的 P0 bug
- _parse_card_md 补齐 gender/faction/aliases/status/role_tags 字段
- 合并函数改用 copy.deepcopy() 避免浅拷贝导致的数据污染
"""
import json
import hashlib
import re
from pathlib import Path

from src.analyzer import analyze_chapter, generate_context_summary
from src.api_client import call_api
from src.splitter import Chapter, split_chapters, get_split_summary
from src.config import VAULT_DIR, CACHE_DIR
from src.logging_setup import get_logger
from src.utils import safe_filename as _safe_filename
from src.merger import (  # noqa: F401 — 保留兼容入口
    merge_characters,
    merge_settings,
    merge_events,
)

logger = get_logger("pipeline")


def analyze_chaptered(text: str, title: str = None, chunk_size: int = 5000,
                      on_chapter_start=None, on_chapter_done=None,
                      use_cache: bool = True) -> dict:
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
        use_cache: 是否使用分析结果缓存（默认 True）

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

    total_chapters = len(chapters)
    logger.info(f"分章完成：{get_split_summary(chapters)}")

    # Step 2: 逐章分析
    all_characters = []   # 累积所有人物
    all_settings = []     # 累积所有设定
    all_events = []       # 累积所有事件
    chapter_summaries = []  # 每章摘要
    context_before_summary = None  # 前文摘要（DeepSeek 建议）

    for i, chapter in enumerate(chapters):
        if on_chapter_start:
            on_chapter_start(chapter)

        # 进度百分比
        progress = (i + 1) / total_chapters * 100
        logger.info(f"{progress:.0f}% ({i+1}/{total_chapters}) — 分析: {chapter.title} ({chapter.char_count} 字)")

        # 尝试从缓存读取
        cached_result = None
        if use_cache:
            cached_result = _get_cached_result(chapter.text, title)
            if cached_result:
                logger.info("命中缓存，跳过 API 调用")

        if cached_result is None:
            try:
                # 使用前文摘要（DeepSeek 建议）
                result = analyze_chapter(
                    text=chapter.text,
                    known_characters=all_characters,
                    known_settings=all_settings,
                    known_events=all_events,
                    chapter_title=chapter.title,
                    context_before_summary=context_before_summary,
                )
                # 写入缓存
                if use_cache:
                    _save_cached_result(chapter.text, title, result)
            except (ValueError, RuntimeError) as e:
                logger.warning(f"第 {i+1} 章分析失败: {e}，跳过")
                continue
        else:
            result = cached_result

        # 收集本章结果
        new_chars = result.get("characters", [])
        new_settings = result.get("settings", [])
        new_events = result.get("events", [])
        ch_summary = result.get("chapter_summary", "")

        if ch_summary:
            chapter_summaries.append(ch_summary)

        logger.info(f"新增: {len(new_chars)} 人物, {len(new_settings)} 设定, {len(new_events)} 事件")

        # Step 3: 增量合并（每章合并后更新已知列表，供下一章使用）
        all_characters = merge_characters(all_characters, new_chars)
        all_settings = merge_settings(all_settings, new_settings)
        all_events = merge_events(all_events, new_events)

        # 生成前文摘要（DeepSeek 建议）
        context_before_summary = generate_context_summary(result)

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


def merge_chapter_summaries(title: str, chapter_summaries: list[str]) -> str:
    """
    用 AI 将各章摘要合并为连贯的全书概要。

    Args:
        title: 作品名
        chapter_summaries: 各章摘要列表

    Returns:
        连贯的全书概要文本
    """
    if not chapter_summaries:
        return ""

    # 如果只有1章，直接返回
    if len(chapter_summaries) == 1:
        return chapter_summaries[0]

    # 限制摘要数量（避免输入过长）
    summaries_to_merge = chapter_summaries[:30]

    system_prompt = f"""你是一个专业的文学作品摘要编辑。
请将以下各章摘要合并为一段连贯、简洁的全书概要。

要求：
1. 保留关键情节和人物发展
2. 使用流畅的叙述语言，不要简单罗列
3. 控制在200-400字之间
4. 如果是《{title}》，请确保概要准确反映作品主旨"""

    summaries_text = "\n".join(f"第{i+1}章：{s}" for i, s in enumerate(summaries_to_merge))
    user_prompt = f"请将以下各章摘要合并为连贯的全书概要：\n\n{summaries_text}"

    try:
        result = call_api(system_prompt, user_prompt)
        # 清理AI返回的结果
        result = result.strip()
        if result.startswith("```") and result.endswith("```"):
            result = result[3:-3].strip()
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]
        return result
    except (RuntimeError, ValueError) as e:
        print(f"  ⚠️ AI合并摘要失败，使用简单拼接: {e}")  # 保留 print（面向用户的 CLI 输出）
        # 回退到简单拼接
        combined = "；".join(summaries_to_merge[:10])
        if len(chapter_summaries) > 10:
            combined += f"（共 {len(chapter_summaries)} 章）"
        return combined


def _build_summary(title: str, chapter_summaries: list, characters: list, settings: list) -> str:
    """从各章摘要构建全书摘要。"""
    parts = []
    if title:
        parts.append(f"《{title}》")
    parts.append(f"共提取 {len(characters)} 个人物、{len(settings)} 个设定。")

    if chapter_summaries:
        # 尝试用 AI 合并各章摘要为连贯概要
        merged_summary = merge_chapter_summaries(title, chapter_summaries)
        if merged_summary:
            parts.append(merged_summary)

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
        except (FileNotFoundError, UnicodeDecodeError, ValueError) as e:
            logger.warning(f"解析卡片文件失败 {md_file.name}: {e}")
            continue

    return cards


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    解析 Obsidian frontmatter 块。

    Returns:
        (frontmatter_dict, 正文内容)
    """
    frontmatter: dict = {}
    if not content.startswith("---"):
        return frontmatter, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return frontmatter, content

    fm_text = parts[1].strip()
    body = parts[2].lstrip("\n")
    current_list_key: str | None = None

    for raw_line in fm_text.split("\n"):
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue
        # 列表项延续
        if line.startswith("  - ") or line.startswith("-\t") or line.startswith(" - "):
            value = line.lstrip(" -").lstrip("\t").strip()
            if current_list_key is not None:
                frontmatter.setdefault(current_list_key, []).append(_coerce_scalar(value))
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            current_list_key = None
            if not value:
                # 接下来可能是列表
                current_list_key = key
                frontmatter.setdefault(key, [])
            else:
                frontmatter[key] = _coerce_scalar(value)
    return frontmatter, body


def _coerce_scalar(value: str):
    """把字符串值转换为合适的标量（去引号、数字等）。"""
    v = value.strip()
    if not v:
        return v
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.startswith("[") and v.endswith("]"):
        # 极简列表语法兼容
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_coerce_scalar(item.strip()) for item in inner.split(",")]
    return v


def _parse_card_md(content: str, card_type: str) -> dict:
    """解析卡片 .md 文件，提取结构化数据。"""
    lines = content.strip().split('\n')
    if not lines:
        return None

    # 简单解析：从文件名和内容中提取信息
    card: dict = {"type": card_type}

    # 1) 解析 frontmatter（补齐 gender/faction/aliases/status/role_tags 等）
    frontmatter, body = _parse_frontmatter(content)
    if frontmatter:
        # 保留所有标量字段，列表字段直接合并
        for k, v in frontmatter.items():
            if k in ("aliases", "role_tags", "related_settings", "related_characters"):
                if isinstance(v, list):
                    card[k] = v
            else:
                if v is not None and v != "":
                    card[k] = v

    # 2) 提取标题（第一行 # 开头），若 frontmatter 中已有 name 优先使用
    if not card.get("name"):
        for line in lines:
            if line.startswith('# '):
                card["name"] = line[2:].strip()
                break

    if not card.get("name"):
        return None

    # 3) 提取各部分内容（仅解析正文，跳过 frontmatter）
    current_section = None
    section_content = []
    for line in body.split('\n'):
        if line.startswith('## '):
            if current_section and section_content:
                _assign_section(card, current_section, section_content)
            current_section = line[3:].strip()
            section_content = []
        elif line.startswith('# '):
            # 一级标题（人物名）跳过，已从 frontmatter 取过 name
            continue
        elif line.startswith('- '):
            section_content.append(line[2:].strip())
        elif current_section is not None:
            stripped = line.strip()
            if stripped:
                section_content.append(stripped)

    if current_section and section_content:
        _assign_section(card, current_section, section_content)

    # 4) frontmatter 中的别名字符串（如 "贾宝玉, 通灵宝玉"）转为列表
    aliases = card.get("aliases")
    if isinstance(aliases, str) and aliases:
        card["aliases"] = [a.strip() for a in re.split(r"[,，;；]", aliases) if a.strip()]
    if "aliases" not in card:
        card["aliases"] = []

    role_tags = card.get("role_tags")
    if isinstance(role_tags, str) and role_tags:
        card["role_tags"] = [a.strip() for a in re.split(r"[,，;；]", role_tags) if a.strip()]
    if "role_tags" not in card:
        card["role_tags"] = []

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
    elif '性别' in section_lower:
        card["gender"] = content[0].strip() if content else None
    elif '势力' in section_lower or '阵营' in section_lower:
        card["faction"] = content[0].strip() if content else None
    elif '状态' in section_lower:
        card["status"] = content[0].strip() if content else None
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
                                   on_chapter_done=None,
                                   use_cache: bool = True) -> dict:
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
        use_cache: 是否使用分析结果缓存（默认 True）

    Returns:
        合并后的分析结果 dict
    """
    # Step 1: 检测已有分析结果
    existing = detect_existing_analysis(title)
    existing_chapters = set(existing.get("chapters_analyzed", []))

    if existing["exists"]:
        logger.info(f"检测到已有分析结果：{len(existing_chapters)} 章已分析")
        logger.info(f"人物: {len(existing['characters'])} 个 | 设定: {len(existing['settings'])} 个 | 事件: {len(existing['events'])} 个")
    else:
        logger.info("无已有分析结果，将从头开始")

    # Step 2: 切分章节
    chapters = split_chapters(text, chunk_size=chunk_size)
    if not chapters:
        raise ValueError("文本切分结果为空")

    logger.info(f"分章完成：{get_split_summary(chapters)}")

    # 筛选需要分析的章节
    chapters_to_analyze = _filter_chapters(
        chapters, existing_chapters, start_chapter, end_chapter
    )

    if not chapters_to_analyze:
        logger.info("所有章节已分析，无需重复分析")
        return _build_result_from_existing(existing, title)

    total_new = len(chapters_to_analyze)
    logger.info(f"需分析 {total_new} 个新章节")

    # Step 3: 构建初始上下文
    known_characters, known_settings, known_events = build_initial_context_for_incremental(existing)

    # Step 4: 逐章分析
    new_characters = []
    new_settings = []
    new_events = []
    new_chapter_summaries = []
    context_before_summary = None  # 前文摘要（DeepSeek 建议）

    for i, chapter in enumerate(chapters_to_analyze):
        if on_chapter_start:
            on_chapter_start(chapter)

        # 进度百分比
        progress = (i + 1) / total_new * 100
        logger.info(f"{progress:.0f}% ({i+1}/{total_new}) — 分析: {chapter.title} ({chapter.char_count} 字)")

        # 尝试从缓存读取
        cached_result = None
        if use_cache:
            cached_result = _get_cached_result(chapter.text, title)
            if cached_result:
                logger.info("命中缓存，跳过 API 调用")

        if cached_result is None:
            try:
                # 使用前文摘要（DeepSeek 建议）
                result = analyze_chapter(
                    text=chapter.text,
                    known_characters=known_characters + new_characters,
                    known_settings=known_settings + new_settings,
                    known_events=known_events + new_events,
                    chapter_title=chapter.title,
                    context_before_summary=context_before_summary,
                )
                # 写入缓存
                if use_cache:
                    _save_cached_result(chapter.text, title, result)
            except (ValueError, RuntimeError) as e:
                logger.warning(f"第 {i+1} 章分析失败: {e}，跳过")
                continue
        else:
            result = cached_result

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

        logger.info(f"新增: {len(chapter_chars)} 人物, {len(chapter_settings)} 设定, {len(chapter_events)} 事件")

        # 合并到新数据列表
        new_characters = merge_characters(new_characters, chapter_chars)
        new_settings = merge_settings(new_settings, chapter_settings)
        new_events = merge_events(new_events, chapter_events)

        # 生成前文摘要（DeepSeek 建议）
        context_before_summary = generate_context_summary(result)

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


# ── 分析结果缓存功能 ──────────────────────────────────────────────────

def _get_text_hash(text: str) -> str:
    """计算文本的 MD5 哈希值，用于缓存键。"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def _get_cache_path(text: str, title: str = None) -> Path:
    """获取缓存文件路径。"""
    text_hash = _get_text_hash(text)
    title_hash = _get_text_hash(title or "unknown")[:8]
    cache_dir = CACHE_DIR / "analysis"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{text_hash}_{title_hash}.json"


def _get_cached_result(text: str, title: str = None) -> dict | None:
    """
    从缓存读取分析结果。

    Args:
        text: 原始文本
        title: 作品名

    Returns:
        缓存的分析结果，如果未命中则返回 None
    """
    cache_path = _get_cache_path(text, title)
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 检查缓存是否有效（7天过期）
            cached_time = data.get("cached_at")
            if cached_time:
                from datetime import datetime, timedelta
                cached_dt = datetime.fromisoformat(cached_time)
                if datetime.now() - cached_dt > timedelta(days=7):
                    return None
            return data.get("result")
    except (json.JSONDecodeError, IOError, KeyError):
        return None


def _save_cached_result(text: str, title: str, result: dict):
    """
    保存分析结果到缓存。

    Args:
        text: 原始文本
        title: 作品名
        result: 分析结果
    """
    cache_path = _get_cache_path(text, title)
    try:
        from datetime import datetime
        data = {
            "result": result,
            "cached_at": datetime.now().isoformat(),
            "text_length": len(text),
            "title": title,
        }
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.warning(f"缓存写入失败: {e}")


def clear_cache():
    """清除所有分析缓存。"""
    cache_dir = CACHE_DIR / "analysis"
    if cache_dir.exists():
        import shutil
        shutil.rmtree(cache_dir)
        logger.info("已清除所有缓存")
    else:
        logger.info("无缓存可清除")



