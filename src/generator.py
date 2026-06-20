"""
Story Wiki - 笔记生成模块
将 AI 分析的 JSON 数据转换为 Obsidian Markdown 文件。
生成人物、设定之间的交叉引用链接，确保 Graph View 中节点互相连接。
支持增量写入：更新已有文件而非覆盖。
"""
from pathlib import Path
from datetime import datetime

from src.config import VAULT_DIR


def generate_vault(analysis: dict, output_dir: Path = None) -> list[str]:
    """
    根据分析结果生成 Obsidian 笔记文件。

    Args:
        analysis: AI 分析结果 dict
        output_dir: 输出目录（默认使用配置的 VAULT_DIR）

    Returns:
        生成的文件路径列表
    """
    output = output_dir or VAULT_DIR
    title = analysis.get("title", "未命名作品")
    characters = analysis.get("characters", [])
    settings = analysis.get("settings", [])
    events = analysis.get("events", [])
    summary = analysis.get("summary", "")

    # 创建作品目录
    book_dir = output / _safe_filename(title)
    char_dir = book_dir / "characters"
    setting_dir = book_dir / "settings"
    event_dir = book_dir / "events"
    for d in [char_dir, setting_dir, event_dir]:
        d.mkdir(parents=True, exist_ok=True)

    generated_files = []

    for char in characters:
        generated_files.append(str(_write_character_card(char, char_dir, title, events)))

    for setting in settings:
        generated_files.append(str(_write_setting_card(setting, setting_dir, title)))

    for event in events:
        generated_files.append(str(_write_event_card(event, event_dir, title)))

    generated_files.append(str(_write_book_index(title, summary, characters, settings, events, book_dir)))

    return generated_files


# ── 辅助函数 ──────────────────────────────────────────────────

def _frontmatter(fields: list[str]) -> list[str]:
    """构建 frontmatter 块（含开头结尾 ---），自动过滤 None 值。"""
    return ["---"] + [f for f in fields if f is not None] + ["---"]


def _wikilink_section(title: str, links: list[str]) -> list[str]:
    """构建一个 wikilink 列表段落，如 '## 关联人物' + '- [[xxx]]' 列表。"""
    if not links:
        return []
    lines = [f"## {title}"]
    for link in links:
        lines.append(f"- {link}")
    lines.append("")
    return lines


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ── 状态图标映射 ──────────────────────────────────────────────

_STATUS_ICONS = {
    "活跃": "🟢",
    "已故": "⚫",
    "失踪": "🔴",
    "退场": "🟡",
    "未知": "⚪",
}


def _build_status_bar(char: dict) -> list[str]:
    """
    构建人物状态栏。
    格式：> 🟢 活跃 | 阵营：荣国府 | 定位：主角 · 女主
    """
    status = char.get("status") or "未知"
    icon = _STATUS_ICONS.get(status, "⚪")
    faction = char.get("faction") or ""
    role_tags = char.get("role_tags") or []

    parts = [f"{icon} {status}"]
    if faction:
        parts.append(f"阵营：{faction}")
    if role_tags:
        parts.append(f"定位：{' · '.join(role_tags)}")

    return ["> " + " | ".join(parts), ""]


def _build_setting_status_bar(setting: dict, related_chars: list) -> list[str]:
    """
    构建设定状态栏。
    格式：> 类型：地点 | 关联人物：6
    """
    stype = setting.get("type") or setting.get("setting_type") or "其他"
    char_count = len(related_chars) if related_chars else 0

    parts = [f"类型：{stype}"]
    if char_count > 0:
        parts.append(f"关联人物：{char_count}")

    return ["> " + " | ".join(parts), ""]


def _build_event_status_bar(event: dict) -> list[str]:
    """
    构建事件状态栏。
    格式：> 📍 大观园 | 👥 5人参与 | 🔗 前置：2个事件
    """
    location = event.get("location") or ""
    participants = event.get("participants") or []
    cause = event.get("cause") or []

    parts = []
    if location:
        parts.append(f"📍 {location}")
    if participants:
        parts.append(f"👥 {len(participants)}人参与")
    if cause:
        parts.append(f"🔗 前置：{len(cause)}个事件")

    if not parts:
        return []
    return ["> " + " | ".join(parts), ""]


