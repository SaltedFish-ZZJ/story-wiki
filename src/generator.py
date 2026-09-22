"""
Story Wiki - 笔记生成模块
将 AI 分析的 JSON 数据转换为 Obsidian Markdown 文件。
生成人物、设定之间的交叉引用链接，确保 Graph View 中节点互相连接。
支持增量写入：更新已有文件而非覆盖。
"""
from pathlib import Path

from src.config import VAULT_DIR
from src.utils import safe_filename as _safe_filename, frontmatter as _frontmatter, today_str as _today
from src.logging_setup import get_logger

logger = get_logger("generator")


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
    book_dir.mkdir(parents=True, exist_ok=True)
    char_dir = book_dir / "characters"
    setting_dir = book_dir / "settings"
    event_dir = book_dir / "events"

    # 构建实体映射表（name → 子文件夹）
    char_map, setting_map, event_map = _build_entity_maps(characters, settings, events)

    # 创建子文件夹
    char_subfolders = {char_map.get(c.get("name", ""), "其他人物") for c in characters}
    setting_subfolders = {setting_map.get(s.get("name", ""), "概念") for s in settings}
    event_subfolders = {event_map.get(e.get("name", ""), "一般事件") for e in events}

    for sub in char_subfolders:
        (char_dir / sub).mkdir(parents=True, exist_ok=True)
    for sub in setting_subfolders:
        (setting_dir / sub).mkdir(parents=True, exist_ok=True)
    for sub in event_subfolders:
        (event_dir / sub).mkdir(parents=True, exist_ok=True)

    generated_files = []

    for char in characters:
        sub = char_map.get(char.get("name", ""), "其他人物")
        generated_files.append(str(_write_character_card(char, char_dir / sub, title, events, char_map, setting_map, event_map)))

    for setting in settings:
        sub = setting_map.get(setting.get("name", ""), "概念")
        generated_files.append(str(_write_setting_card(setting, setting_dir / sub, title, char_map, setting_map)))

    for event in events:
        sub = event_map.get(event.get("name", ""), "一般事件")
        generated_files.append(str(_write_event_card(event, event_dir / sub, title, char_map, setting_map, event_map)))

    generated_files.append(str(_write_book_index(title, summary, characters, settings, events, book_dir, char_map, setting_map, event_map)))

    # 生成独立时间线页面
    timeline_path = generate_timeline_page(title, events, book_dir, char_map, setting_map, event_map)
    if timeline_path:
        generated_files.append(str(timeline_path))

    return generated_files


# ── 辅助函数 ──────────────────────────────────────────────────

def _wikilink_section(title: str, links: list[str]) -> list[str]:
    """构建一个 wikilink 列表段落，如 '## 关联人物' + '- [[xxx]]' 列表。"""
    if not links:
        return []
    lines = [f"## {title}"]
    for link in links:
        lines.append(f"- {link}")
    lines.append("")
    return lines



def _flatten(items: list) -> list:
    """展平嵌套 list，AI 返回数据中某些字段可能是 list of list。"""
    result = []
    for item in items:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result


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
    格式：> 🔴 高 | 📍 大观园 | 👥 5人参与 | 🔗 前置：2个事件
    """
    importance = event.get("importance") or ""
    location = event.get("location") or ""
    participants = event.get("participants") or []
    cause = event.get("cause") or []

    importance_icons = {"高": "🔴", "中": "🟡", "低": "⚪"}

    parts = []
    if importance:
        icon = importance_icons.get(importance, "⚪")
        parts.append(f"{icon} {importance}")
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
    构建人物高光时刻列表（旧版兼容）。
    """
    return _build_achievements_with_maps(char_name, events, {})


def _build_achievements_with_maps(char_name: str, events: list, event_map: dict) -> list[str]:
    """
    构建人物高光时刻列表。
    从 events 中筛选该人物参与的事件，按重要性排序。
    """
    if not events:
        return []

    char_events = [
        e for e in events
        if char_name in (e.get("participants") or [])
    ]

    if not char_events:
        return []

    # 按重要性排序：高 > 中 > 低 > 未知
    _importance_order = {"高": 3, "中": 2, "低": 1}
    char_events.sort(
        key=lambda e: _importance_order.get(e.get("importance") or "", 0),
        reverse=True
    )

    lines = ["## 🏆 参与事件"]
    for e in char_events[:10]:  # 最多显示 10 个
        ename = e.get("name", "未知")
        desc = e.get("description") or ""
        importance = e.get("importance") or ""
        # 截断过长描述
        if len(desc) > 30:
            desc = desc[:30] + "..."
        importance_tag = f" [{importance}]" if importance else ""
        lines.append(f"- {_event_link(ename, event_map)}{importance_tag} — {desc}")
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


