"""
Story Wiki - 知识库管理模块
从 Obsidian Vault 读取、更新、添加、搜索卡片，以及获取时间线。
实现 VaultManagerInterface 接口。
"""
from pathlib import Path
from typing import Dict, List, Optional
import re

from src.interfaces import (
    VaultManagerInterface,
    Character,
    Setting,
    Event,
)
from src.config import VAULT_DIR
from src.utils import safe_filename as _safe_filename, frontmatter as _frontmatter, today_str as _today


# ── VaultManager ──────────────────────────────────────────────

class VaultManager(VaultManagerInterface):
    """
    知识库管理器，负责从 Obsidian Vault 读取和更新知识库。

    目录结构约定：
        {VAULT_DIR}/{book_title}/
            characters/    人物卡片
            settings/      设定卡片
            events/        事件卡片
            _index.md      作品索引
    """

    def __init__(self, config: dict):
        """
        初始化模块。

        Args:
            config: 配置字典，支持以下键：
                - vault_dir: Vault 根目录（可选，默认使用 VAULT_DIR）
                - book_title: 作品标题（可选，用于定位子目录）
        """
        self.vault_dir = Path(config.get("vault_dir", VAULT_DIR))
        self.book_title = config.get("book_title", "")

    def _book_dir(self) -> Path:
        """获取当前作品目录。"""
        if self.book_title:
            return self.vault_dir / _safe_filename(self.book_title)
        return self.vault_dir

    def _char_dir(self) -> Path:
        return self._book_dir() / "characters"

    def _setting_dir(self) -> Path:
        return self._book_dir() / "settings"

    def _event_dir(self) -> Path:
        return self._book_dir() / "events"

    # ── 加载所有卡片 ──────────────────────────────────────────────

    def load_all_cards(self) -> Dict[str, List[dict]]:
        """
        加载所有卡片。

        Returns:
            {
                "characters": [人物卡片列表],
                "settings": [设定卡片列表],
                "events": [事件卡片列表]
            }
        """
        return {
            "characters": self._load_cards_from_dir(self._char_dir(), "character"),
            "settings": self._load_cards_from_dir(self._setting_dir(), "setting"),
            "events": self._load_cards_from_dir(self._event_dir(), "event"),
        }

    def _load_cards_from_dir(self, directory: Path, card_type: str) -> List[dict]:
        """从指定目录加载所有 .md 卡片。"""
        if not directory.exists():
            return []

        cards = []
        for md_file in sorted(directory.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                card = self._parse_card(content, card_type)
                if card:
                    cards.append(card)
            except Exception as e:
                print(f"[VaultManager] 读取卡片失败 {md_file}: {e}")
        return cards

    def _parse_card(self, content: str, card_type: str) -> Optional[dict]:
        """根据卡片类型调用对应的解析函数。"""
        if card_type == "character":
            return _parse_character_md(content)
        elif card_type == "setting":
            return _parse_setting_md(content)
        elif card_type == "event":
            return _parse_event_md(content)
        return None

    # ── 加载单个卡片 ──────────────────────────────────────────────

    def load_character(self, name: str) -> Optional[Character]:
        """加载人物卡片。"""
        filepath = self._char_dir() / f"{_safe_filename(name)}.md"
        return self._load_character_from_file(filepath)

    def _load_character_from_file(self, filepath: Path) -> Optional[Character]:
        """从文件加载人物对象。"""
        if not filepath.exists():
            return None
        try:
            content = filepath.read_text(encoding="utf-8")
            data = _parse_character_md(content)
            if not data:
                return None
            return _dict_to_character(data)
        except Exception as e:
            print(f"[VaultManager] 读取人物失败 {filepath}: {e}")
            return None

    def load_setting(self, name: str) -> Optional[Setting]:
        """加载设定卡片。"""
        filepath = self._setting_dir() / f"{_safe_filename(name)}.md"
        return self._load_setting_from_file(filepath)

    def _load_setting_from_file(self, filepath: Path) -> Optional[Setting]:
        """从文件加载设定对象。"""
        if not filepath.exists():
            return None
        try:
            content = filepath.read_text(encoding="utf-8")
            data = _parse_setting_md(content)
            if not data:
                return None
            return _dict_to_setting(data)
        except Exception as e:
            print(f"[VaultManager] 读取设定失败 {filepath}: {e}")
            return None

    def load_event(self, name: str) -> Optional[Event]:
        """加载事件卡片。"""
        filepath = self._event_dir() / f"{_safe_filename(name)}.md"
        return self._load_event_from_file(filepath)

    def _load_event_from_file(self, filepath: Path) -> Optional[Event]:
        """从文件加载事件对象。"""
        if not filepath.exists():
            return None
        try:
            content = filepath.read_text(encoding="utf-8")
            data = _parse_event_md(content)
            if not data:
                return None
            return _dict_to_event(data)
        except Exception as e:
            print(f"[VaultManager] 读取事件失败 {filepath}: {e}")
            return None

    # ── 更新卡片 ──────────────────────────────────────────────────

    def update_character(self, name: str, updates: dict):
        """
        更新人物卡片。

        Args:
            name: 人物名称
            updates: 更新字段字典，支持字段名与 Character 数据结构一致
        """
        filepath = self._char_dir() / f"{_safe_filename(name)}.md"
        if not filepath.exists():
            raise FileNotFoundError(f"人物卡片不存在: {name}")

        existing = self.load_character(name)
        if existing is None:
            raise ValueError(f"无法解析人物卡片: {name}")

        merged = _merge_character_updates(existing, updates)
        self._write_character_card(merged)

    def update_setting(self, name: str, updates: dict):
        """
        更新设定卡片。

        Args:
            name: 设定名称
            updates: 更新字段字典
        """
        filepath = self._setting_dir() / f"{_safe_filename(name)}.md"
        if not filepath.exists():
            raise FileNotFoundError(f"设定卡片不存在: {name}")

        existing = self.load_setting(name)
        if existing is None:
            raise ValueError(f"无法解析设定卡片: {name}")

        merged = _merge_setting_updates(existing, updates)
        self._write_setting_card(merged)

    def update_event(self, name: str, updates: dict):
        """
        更新事件卡片。

        Args:
            name: 事件名称
            updates: 更新字段字典
        """
        filepath = self._event_dir() / f"{_safe_filename(name)}.md"
        if not filepath.exists():
            raise FileNotFoundError(f"事件卡片不存在: {name}")

        existing = self.load_event(name)
        if existing is None:
            raise ValueError(f"无法解析事件卡片: {name}")

        merged = _merge_event_updates(existing, updates)
        self._write_event_card(merged)

    # ── 添加新卡片 ──────────────────────────────────────────────

    def add_event(self, event: Event):
        """添加事件卡片。"""
        self._event_dir().mkdir(parents=True, exist_ok=True)
        self._write_event_card(event)

    def add_character(self, character: Character):
        """添加人物卡片。"""
        self._char_dir().mkdir(parents=True, exist_ok=True)
        self._write_character_card(character)

    def add_setting(self, setting: Setting):
        """添加设定卡片。"""
        self._setting_dir().mkdir(parents=True, exist_ok=True)
        self._write_setting_card(setting)

    # ── 搜索卡片 ──────────────────────────────────────────────────

    def search_cards(self, keyword: str) -> Dict[str, List[dict]]:
        """
        搜索卡片，按关键词匹配名称、内容。

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的卡片列表
        """
        keyword_lower = keyword.lower()
        all_cards = self.load_all_cards()

        return {
            "characters": [
                c for c in all_cards["characters"]
                if _card_matches_keyword(c, keyword_lower)
            ],
            "settings": [
                s for s in all_cards["settings"]
                if _card_matches_keyword(s, keyword_lower)
            ],
            "events": [
                e for e in all_cards["events"]
                if _card_matches_keyword(e, keyword_lower)
            ],
        }

    # ── 获取时间线 ──────────────────────────────────────────────

    def get_timeline(self) -> List[dict]:
        """
        获取事件时间线，按时间排序。

        Returns:
            按时间排序的事件列表
        """
        all_cards = self.load_all_cards()
        events = all_cards["events"]
        return sorted(events, key=lambda e: e.get("time", ""))

    # ── 写入卡片文件 ──────────────────────────────────────────────

    def _write_character_card(self, character: Character):
        """将 Character 对象写入 .md 文件。"""
        self._char_dir().mkdir(parents=True, exist_ok=True)
        content = _character_to_markdown(character)
        filepath = self._char_dir() / f"{_safe_filename(character.name)}.md"
        filepath.write_text(content, encoding="utf-8")

    def _write_setting_card(self, setting: Setting):
        """将 Setting 对象写入 .md 文件。"""
        self._setting_dir().mkdir(parents=True, exist_ok=True)
        content = _setting_to_markdown(setting)
        filepath = self._setting_dir() / f"{_safe_filename(setting.name)}.md"
        filepath.write_text(content, encoding="utf-8")

    def _write_event_card(self, event: Event):
        """将 Event 对象写入 .md 文件。"""
        self._event_dir().mkdir(parents=True, exist_ok=True)
        content = _event_to_markdown(event)
        filepath = self._event_dir() / f"{_safe_filename(event.name)}.md"
        filepath.write_text(content, encoding="utf-8")

    # ── BaseModule 接口实现 ────────────────────────────────────

    def run(self, input_data: dict) -> dict:
        """运行模块，支持的操作类型：load_all, load, update, add, search, timeline。"""
        action = input_data.get("action", "")
        if action == "load_all":
            return self.load_all_cards()
        elif action == "load":
            card_type = input_data.get("card_type", "")
            name = input_data.get("name", "")
            if card_type == "character":
                char = self.load_character(name)
                return {"result": _character_to_dict(char) if char else None}
            elif card_type == "setting":
                setting = self.load_setting(name)
                return {"result": _setting_to_dict(setting) if setting else None}
            elif card_type == "event":
                event = self.load_event(name)
                return {"result": _event_to_dict(event) if event else None}
            return {"error": f"未知卡片类型: {card_type}"}
        elif action == "update":
            card_type = input_data.get("card_type", "")
            name = input_data.get("name", "")
            updates = input_data.get("updates", {})
            try:
                if card_type == "character":
                    self.update_character(name, updates)
                elif card_type == "setting":
                    self.update_setting(name, updates)
                elif card_type == "event":
                    self.update_event(name, updates)
                else:
                    return {"error": f"未知卡片类型: {card_type}"}
                return {"success": True}
            except (FileNotFoundError, ValueError) as e:
                return {"error": str(e)}
        elif action == "add":
            card_type = input_data.get("card_type", "")
            card_data = input_data.get("card_data", {})
            try:
                if card_type == "character":
                    self.add_character(_dict_to_character(card_data))
                elif card_type == "setting":
                    self.add_setting(_dict_to_setting(card_data))
                elif card_type == "event":
                    self.add_event(_dict_to_event(card_data))
                else:
                    return {"error": f"未知卡片类型: {card_type}"}
                return {"success": True}
            except Exception as e:
                return {"error": str(e)}
        elif action == "search":
            keyword = input_data.get("keyword", "")
            return self.search_cards(keyword)
        elif action == "timeline":
            return {"timeline": self.get_timeline()}
        return {"error": f"未知操作: {action}"}

    def validate(self, output_data: dict) -> bool:
        """验证输出数据格式。"""
        if not isinstance(output_data, dict):
            return False
        if "error" in output_data:
            return True  # 错误响应也是合法的
        if "result" in output_data:
            return True
        if "success" in output_data:
            return True
        if "characters" in output_data and "settings" in output_data and "events" in output_data:
            return True
        if "timeline" in output_data:
            return True
        return False


# ══════════════════════════════════════════════════════════════
# 解析函数：从 Markdown 卡片中提取结构化数据
# ══════════════════════════════════════════════════════════════

def _parse_frontmatter(content: str) -> dict:
    """提取 YAML frontmatter 键值对（简易解析，不依赖第三方库）。"""
    fm = {}
    lines = content.strip().split("\n")
    in_fm = False
    for line in lines:
        if line.strip() == "---":
            if not in_fm:
                in_fm = True
                continue
            else:
                break
        if in_fm and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key and value:
                fm[key] = value
    return fm


def _extract_wikilink_text(item: str) -> str:
    """从 wikilink 中提取显示文本。例如 '[[characters/林黛玉|林黛玉]] — 恋人' -> '林黛玉'。"""
    import re
    # 匹配 [[path|display]] 或 [[name]]
    m = re.search(r'\[\[(?:[^\]|]*\|)?([^\]]+)\]\]', item)
    if m:
        return m.group(1)
    # 如果不是 wikilink，返回原始文本（去掉尾部修饰）
    return item.strip().rstrip("]").lstrip("[").split("/")[-1].split("—")[0].strip()


def _extract_section(content: str, section_name: str) -> List[str]:
    """提取指定 ## 标题下的内容。支持列表项、语录和纯文本。"""
    lines = content.split("\n")
    in_section = False
    items = []
    for line in lines:
        if line.startswith("## "):
            if in_section:
                break
            if section_name in line:
                in_section = True
                continue
        if in_section:
            if line.startswith("## "):
                break
            if line.startswith("- "):
                items.append(line[2:].strip())
            elif line.startswith("> ") and '"' in line:
                # 语录行
                quote = line[2:].strip().strip('"')
                if quote:
                    items.append(quote)
            elif line.strip() and not line.startswith("```"):
                # 纯文本行（如身份、性格描述）
                items.append(line.strip())
    return items


def _extract_status(content: str) -> str:
    """从状态栏提取状态。"""
    for line in content.split("\n"):
        if line.startswith("> "):
            for status in ["活跃", "已故", "失踪", "退场", "未知"]:
                if status in line:
                    return status
    return "未知"


def _parse_character_md(content: str) -> Optional[dict]:
    """解析人物卡片 Markdown。"""
    lines = content.strip().split("\n")
    char = {}

    # 标题
    for line in lines:
        if line.startswith("# "):
            char["name"] = line[2:].strip()
            break
    if not char.get("name"):
        return None

    # frontmatter
    fm = _parse_frontmatter(content)
    char["gender"] = fm.get("gender", "未知")
    char["faction"] = fm.get("faction", "")
    aliases_str = fm.get("aliases", "")
    if aliases_str.startswith("[") and aliases_str.endswith("]"):
        char["aliases"] = [a.strip() for a in aliases_str[1:-1].split(",") if a.strip()]
    else:
        char["aliases"] = []
    tags_str = fm.get("role_tags", "")
    if tags_str.startswith("[") and tags_str.endswith("]"):
        char["role_tags"] = [t.strip() for t in tags_str[1:-1].split(",") if t.strip()]
    else:
        char["role_tags"] = []

    char["status"] = _extract_status(content)

    # 各节
    char["identity"] = "\n".join(_extract_section(content, "身份")) or ""
    char["personality"] = "\n".join(_extract_section(content, "性格")) or ""

    # 人际关系
    rel_lines = _extract_section(content, "人际关系")
    relationships = []
    for item in rel_lines:
        if "—" in item:
            parts = item.split("—", 1)
            target = _extract_wikilink_text(parts[0])
            nature = parts[1].strip() if len(parts) > 1 else ""
            relationships.append({"target": target, "nature": nature})
    char["relationships"] = relationships

    # 关联设定
    setting_lines = _extract_section(content, "关联设定")
    char["related_settings"] = [_extract_wikilink_text(s) for s in setting_lines]

    # 语录
    char["quotes"] = _extract_section(content, "语录")

    return char


def _parse_setting_md(content: str) -> Optional[dict]:
    """解析设定卡片 Markdown。"""
    lines = content.strip().split("\n")
    setting = {}

    for line in lines:
        if line.startswith("# "):
            setting["name"] = line[2:].strip()
            break
    if not setting.get("name"):
        return None

    fm = _parse_frontmatter(content)
    setting["type"] = fm.get("setting_type", "其他")

    # 提取描述（**类型**：之后的文字）
    desc_lines = []
    in_desc = False
    for line in lines:
        if line.startswith("**类型**"):
            in_desc = True
            continue
        if in_desc and line.startswith("## "):
            break
        if in_desc and line.strip():
            desc_lines.append(line.strip())
    setting["description"] = "\n".join(desc_lines)

    # 关联人物
    char_lines = _extract_section(content, "关联人物")
    setting["related_characters"] = [_extract_wikilink_text(c) for c in char_lines]

    # 关联设定
    setting_lines = _extract_section(content, "关联设定")
    setting["related_settings"] = [_extract_wikilink_text(s) for s in setting_lines]

    return setting


def _parse_event_md(content: str) -> Optional[dict]:
    """解析事件卡片 Markdown。"""
    lines = content.strip().split("\n")
    event = {}

    for line in lines:
        if line.startswith("# "):
            event["name"] = line[2:].strip()
            break
    if not event.get("name"):
        return None

    fm = _parse_frontmatter(content)
    event["time"] = fm.get("time", "")
    event["chapter"] = fm.get("chapter", "")

    # 提取描述（时间行之后的内容）
    desc_lines = []
    in_desc = False
    for line in lines:
        if line.startswith("**时间**"):
            in_desc = True
            continue
        if in_desc and line.startswith("## "):
            break
        if in_desc and line.strip():
            desc_lines.append(line.strip())
    event["description"] = "\n".join(desc_lines)

    # 参与人物
    part_lines = _extract_section(content, "参与人物")
    event["participants"] = [_extract_wikilink_text(p) for p in part_lines]

    # 发生地点
    loc_lines = _extract_section(content, "发生地点")
    event["location"] = _extract_wikilink_text(loc_lines[0]) if loc_lines else ""

    # 前置事件
    cause_lines = _extract_section(content, "前置事件")
    event["cause"] = [_extract_wikilink_text(c) for c in cause_lines]
    event["effect"] = []

    return event


# ══════════════════════════════════════════════════════════════
# 转换函数：dict <-> dataclass
# ══════════════════════════════════════════════════════════════

def _dict_to_character(d: dict) -> Character:
    return Character(
        name=d.get("name", ""),
        identity=d.get("identity", ""),
        personality=d.get("personality", ""),
        gender=d.get("gender", "未知"),
        faction=d.get("faction", ""),
        aliases=d.get("aliases", []),
        role_tags=d.get("role_tags", []),
        status=d.get("status", "活跃"),
        relationships=d.get("relationships", []),
        related_settings=d.get("related_settings", []),
        quotes=d.get("quotes", []),
        motivation=d.get("motivation", ""),
        current_state=d.get("current_state", ""),
    )


def _dict_to_setting(d: dict) -> Setting:
    return Setting(
        name=d.get("name", ""),
        type=d.get("type", d.get("setting_type", "")),
        description=d.get("description", ""),
        related_characters=d.get("related_characters", []),
        related_settings=d.get("related_settings", []),
    )


def _dict_to_event(d: dict) -> Event:
    return Event(
        name=d.get("name", ""),
        time=d.get("time", ""),
        participants=d.get("participants", []),
        location=d.get("location", ""),
        description=d.get("description", ""),
        cause=d.get("cause", []),
        effect=d.get("effect", []),
        chapter=d.get("chapter", ""),
        importance=d.get("importance", "普通"),
    )


def _character_to_dict(c: Character) -> dict:
    return {
        "name": c.name,
        "identity": c.identity,
        "personality": c.personality,
        "gender": c.gender,
        "faction": c.faction,
        "aliases": c.aliases,
        "role_tags": c.role_tags,
        "status": c.status,
        "relationships": c.relationships,
        "related_settings": c.related_settings,
        "quotes": c.quotes,
        "motivation": c.motivation,
        "current_state": c.current_state,
    }


def _setting_to_dict(s: Setting) -> dict:
    return {
        "name": s.name,
        "type": s.type,
        "description": s.description,
        "related_characters": s.related_characters,
        "related_settings": s.related_settings,
    }


def _event_to_dict(e: Event) -> dict:
    return {
        "name": e.name,
        "time": e.time,
        "participants": e.participants,
        "location": e.location,
        "description": e.description,
        "cause": e.cause,
        "effect": e.effect,
        "chapter": e.chapter,
        "importance": e.importance,
    }


# ══════════════════════════════════════════════════════════════
# 合并更新函数
# ══════════════════════════════════════════════════════════════

def _merge_character_updates(existing: Character, updates: dict) -> Character:
    """将 updates dict 合并到现有 Character 对象上。"""
    data = _character_to_dict(existing)
    for key, value in updates.items():
        if key in data:
            data[key] = value
    return _dict_to_character(data)


def _merge_setting_updates(existing: Setting, updates: dict) -> Setting:
    """将 updates dict 合并到现有 Setting 对象上。"""
    data = _setting_to_dict(existing)
    for key, value in updates.items():
        if key in data:
            data[key] = value
    return _dict_to_setting(data)


def _merge_event_updates(existing: Event, updates: dict) -> Event:
    """将 updates dict 合并到现有 Event 对象上。"""
    data = _event_to_dict(existing)
    for key, value in updates.items():
        if key in data:
            data[key] = value
    return _dict_to_event(data)


# ══════════════════════════════════════════════════════════════
# Markdown 生成函数：dataclass -> Markdown 文本
# ══════════════════════════════════════════════════════════════




def _character_to_markdown(char: Character) -> str:
    """将 Character 对象转为 Markdown 文本。"""
    fm = _frontmatter([
        "type: character",
        "color: character",
        f"gender: {char.gender}",
        f"faction: {char.faction}" if char.faction else None,
        f"aliases: [{', '.join(char.aliases)}]" if char.aliases else None,
        f"role_tags: [{', '.join(char.role_tags)}]" if char.role_tags else None,
        "tags: [character]",
        f"created: {_today()}",
    ])

    body = [
        "",
        f"# {char.name}",
        "",
        f"> {char.status}",
        "",
        "## 身份",
        char.identity or "未知",
        "",
        "## 性格",
        char.personality or "未知",
        "",
    ]

    # 人际关系
    if char.relationships:
        body.append("## 人际关系")
        for r in char.relationships:
            target = r.get("target", "")
            nature = r.get("nature", "")
            body.append(f"- [[characters/{target}|{target}]] — {nature}")
        body.append("")

    # 关联设定
    if char.related_settings:
        body.append("## 关联设定")
        for s in char.related_settings:
            body.append(f"- [[settings/{s}|{s}]]")
        body.append("")

    # 语录
    if char.quotes:
        body.append("## 经典语录")
        for q in char.quotes[:5]:
            body.append(f'> "{q}"')
        body.append("")

    return "\n".join(fm) + "\n".join(body)


def _setting_to_markdown(setting: Setting) -> str:
    """将 Setting 对象转为 Markdown 文本。"""
    stype = setting.type or "其他"
    fm = _frontmatter([
        "type: setting",
        "color: setting",
        f"setting_type: {stype}",
        "tags: [setting]",
        f"created: {_today()}",
    ])

    body = [
        "",
        f"# {setting.name}",
        "",
        f"**类型**：{stype}",
        "",
        setting.description or "暂无描述",
        "",
    ]

    if setting.related_characters:
        body.append("## 关联人物")
        for c in setting.related_characters:
            body.append(f"- [[characters/{c}|{c}]]")
        body.append("")

    if setting.related_settings:
        body.append("## 关联设定")
        for s in setting.related_settings:
            body.append(f"- [[settings/{s}|{s}]]")
        body.append("")

    return "\n".join(fm) + "\n".join(body)


def _event_to_markdown(event: Event) -> str:
    """将 Event 对象转为 Markdown 文本。"""
    fm = _frontmatter([
        "type: event",
        "color: event",
        f"time: {event.time}",
        f"chapter: {event.chapter}" if event.chapter else None,
        "tags: [event]",
        f"created: {_today()}",
    ])

    body = [
        "",
        f"# {event.name}",
        "",
        f"**时间**：{event.time}",
        "",
        event.description or "暂无描述",
        "",
    ]

    if event.participants:
        body.append("## 参与人物")
        for p in event.participants:
            body.append(f"- [[characters/{p}|{p}]]")
        body.append("")

    if event.location:
        body.append("## 发生地点")
        body.append(f"- [[settings/{event.location}|{event.location}]]")
        body.append("")

    if event.cause:
        body.append("## 前置事件")
        for c in event.cause:
            body.append(f"- [[events/{c}|{c}]]")
        body.append("")

    return "\n".join(fm) + "\n".join(body)


# ══════════════════════════════════════════════════════════════
# 搜索辅助
# ══════════════════════════════════════════════════════════════

def _card_matches_keyword(card: dict, keyword_lower: str) -> bool:
    """检查卡片是否匹配关键词。"""
    # 名称匹配
    if keyword_lower in card.get("name", "").lower():
        return True
    # 内容字段匹配
    for field in ["identity", "personality", "description", "faction", "location"]:
        if keyword_lower in card.get(field, "").lower():
            return True
    # 列表字段匹配
    for field in ["aliases", "participants", "related_characters", "related_settings"]:
        items = card.get(field, [])
        for item in items:
            if isinstance(item, str) and keyword_lower in item.lower():
                return True
    # 关系匹配
    for rel in card.get("relationships", []):
        if keyword_lower in rel.get("target", "").lower():
            return True
        if keyword_lower in rel.get("nature", "").lower():
            return True
    return False