def _build_achievements(char_name: str, events: list) -> list[str]:
    """
    构建人物高光时刻列表。
    从 events 中筛选该人物参与的事件。
    """
    if not events:
        return []

    char_events = [
        e for e in events
        if char_name in (e.get("participants") or [])
    ]

    if not char_events:
        return []

    lines = ["## 🏆 高光时刻"]
    for e in char_events[:8]:  # 最多显示 8 个
        name = e.get("name", "未知")
        desc = e.get("description") or ""
        # 截断过长描述
        if len(desc) > 30:
            desc = desc[:30] + "..."
        lines.append(f"- [[events/{name}|{name}]] — {desc}")
    lines.append("")
    return lines


def _build_quotes_section(char: dict) -> list[str]:
    """
    构建语录区域。
    """
    quotes = char.get("quotes") or []
    if not quotes:
        return []

    lines = ["## 💬 经典语录"]
    for q in quotes[:5]:  # 最多显示 5 条
        lines.append(f'> "{q}"')
    lines.append("")
    return lines


def _build_character_mermaid(char: dict) -> list[str]:
    """
    构建人物关系子图（Mermaid）。
    只展示该人物的直接关系，最多 8 条。
    """
    name = char.get("name", "")
    relationships = char.get("relationships") or []

    if not relationships or not name:
        return []

    lines = ["## 🕸️ 关系网", "", "```mermaid", "graph LR"]

    # 只取前 8 条关系
    for r in relationships[:8]:
        target = r.get("target", "")
        nature = r.get("nature", "")
        if not target:
            continue
        a_id = _safe_filename(name)
        b_id = _safe_filename(target)
        lines.append(f'    {a_id}["{name}"] -- "{nature}" --> {b_id}["{target}"]')

    lines.append("```")
    lines.append("")
    return lines


# ── 人物卡片 ──────────────────────────────────────────────────

def _write_character_card(char: dict, char_dir: Path, origin: str, events: list = None) -> Path:
    """生成单个人物卡片 .md 文件，包含状态栏、人际关系、关联设定、高光时刻、语录和关系子图。"""
    name = char.get("name", "未知")
    aliases = char.get("aliases", []) or []
    identity = char.get("identity") or "未知"
    personality = char.get("personality") or "未知"
    gender = char.get("gender") or "未知"
    faction = char.get("faction") or ""
    relationships = char.get("relationships", []) or []
    related_settings = char.get("related_settings", []) or []
    role_tags = char.get("role_tags", []) or []

    # frontmatter
    fm = _frontmatter([
        "type: character",
        "source: analyzed",
        f"origin: {origin}",
        f"gender: {gender}",
        f"faction: {faction}" if faction else None,
        f"aliases: [{', '.join(aliases)}]" if aliases else None,
        f"role_tags: [{', '.join(role_tags)}]" if role_tags else None,
        f"tags: [character, {_safe_filename(faction)}]" if faction else "tags: [character]",
        f"created: {_today()}",
    ])

    # 正文
    body = [
        "",
        f"# {name}",
        "",
    ]

    # 状态栏
    body += _build_status_bar(char)

    # 身份和性格
    body += [
        "## 身份",
        identity,
        "",
        "## 性格",
        personality,
        "",
    ]

    # 人际关系（wikilink → characters/）
    rel_links = [
        f"[[characters/{r['target']}|{r['target']}]] — {r.get('nature', '未知')}"
        for r in relationships
    ]
    body += _wikilink_section("人际关系", rel_links)

    # 关联设定（wikilink → settings/）
    setting_links = [f"[[settings/{s}|{s}]]" for s in related_settings]
    body += _wikilink_section("关联设定", setting_links)

    # 高光时刻
    body += _build_achievements(name, events or [])

    # 语录
    body += _build_quotes_section(char)

    # 关系子图
    body += _build_character_mermaid(char)

    content = "\n".join(fm) + "\n".join(body)
    filepath = char_dir / f"{_safe_filename(name)}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── 设定卡片 ──────────────────────────────────────────────────