# ── Graph View 颜色分类 ──────────────────────────────────────

_PROTAGONIST_TAGS = {"主角", "女主", "男主", "反派"}
_IMPORTANT_TAGS = {"配角", "导师", "伙伴", "BOSS", "隐藏角色"}
_LOCATION_KEYWORDS = {"地点", "地名", "城市", "国家", "省份", "区域"}
_ORG_KEYWORDS = {"组织", "公司", "势力", "团体", "宗门", "门派", "学院", "帝国"}


def _get_character_color(role_tags: list) -> str:
    """根据 role_tags 返回人物的 Graph View 颜色标识。"""
    tags = set(role_tags or [])
    if tags & _PROTAGONIST_TAGS:
        return "character-protagonist"
    if tags & _IMPORTANT_TAGS:
        return "character-important"
    return "character-minor"


def _get_setting_color(stype: str) -> str:
    """根据设定类型返回设定的 Graph View 颜色标识。"""
    stype = stype or ""
    if any(kw in stype for kw in _LOCATION_KEYWORDS):
        return "setting-location"
    if any(kw in stype for kw in _ORG_KEYWORDS):
        return "setting-organization"
    return "setting-concept"


def _get_event_color(importance: str) -> str:
    """根据重要性返回事件的 Graph View 颜色标识。"""
    if importance == "高":
        return "event-major"
    if importance == "低":
        return "event-minor"
    return "event-normal"


# ── 子文件夹分类 ──────────────────────────────────────────────

def _get_character_subfolder(role_tags: list) -> str:
    """根据 role_tags 返回人物子文件夹名。"""
    tags = set(role_tags or [])
    if tags & _PROTAGONIST_TAGS:
        return "主要人物"
    if tags & _IMPORTANT_TAGS:
        return "次要人物"
    return "其他人物"


def _get_setting_subfolder(stype: str) -> str:
    """根据设定类型返回设定子文件夹名。"""
    stype = stype or ""
    if any(kw in stype for kw in _LOCATION_KEYWORDS):
        return "地点"
    if any(kw in stype for kw in _ORG_KEYWORDS):
        return "组织"
    return "概念"


def _get_event_subfolder(importance: str) -> str:
    """根据重要性返回事件子文件夹名。"""
    if importance == "高":
        return "重大事件"
    return "一般事件"


def _build_entity_maps(characters: list, settings: list, events: list) -> tuple:
    """构建 name→子文件夹 映射表，用于 wikilink 生成。"""
    char_map = {}
    for c in characters:
        name = c.get("name", "")
        if name:
            char_map[name] = _get_character_subfolder(c.get("role_tags", []))

    setting_map = {}
    for s in settings:
        name = s.get("name", "")
        if name:
            setting_map[name] = _get_setting_subfolder(
                s.get("type") or s.get("setting_type") or ""
            )

    event_map = {}
    for e in events:
        name = e.get("name", "")
        if name:
            event_map[name] = _get_event_subfolder(e.get("importance", ""))

    return char_map, setting_map, event_map


def _char_link(name: str, char_map: dict) -> str:
    """生成人物 wikilink，包含子文件夹路径。"""
    sub = char_map.get(name, "其他人物")
    return f"[[characters/{sub}/{name}|{name}]]"


def _setting_link(name, setting_map: dict) -> str:
    """生成设定 wikilink，包含子文件夹路径。自动处理 list 类型输入。"""
    if isinstance(name, list):
        return "、".join(_setting_link(n, setting_map) for n in name) if name else ""
    sub = setting_map.get(name, "概念")
    return f"[[settings/{sub}/{name}|{name}]]"


def _event_link(name: str, event_map: dict) -> str:
    """生成事件 wikilink，包含子文件夹路径。"""
    sub = event_map.get(name, "一般事件")
    return f"[[events/{sub}/{name}|{name}]]"