def _write_setting_card(setting: dict, setting_dir: Path, origin: str) -> Path:
    """生成单个设定卡片 .md 文件，包含状态栏、关联人物和关联设定链接。"""
    name = setting.get("name", "未知")
    stype = setting.get("type") or setting.get("setting_type") or "其他"
    description = setting.get("description") or "暂无描述"
    related_characters = setting.get("related_characters", []) or []
    related_settings = setting.get("related_settings", []) or []

    # frontmatter
    fm = _frontmatter([
        "type: setting",
        "source: analyzed",
        f"origin: {origin}",
        f"setting_type: {stype}",
        f"tags: [setting, {_safe_filename(stype)}]",
        f"created: {_today()}",
    ])

    # 正文
    body = [
        "",
        f"# {name}",
        "",
    ]

    # 状态栏
    body += _build_setting_status_bar(setting, related_characters)

    # 类型和描述
    body += [
        f"**类型**：{stype}",
        "",
        description,
        "",
    ]

    # 关联人物（wikilink → characters/）
    char_links = [f"[[characters/{c}|{c}]]" for c in related_characters]
    body += _wikilink_section("关联人物", char_links)

    # 关联设定（wikilink → settings/，排除自引用）
    setting_links = [f"[[settings/{s}|{s}]]" for s in related_settings if s != name]
    body += _wikilink_section("关联设定", setting_links)

    content = "\n".join(fm) + "\n".join(body)
    filepath = setting_dir / f"{_safe_filename(name)}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── 事件卡片 ──────────────────────────────────────────────────

def _write_event_card(event: dict, event_dir: Path, origin: str) -> Path:
    """生成单个事件卡片 .md 文件，包含状态栏、参与人物、前置事件和关联设定链接。"""
    name = event.get("name", "未知")
    time = event.get("time") or "未知"
    participants = event.get("participants", []) or []
    location = event.get("location") or ""
    description = event.get("description") or "暂无描述"
    cause = event.get("cause", []) or []
    chapter = event.get("chapter") or ""

    # frontmatter
    fm = _frontmatter([
        "type: event",
        "source: analyzed",
        f"origin: {origin}",
        f"time: {time}",
        f"chapter: {chapter}" if chapter else None,
        f"tags: [event]",
        f"created: {_today()}",
    ])

    # 正文
    body = [
        "",
        f"# {name}",
        "",
    ]

    # 状态栏
    body += _build_event_status_bar(event)

    # 时间和描述
    body += [
        f"**时间**：{time}",
        "",
        description,
        "",
    ]

    # 参与人物（wikilink → characters/）
    char_links = [f"[[characters/{c}|{c}]]" for c in participants]
    body += _wikilink_section("参与人物", char_links)

    # 发生地点（wikilink → settings/）
    if location:
        body += _wikilink_section("发生地点", [f"[[settings/{location}|{location}]]"])

    # 前置事件（wikilink → events/）
    cause_links = [f"[[events/{c}|{c}]]" for c in cause]
    body += _wikilink_section("前置事件", cause_links)

    content = "\n".join(fm) + "\n".join(body)
    filepath = event_dir / f"{_safe_filename(name)}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── 作品索引 ──────────────────────────────────────────────────

def _write_book_index(
    title: str, summary: str, characters: list, settings: list,
    events: list, book_dir: Path
) -> Path:
    """生成作品索引 _index.md，包含人物、设定、事件、关系图谱和时间线。"""
    fm = _frontmatter([
        "type: book",
        "tags: [book]",
        f"created: {_today()}",
    ])

    body = ["", f"# {title}", ""]

    if summary:
        body += [f"> {summary}", ""]

    # 人物
    body += _wikilink_section("人物", [
        f"[[characters/{c.get('name', '?')}|{c.get('name', '?')}]]"
        + (f" — {c['identity']}" if c.get("identity") else "")
        for c in characters
    ])

    # 设定
    body += _wikilink_section("设定", [
        f"[[settings/{s.get('name', '?')}|{s.get('name', '?')}]]"
        + (f" — {(s.get('description') or '')[:30]}" if s.get("description") else "")
        for s in settings
    ])

    # 事件
    if events:
        body += _wikilink_section("事件", [
            f"[[events/{e.get('name', '?')}|{e.get('name', '?')}]]"
            + (f" — {e.get('time', '')}" if e.get("time") else "")
            for e in events
        ])

    # Mermaid 关系图谱（人物关系网络）
    mermaid = _build_mermaid_graph(characters)
    if mermaid:
        body += ["", "## 关系图谱", "", "```mermaid"]
        body += mermaid
        body += ["```", ""]

    # 时间线（事件按时间排列）
    if events:
        timeline = _build_mermaid_timeline(title, events)
        if timeline:
            body += ["## 时间线", "", "```mermaid"]
            body += timeline
            body += ["```", ""]

    content = "\n".join(fm) + "\n".join(body)
    filepath = book_dir / "_index.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _build_mermaid_graph(characters: list) -> list[str]:
    """从人物关系数组生成 Mermaid graph 语法。人物数 > 30 时只取主要人物。"""
    # 按关系数量排序，取 top 15
    ranked = sorted(characters, key=lambda c: len(c.get("relationships") or []), reverse=True)
    top_chars = ranked[:15]
    char_names = {c.get("name", "") for c in top_chars}

    lines = ["graph LR"]
    seen_edges = set()

    for c in top_chars:
        name = c.get("name", "?")
        for r in (c.get("relationships") or []):
            target = r.get("target", "")
            nature = r.get("nature", "")
            # 只展示双方都在 top 15 中的关系
            if target not in char_names:
                continue
            edge_key = tuple(sorted([name, target]))
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            # Mermaid node id 去掉特殊字符
            a_id = _safe_filename(name)
            b_id = _safe_filename(target)
            lines.append(f'    {a_id}["{name}"] -- "{nature}" --> {b_id}["{target}"]')

    # 如果没有任何边，返回空
    if len(lines) <= 1:
        return []
    return lines


def _build_mermaid_timeline(title: str, events: list) -> list[str]:
    """从事件列表生成 Mermaid timeline 语法，按章节分组。"""
    # 按 chapter 分组
    by_chapter: dict[str, list[dict]] = {}
    for e in events:
        ch = e.get("chapter") or "其他"
        by_chapter.setdefault(ch, []).append(e)

    lines = [f'timeline', f'    title {title}']

    for ch, ch_events in by_chapter.items():
        lines.append(f'    section {ch}')
        for e in ch_events:
            name = e.get("name", "?")
            participants = "、".join(e.get("participants", [])[:3])
            label = f"{name}" if not participants else f"{name} : {participants}"
            lines.append(f'        {label}')

    return lines


def _safe_filename(name: str) -> str:
    """将名称转为安全的文件名（去除非法字符）。"""
    illegal = '<>:"/\\|?*'
    safe = name
    for ch in illegal:
        safe = safe.replace(ch, "_")
    return safe.strip()


# ── 增量写入功能 ──────────────────────────────────────────────────

def generate_vault_incremental(analysis: dict, output_dir: Path = None) -> list[str]:
    """
    根据分析结果生成 Obsidian 笔记文件（增量模式）。

    增量模式逻辑：
    - 人物/设定/事件卡片：已存在则更新，不存在则创建
    - 索引文件：始终重新生成（包含所有内容）
    - 章节摘要：追加到已有列表

    Args:
        analysis: AI 分析结果 dict（包含 incremental: True 标记）
        output_dir: 输出目录（默认使用配置的 VAULT_DIR）

    Returns:
        生成/更新的文件路径列表
    """
    output = output_dir or VAULT_DIR
    title = analysis.get("title", "未命名作品")
    characters = analysis.get("characters", [])
    settings = analysis.get("settings", [])
    events = analysis.get("events", [])
    summary = analysis.get("summary", "")

    # 创建作品目录
    book_dir = output / _safe_filename(title)
    char_dir = book_dir / "characters"
    setting_dir = book_dir / "settings"
    event_dir = book_dir / "events"
    for d in [char_dir, setting_dir, event_dir]:
        d.mkdir(parents=True, exist_ok=True)

    generated_files = []

    # 增量写入人物卡片
    for char in characters:
        filepath = _write_character_card_incremental(char, char_dir, title, events)
        generated_files.append(str(filepath))

    # 增量写入设定卡片
    for setting in settings:
        filepath = _write_setting_card_incremental(setting, setting_dir, title)
        generated_files.append(str(filepath))

    # 增量写入事件卡片
    for event in events:
        filepath = _write_event_card_incremental(event, event_dir, title)
        generated_files.append(str(filepath))

    # 始终重新生成索引文件
    generated_files.append(str(_write_book_index(title, summary, characters, settings, events, book_dir)))

    return generated_files


def _write_character_card_incremental(char: dict, char_dir: Path, origin: str, events: list = None) -> Path:
    """
    增量写入人物卡片：已存在则更新，不存在则创建。

    更新策略：
    - 基本信息：取更长的值
    - 关系列表：合并去重
    - 别名列表：合并去重
    - role_tags/status/quotes：合并去重
    """
    name = char.get("name", "未知")
    filepath = char_dir / f"{_safe_filename(name)}.md"

    if filepath.exists():
        # 已存在 → 读取并合并
        existing = _read_character_from_file(filepath)
        if existing:
            char = _merge_character_data(existing, char)

    # 写入（新建或更新后）
    return _write_character_card(char, char_dir, origin, events)