# ── 人物卡片 ──────────────────────────────────────────────────

def _write_character_card(char: dict, char_dir: Path, origin: str, events: list = None, char_map: dict = None, setting_map: dict = None, event_map: dict = None) -> Path:
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

    char_map = char_map or {}
    setting_map = setting_map or {}
    event_map = event_map or {}

    # frontmatter
    fm = _frontmatter([
        "type: character",
        f"color: {_get_character_color(role_tags)}",  # Graph View 分色
        "source: analyzed",
        f"origin: {origin}",
        f"gender: {gender}",
        f"faction: {faction}" if faction else None,
        f"aliases: [{', '.join(aliases)}]" if aliases else None,
        f"role_tags: [{', '.join(role_tags)}]" if role_tags else None,
        f"tags: [character]" if not faction else f"tags: [character, {_safe_filename(faction).replace('/', '_')}]",
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

    # 人际关系（wikilink → characters/{子文件夹}/，去重 + top 20）
    rel_map: dict[str, list[str]] = {}
    for r in relationships:
        target = r.get("target", "")
        nature = r.get("nature", "未知")
        if target:
            rel_map.setdefault(target, []).append(nature)
    # 按关系条数降序，取 top 20
    sorted_rels = sorted(rel_map.items(), key=lambda x: len(x[1]), reverse=True)[:20]
    rel_links = []
    for target, natures in sorted_rels:
        # 合并重复关系词，去重后拼接
        unique_natures = list(dict.fromkeys(natures))  # 保序去重
        nature_str = "、".join(unique_natures[:3])  # 最多显示 3 种关系
        if len(unique_natures) > 3:
            nature_str += f" 等{len(unique_natures)}种"
        rel_links.append(f"{_char_link(target, char_map)} — {nature_str}")
    body += _wikilink_section("人际关系", rel_links)

    # 关联设定（wikilink → settings/{子文件夹}/，top 15）
    setting_links = [_setting_link(s, setting_map) for s in related_settings[:15]]
    if len(related_settings) > 15:
        setting_links.append(f"*...共 {len(related_settings)} 个设定*")
    body += _wikilink_section("关联设定", setting_links)

    # 高光时刻
    body += _build_achievements_with_maps(name, events or [], event_map)

    # 语录
    body += _build_quotes_section(char)

    # 关系子图
    body += _build_character_mermaid(char)

    content = "\n".join(fm) + "\n".join(body)
    filepath = char_dir / f"{_safe_filename(name)}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── 设定卡片 ──────────────────────────────────────────────────

def _write_setting_card(setting: dict, setting_dir: Path, origin: str, char_map: dict = None, setting_map: dict = None) -> Path:
    """生成单个设定卡片 .md 文件，包含状态栏、关联人物和关联设定链接。"""
    name = setting.get("name", "未知")
    stype = setting.get("type") or setting.get("setting_type") or "其他"
    description = setting.get("description") or "暂无描述"
    related_characters = setting.get("related_characters", []) or []
    related_settings = setting.get("related_settings", []) or []

    char_map = char_map or {}
    setting_map = setting_map or {}

    # frontmatter
    fm = _frontmatter([
        "type: setting",
        f"color: {_get_setting_color(stype)}",  # Graph View 分色
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

    # 关联人物（wikilink → characters/{子文件夹}/）
    char_links = [_char_link(c, char_map) for c in related_characters]
    body += _wikilink_section("关联人物", char_links)

    # 关联设定（wikilink → settings/{子文件夹}/，排除自引用）
    setting_links = [_setting_link(s, setting_map) for s in related_settings if s != name]
    body += _wikilink_section("关联设定", setting_links)

    content = "\n".join(fm) + "\n".join(body)
    filepath = setting_dir / f"{_safe_filename(name)}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── 事件卡片 ──────────────────────────────────────────────────

def _write_event_card(event: dict, event_dir: Path, origin: str, char_map: dict = None, setting_map: dict = None, event_map: dict = None) -> Path:
    """生成单个事件卡片 .md 文件，包含状态栏、参与人物、前置事件和关联设定链接。"""
    name = event.get("name", "未知")
    time = event.get("time") or "未知"
    participants = event.get("participants", []) or []
    location = event.get("location") or ""
    description = event.get("description") or "暂无描述"
    cause = event.get("cause", []) or []
    effect = event.get("effect", []) or []
    chapter = event.get("chapter") or ""
    importance = event.get("importance") or ""

    char_map = char_map or {}
    setting_map = setting_map or {}
    event_map = event_map or {}

    # frontmatter
    fm = _frontmatter([
        "type: event",
        f"color: {_get_event_color(importance)}",  # Graph View 分色
        "source: analyzed",
        f"origin: {origin}",
        f"time: {time}",
        f"chapter: {chapter}" if chapter else None,
        f"importance: {importance}" if importance else None,
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

    # 重要性标签
    if importance:
        importance_icons = {"高": "🔴", "中": "🟡", "低": "⚪"}
        icon = importance_icons.get(importance, "⚪")
        body += [f"{icon} **重要性**：{importance}", ""]

    # 时间和描述
    body += [
        f"**时间**：{time}",
        "",
        description,
        "",
    ]

    # 参与人物（wikilink → characters/{子文件夹}/，展平嵌套 list）
    char_links = [_char_link(c, char_map) for c in _flatten(participants)]
    body += _wikilink_section("参与人物", char_links)

    # 发生地点（wikilink → settings/{子文件夹}/）
    if location:
        body += _wikilink_section("发生地点", [_setting_link(location, setting_map)])

    # 前置事件（wikilink → events/{子文件夹}/）
    cause_links = [_event_link(c, event_map) for c in _flatten(cause)]
    body += _wikilink_section("前置事件", cause_links)

    # 后果/影响（wikilink → events/{子文件夹}/）
    effect_links = [_event_link(e, event_map) for e in _flatten(effect)]
    body += _wikilink_section("后续影响", effect_links)

    content = "\n".join(fm) + "\n".join(body)
    filepath = event_dir / f"{_safe_filename(name)}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── 作品索引 ──────────────────────────────────────────────────

def _build_character_list_grouped(characters: list, char_map: dict = None) -> list[str]:
    """按角色定位分组显示人物列表。"""
    char_map = char_map or {}
    groups: dict[str, list] = {"核心人物": [], "重要配角": [], "其他人物": []}
    for c in characters:
        tags = set(c.get("role_tags") or [])
        if tags & _PROTAGONIST_TAGS:
            groups["核心人物"].append(c)
        elif tags & _IMPORTANT_TAGS:
            groups["重要配角"].append(c)
        else:
            groups["其他人物"].append(c)

    section_icons = {"核心人物": "🔴", "重要配角": "🟡", "其他人物": "⚪"}
    lines = ["## 人物", ""]
    for section, chars in groups.items():
        if not chars:
            continue
        icon = section_icons.get(section, "")
        lines.append(f"### {icon} {section}（{len(chars)}人）")
        lines.append("")
        for c in chars:
            name = c.get("name", "?")
            link = _char_link(name, char_map)
            identity = c.get("identity") or ""
            tags = c.get("role_tags") or []
            tag_str = f" `{'·'.join(tags)}`" if tags else ""
            suffix = f" — {identity}" if identity else ""
            lines.append(f"- {link}{tag_str}{suffix}")
        lines.append("")
    return lines


def _build_settings_list_grouped(settings: list, setting_map: dict = None) -> list[str]:
    """按类型分组显示设定列表（地点/组织/概念）。"""
    setting_map = setting_map or {}
    groups: dict[str, list] = {"地点": [], "组织": [], "概念": []}
    for s in settings:
        sub = setting_map.get(s.get("name", ""), "概念")
        groups.setdefault(sub, []).append(s)

    section_icons = {"地点": "📍", "组织": "🏛️", "概念": "💡"}
    lines = ["## 设定", ""]
    for section in ["地点", "组织", "概念"]:
        items = groups.get(section, [])
        if not items:
            continue
        icon = section_icons.get(section, "")
        lines.append(f"### {icon} {section}（{len(items)}个）")
        lines.append("")
        for s in items[:20]:  # 每类最多显示 20 个
            name = s.get("name", "?")
            link = _setting_link(name, setting_map)
            desc = (s.get("description") or "")[:30]
            suffix = f" — {desc}" if desc else ""
            lines.append(f"- {link}{suffix}")
        if len(items) > 20:
            lines.append(f"- *...还有 {len(items) - 20} 个*")
        lines.append("")
    return lines


def _write_book_index(
    title: str, summary: str, characters: list, settings: list,
    events: list, book_dir: Path, char_map: dict = None, setting_map: dict = None, event_map: dict = None
) -> Path:
    """生成作品索引 _index.md，包含人物、设定、事件、关系图谱和时间线。"""
    char_map = char_map or {}
    setting_map = setting_map or {}
    event_map = event_map or {}

    fm = _frontmatter([
        "type: book",
        "tags: [book]",
        f"created: {_today()}",
    ])

    body = ["", f"# {title}", ""]

    if summary:
        body += [f"> {summary}", ""]

    # 人物（按角色分组显示）
    body += _build_character_list_grouped(characters, char_map)

    # 设定（按类型分组显示）
    body += _build_settings_list_grouped(settings, setting_map)

    # 事件（重要事件 top 30 + "更多"提示）
    if events:
        sorted_events = sorted(events, key=lambda e: {"高": 3, "中": 2, "低": 1}.get(e.get("importance") or "", 0), reverse=True)
        shown = sorted_events[:30]
        body += _wikilink_section(f"事件（{len(events)}个）", [
            _event_link(e.get("name", "?"), event_map)
            + (f" — {e.get('time', '')}" if e.get("time") else "")
            for e in shown
        ])
        if len(events) > 30:
            body.append(f"*...还有 {len(events) - 30} 个事件，使用 Path filter `events` 查看全部*")
            body.append("")

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


# ── 独立时间线页面 ──────────────────────────────────────────────────

def _sort_events_by_time(events: list) -> list:
    """
    按时间排序事件。

    排序规则：
    1. 有 chapter 字段的按章节号排序
    2. 有 time 字段的按时间字符串排序
    3. 无时间信息的排到最后
    """
    def _sort_key(e):
        # 优先按 chapter 排序
        chapter = e.get("chapter") or ""
        # 尝试提取章节号（如"第三回"→3, "第12章"→12）
        chapter_num = _extract_chapter_number(chapter)

        # 其次按 time 排序
        time_str = e.get("time") or ""

        # 重要性作为次要排序（高>中>低）
        importance = e.get("importance") or ""
        _importance_order = {"高": 0, "中": 1, "低": 2}

        return (chapter_num, time_str, _importance_order.get(importance, 3))

    return sorted(events, key=_sort_key)


def _extract_chapter_number(chapter: str) -> int:
    """从章节标题中提取数字（如'第三回'→3, '第12章'→12）。"""
    import re
    if not chapter:
        return 9999  # 无章节信息排到最后

    # 尝试阿拉伯数字
    m = re.search(r'(\d+)', chapter)
    if m:
        return int(m.group(1))

    # 尝试中文数字
    cn_nums = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '百': 100,
    }
    # 简单中文数字解析（十以内）
    for cn, num in cn_nums.items():
        if cn in chapter:
            return num

    return 9999


def _build_importance_groups(events: list) -> dict[str, list]:
    """按重要性分组事件。"""
    groups = {"高": [], "中": [], "低": [], "未分类": []}
    for e in events:
        imp = e.get("importance") or "未分类"
        if imp not in groups:
            imp = "未分类"
        groups[imp].append(e)
    return groups


def generate_timeline_page(
    title: str, events: list, book_dir: Path, char_map: dict = None, setting_map: dict = None, event_map: dict = None
) -> Path:
    """
    生成独立的时间线页面 timeline.md。

    特性：
    1. 按章节/时间排序
    2. 按重要性分组显示
    3. 所有事件用 wikilink 可点击跳转
    4. 含 Mermaid timeline 图
    """
    if not events:
        return None

    char_map = char_map or {}
    setting_map = setting_map or {}
    event_map = event_map or {}

    fm = _frontmatter([
        "type: timeline",
        "tags: [timeline]",
        f"origin: {title}",
        f"created: {_today()}",
    ])

    body = [
        "",
        f"# 📅 {title} — 时间线",
        "",
    ]

    # ── Mermaid timeline 图 ──
    mermaid = _build_mermaid_timeline(title, events)
    if mermaid:
        body += ["## 📊 时间线图", "", "```mermaid"]
        body += mermaid
        body += ["```", ""]

    # ── 按重要性分组显示 ──
    importance_groups = _build_importance_groups(events)

    importance_labels = {
        "高": ("🔴 重要事件", "高"),
        "中": ("🟡 一般事件", "中"),
        "低": ("⚪ 细节事件", "低"),
        "未分类": ("⚪ 未分类事件", "未分类"),
    }

    for imp_key in ["高", "中", "低", "未分类"]:
        group_events = importance_groups.get(imp_key) or []
        if not group_events:
            continue

        label, imp_tag = importance_labels[imp_key]
        body += [f"## {label}", ""]

        # 按时间排序
        sorted_events = _sort_events_by_time(group_events)

        for e in sorted_events:
            name = e.get("name", "未知")
            time = e.get("time") or ""
            chapter = e.get("chapter") or ""
            participants = e.get("participants") or []
            location = e.get("location") or ""
            description = e.get("description") or ""

            # 构建时间标签
            time_parts = []
            if chapter:
                time_parts.append(chapter)
            if time and time != "未知":
                time_parts.append(time)
            time_str = f" `{', '.join(time_parts)}`" if time_parts else ""

            # 构建参与者标签
            participants_str = ""
            if participants:
                links = "、".join(
                    _char_link(p, char_map) for p in participants[:5]
                )
                participants_str = f" — {links}"

            # 构建地点标签
            location_str = ""
            if location:
                location_str = f" {_setting_link(location, setting_map)}"

            # 主行
            line = f"- {_event_link(name, event_map)}{time_str}{participants_str}{location_str}"
            body.append(line)

            # 描述行（缩进）
            if description:
                body.append(f"  > {description}")

        body.append("")

    content = "\n".join(fm) + "\n".join(body)
    filepath = book_dir / "timeline.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath



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
    book_dir.mkdir(parents=True, exist_ok=True)
    char_dir = book_dir / "characters"
    setting_dir = book_dir / "settings"
    event_dir = book_dir / "events"

    # 构建实体映射表（name → 子文件夹）
    char_map, setting_map, event_map = _build_entity_maps(characters, settings, events)

    # 创建子文件夹
    char_subfolders = {char_map.get(c.get("name", ""), "其他人物") for c in characters}
    setting_subfolders = {setting_map.get(s.get("name", ""), "概念") for s in settings}
    event_subfolders = {event_map.get(e.get("name", ""), "一般事件") for e in events}

    for sub in char_subfolders:
        (char_dir / sub).mkdir(parents=True, exist_ok=True)
    for sub in setting_subfolders:
        (setting_dir / sub).mkdir(parents=True, exist_ok=True)
    for sub in event_subfolders:
        (event_dir / sub).mkdir(parents=True, exist_ok=True)

    generated_files = []

    # 增量写入人物卡片
    for char in characters:
        sub = char_map.get(char.get("name", ""), "其他人物")
        filepath = _write_character_card_incremental(char, char_dir / sub, title, events, char_map, setting_map, event_map)
        generated_files.append(str(filepath))

    # 增量写入设定卡片
    for setting in settings:
        sub = setting_map.get(setting.get("name", ""), "概念")
        filepath = _write_setting_card_incremental(setting, setting_dir / sub, title, char_map, setting_map)
        generated_files.append(str(filepath))

    # 增量写入事件卡片
    for event in events:
        sub = event_map.get(event.get("name", ""), "一般事件")
        filepath = _write_event_card_incremental(event, event_dir / sub, title, char_map, setting_map, event_map)
        generated_files.append(str(filepath))

    # 始终重新生成索引文件
    generated_files.append(str(_write_book_index(title, summary, characters, settings, events, book_dir, char_map, setting_map, event_map)))

    return generated_files


def _write_character_card_incremental(char: dict, char_dir: Path, origin: str, events: list = None, char_map: dict = None, setting_map: dict = None, event_map: dict = None) -> Path:
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
    return _write_character_card(char, char_dir, origin, events, char_map, setting_map, event_map)


def _write_setting_card_incremental(setting: dict, setting_dir: Path, origin: str, char_map: dict = None, setting_map: dict = None) -> Path:
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

    return _write_setting_card(setting, setting_dir, origin, char_map, setting_map)


def _write_event_card_incremental(event: dict, event_dir: Path, origin: str, char_map: dict = None, setting_map: dict = None, event_map: dict = None) -> Path:
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

    return _write_event_card(event, event_dir, origin, char_map, setting_map, event_map)


def _read_character_from_file(filepath: Path) -> dict:
    """从文件读取人物数据。"""
    try:
        content = filepath.read_text(encoding='utf-8')
        return _parse_character_md(content)
    except (FileNotFoundError, UnicodeDecodeError) as e:
        logger.warning(f"读取人物文件失败 {filepath.name}: {e}")
        return None


def _read_setting_from_file(filepath: Path) -> dict:
    """从文件读取设定数据。"""
    try:
        content = filepath.read_text(encoding='utf-8')
        return _parse_setting_md(content)
    except (FileNotFoundError, UnicodeDecodeError) as e:
        logger.warning(f"读取设定文件失败 {filepath.name}: {e}")
        return None


def _read_event_from_file(filepath: Path) -> dict:
    """从文件读取事件数据。"""
    try:
        content = filepath.read_text(encoding='utf-8')
        return _parse_event_md(content)
    except (FileNotFoundError, UnicodeDecodeError) as e:
        logger.warning(f"读取事件文件失败 {filepath.name}: {e}")
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
    """解析事件卡片 .md 文件，提取结构化数据。"""
    lines = content.strip().split('\n')
    event = {"type": "event"}

    for line in lines:
        if line.startswith('# '):
            event["name"] = line[2:].strip()
            break

    if not event.get("name"):
        return None

    # 提取 frontmatter 字段
    in_frontmatter = False
    for line in lines:
        if line.strip() == '---':
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            if line.startswith('time:'):
                event["time"] = line.split(':', 1)[1].strip()
            elif line.startswith('importance:'):
                event["importance"] = line.split(':', 1)[1].strip()
            elif line.startswith('chapter:'):
                event["chapter"] = line.split(':', 1)[1].strip()

    # 提取正文字段
    current_section = None
    section_content = []

    for line in lines:
        if line.startswith('## '):
            if current_section and section_content:
                _assign_event_section(event, current_section, section_content)
            current_section = line[3:].strip()
            section_content = []
        elif line.startswith('- '):
            section_content.append(line[2:].strip())
        elif current_section and line.strip() and not line.startswith('#') and not line.startswith('>'):
            section_content.append(line.strip())

    if current_section and section_content:
        _assign_event_section(event, current_section, section_content)

    return event


def _assign_event_section(event: dict, section: str, content: list):
    """将解析的内容分配到事件卡片的对应字段。"""
    section_lower = section.lower()

    if '参与人物' in section_lower:
        participants = []
        for item in content:
            # 解析 [[characters/xxx|xxx]] 格式
            if '|' in item:
                name = item.split('|')[-1].rstrip(']').strip('[')
            else:
                name = item.strip()
            if name:
                participants.append(name)
        event["participants"] = participants
    elif '前置事件' in section_lower:
        causes = []
        for item in content:
            if '|' in item:
                name = item.split('|')[-1].rstrip(']').strip('[')
            else:
                name = item.strip()
            if name:
                causes.append(name)
        event["cause"] = causes
    elif '后续影响' in section_lower:
        effects = []
        for item in content:
            if '|' in item:
                name = item.split('|')[-1].rstrip(']').strip('[')
            else:
                name = item.strip()
            if name:
                effects.append(name)
        event["effect"] = effects
    elif '描述' in section_lower or '简介' in section_lower:
        event["description"] = '\n'.join(content)


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

    # 后果/影响：合并去重
    old_effect = set(old.get("effect") or [])
    new_effect = set(new.get("effect") or [])
    merged["effect"] = list(old_effect | new_effect)

    # 重要性：取更高的
    _importance_order = {"高": 3, "中": 2, "低": 1}
    old_imp = _importance_order.get(old.get("importance") or "", 0)
    new_imp = _importance_order.get(new.get("importance") or "", 0)
    if old_imp > new_imp:
        merged["importance"] = old.get("importance")

    return merged