def _write_setting_card_incremental(setting: dict, setting_dir: Path, origin: str) -> Path:
    """
    增量写入设定卡片：已存在则更新，不存在则创建。

    更新策略：
    - 描述：取更长的值
    - 关联列表：合并去重
    """
    name = setting.get("name", "未知")
    filepath = setting_dir / f"{_safe_filename(name)}.md"

    if filepath.exists():
        existing = _read_setting_from_file(filepath)
        if existing:
            setting = _merge_setting_data(existing, setting)

    return _write_setting_card(setting, setting_dir, origin)


def _write_event_card_incremental(event: dict, event_dir: Path, origin: str) -> Path:
    """
    增量写入事件卡片：已存在则更新，不存在则创建。

    更新策略：
    - 描述：取更长的值
    - 参与者列表：合并去重
    - 因果链：合并去重
    """
    name = event.get("name", "未知")
    filepath = event_dir / f"{_safe_filename(name)}.md"

    if filepath.exists():
        existing = _read_event_from_file(filepath)
        if existing:
            event = _merge_event_data(existing, event)

    return _write_event_card(event, event_dir, origin)


def _read_character_from_file(filepath: Path) -> dict:
    """从文件读取人物数据。"""
    try:
        content = filepath.read_text(encoding='utf-8')
        return _parse_character_md(content)
    except Exception:
        return None


def _read_setting_from_file(filepath: Path) -> dict:
    """从文件读取设定数据。"""
    try:
        content = filepath.read_text(encoding='utf-8')
        return _parse_setting_md(content)
    except Exception:
        return None


def _read_event_from_file(filepath: Path) -> dict:
    """从文件读取事件数据。"""
    try:
        content = filepath.read_text(encoding='utf-8')
        return _parse_event_md(content)
    except Exception:
        return None


def _parse_character_md(content: str) -> dict:
    """解析人物卡片 .md 文件。"""
    lines = content.strip().split('\n')
    char = {"type": "character"}

    # 提取标题
    for line in lines:
        if line.startswith('# '):
            char["name"] = line[2:].strip()
            break

    if not char.get("name"):
        return None

    # 提取 frontmatter 中的字段
    in_frontmatter = False
    for line in lines:
        if line.strip() == '---':
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            if line.startswith('gender:'):
                char["gender"] = line.split(':', 1)[1].strip()
            elif line.startswith('faction:'):
                char["faction"] = line.split(':', 1)[1].strip()
            elif line.startswith('aliases:'):
                aliases_str = line.split(':', 1)[1].strip()
                if aliases_str.startswith('[') and aliases_str.endswith(']'):
                    char["aliases"] = [a.strip() for a in aliases_str[1:-1].split(',')]
            elif line.startswith('role_tags:'):
                tags_str = line.split(':', 1)[1].strip()
                if tags_str.startswith('[') and tags_str.endswith(']'):
                    char["role_tags"] = [t.strip() for t in tags_str[1:-1].split(',')]

    # 提取状态栏（> 🟢 活跃 | 阵营：xxx | 定位：xxx）
    for line in lines:
        if line.startswith('> '):
            status_text = line[2:]
            # 提取状态
            for status in ["活跃", "已故", "失踪", "退场", "未知"]:
                if status in status_text:
                    char["status"] = status
                    break

    # 提取各部分内容
    current_section = None
    section_content = []

    for line in lines:
        if line.startswith('## '):
            if current_section and section_content:
                _assign_character_section(char, current_section, section_content)
            current_section = line[3:].strip()
            section_content = []
        elif line.startswith('- '):
            section_content.append(line[2:].strip())
        elif line.startswith('> "') and current_section and '语录' in current_section:
            # 语录行
            quote = line[2:].strip().strip('"')
            if quote:
                section_content.append(quote)
        elif current_section and line.strip():
            section_content.append(line.strip())

    if current_section and section_content:
        _assign_character_section(char, current_section, section_content)

    return char


def _assign_character_section(char: dict, section: str, content: list):
    """将解析的内容分配到人物卡片的对应字段。"""
    section_lower = section.lower()

    if '身份' in section_lower:
        char["identity"] = '\n'.join(content)
    elif '性格' in section_lower:
        char["personality"] = '\n'.join(content)
    elif '关系' in section_lower and '网' not in section_lower:
        relationships = []
        for item in content:
            if '—' in item:
                parts = item.split('—')
                if len(parts) == 2:
                    target = parts[0].split('|')[-1].strip().rstrip(']').strip('[')
                    relationships.append({
                        "target": target,
                        "nature": parts[1].strip()
                    })
        char["relationships"] = relationships
    elif '语录' in section_lower:
        char["quotes"] = content


def _parse_setting_md(content: str) -> dict:
    """解析设定卡片 .md 文件。"""
    lines = content.strip().split('\n')
    setting = {"type": "setting"}

    for line in lines:
        if line.startswith('# '):
            setting["name"] = line[2:].strip()
            break

    if not setting.get("name"):
        return None

    # 提取类型
    for line in lines:
        if line.startswith('**类型**：'):
            setting["setting_type"] = line.split('：', 1)[1].strip()
            break

    # 提取描述（类型行之后的内容）
    in_desc = False
    desc_lines = []
    for line in lines:
        if line.startswith('**类型**：'):
            in_desc = True
            continue
        if in_desc and line.startswith('## '):
            break
        if in_desc and line.strip():
            desc_lines.append(line.strip())

    if desc_lines:
        setting["description"] = '\n'.join(desc_lines)

    return setting


def _parse_event_md(content: str) -> dict:
    """解析事件卡片 .md 文件。"""
    lines = content.strip().split('\n')
    event = {"type": "event"}

    for line in lines:
        if line.startswith('# '):
            event["name"] = line[2:].strip()
            break

    if not event.get("name"):
        return None

    # 提取时间
    for line in lines:
        if line.startswith('**时间**：'):
            event["time"] = line.split('：', 1)[1].strip()
            break

    return event


def _merge_character_data(old: dict, new: dict) -> dict:
    """合并人物数据：取更长的值，合并列表。"""
    merged = new.copy()

    # 文本字段：取更长的
    for key in ["identity", "personality", "faction", "gender", "status"]:
        old_val = old.get(key) or ""
        new_val = new.get(key) or ""
        if len(old_val) > len(new_val):
            merged[key] = old_val

    # 列表字段：合并去重
    for key in ["aliases", "related_settings", "role_tags", "quotes"]:
        old_list = set(old.get(key) or [])
        new_list = set(new.get(key) or [])
        merged[key] = list(old_list | new_list)

    # 关系列表：合并去重（按 target+nature）
    old_rels = old.get("relationships") or []
    new_rels = new.get("relationships") or []
    seen = set()
    merged_rels = []
    for rel in old_rels + new_rels:
        k = (rel.get("target", ""), rel.get("nature", ""))
        if k not in seen:
            seen.add(k)
            merged_rels.append(rel)
    merged["relationships"] = merged_rels

    return merged


def _merge_setting_data(old: dict, new: dict) -> dict:
    """合并设定数据：取更长的描述，合并关联列表。"""
    merged = new.copy()

    # 描述：取更长的
    old_desc = old.get("description") or ""
    new_desc = new.get("description") or ""
    if len(old_desc) > len(new_desc):
        merged["description"] = old_desc

    # 类型：保留旧的（如果新的没有）
    if not merged.get("setting_type") and old.get("setting_type"):
        merged["setting_type"] = old.get("setting_type")

    # 关联列表：合并去重
    for key in ["related_characters", "related_settings"]:
        old_list = set(old.get(key) or [])
        new_list = set(new.get(key) or [])
        merged[key] = list(old_list | new_list)

    return merged


def _merge_event_data(old: dict, new: dict) -> dict:
    """合并事件数据：取更长的描述，合并参与者和因果链。"""
    merged = new.copy()

    # 描述：取更长的
    old_desc = old.get("description") or ""
    new_desc = new.get("description") or ""
    if len(old_desc) > len(new_desc):
        merged["description"] = old_desc

    # 时间：保留旧的（如果新的没有）
    if not merged.get("time") and old.get("time"):
        merged["time"] = old.get("time")

    # 参与者：合并去重
    old_participants = set(old.get("participants") or [])
    new_participants = set(new.get("participants") or [])
    merged["participants"] = list(old_participants | new_participants)

    # 因果链：合并去重
    old_cause = set(old.get("cause") or [])
    new_cause = set(new.get("cause") or [])
    merged["cause"] = list(old_cause | new_cause)

    return merged
