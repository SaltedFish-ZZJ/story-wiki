"""
Story Wiki - 笔记生成模块
将 AI 分析的 JSON 数据转换为 Obsidian Markdown 文件。
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
    summary = analysis.get("summary", "")

    # 创建作品目录
    book_dir = output / _safe_filename(title)
    char_dir = book_dir / "characters"
    setting_dir = book_dir / "settings"
    for d in [char_dir, setting_dir]:
        d.mkdir(parents=True, exist_ok=True)

    generated_files = []

    # 生成人物卡片
    for char in characters:
        filepath = _write_character_card(char, char_dir, title)
        generated_files.append(str(filepath))

    # 生成设定卡片
    for setting in settings:
        filepath = _write_setting_card(setting, setting_dir, title)
        generated_files.append(str(filepath))

    # 生成作品索引
    filepath = _write_book_index(title, summary, characters, settings, book_dir)
    generated_files.append(str(filepath))

    return generated_files


def _write_character_card(char: dict, char_dir: Path, origin: str) -> Path:
    """生成单个人物卡片 .md 文件。"""
    name = char.get("name", "未知")
    aliases = char.get("aliases", []) or []
    identity = char.get("identity") or "未知"
    personality = char.get("personality") or "未知"
    gender = char.get("gender") or "未知"
    faction = char.get("faction") or ""
    relationships = char.get("relationships", []) or []

    # 构建 frontmatter
    fm_lines = [
        "---",
        "type: character",
        f"source: analyzed",
        f"origin: {origin}",
        f"gender: {gender}",
    ]
    if faction:
        fm_lines.append(f"faction: {faction}")
    if aliases:
        fm_lines.append(f"aliases: [{', '.join(aliases)}]")
    # tags
    tags = ["character"]
    if faction:
        tags.append(_safe_filename(faction))
    fm_lines.append(f"tags: [{', '.join(tags)}]")
    fm_lines.append(f"created: {datetime.now().strftime('%Y-%m-%d')}")
    fm_lines.append("---")

    # 构建正文
    body_lines = [
        "",
        f"# {name}",
        "",
        "## 身份",
        identity,
        "",
        "## 性格",
        personality,
        "",
    ]

    # 人际关系（wikilink）
    if relationships:
        body_lines.append("## 人际关系")
        for rel in relationships:
            target = rel.get("target", "未知")
            nature = rel.get("nature", "未知")
            body_lines.append(f"- [[{target}]] — {nature}")
        body_lines.append("")

    content = "\n".join(fm_lines) + "\n".join(body_lines)

    filepath = char_dir / f"{_safe_filename(name)}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _write_setting_card(setting: dict, setting_dir: Path, origin: str) -> Path:
    """生成单个设定卡片 .md 文件。"""
    name = setting.get("name", "未知")
    stype = setting.get("type") or "其他"
    description = setting.get("description") or "暂无描述"

    # frontmatter
    fm_lines = [
        "---",
        "type: setting",
        f"source: analyzed",
        f"origin: {origin}",
        f"setting_type: {stype}",
        f"tags: [setting, {_safe_filename(stype)}]",
        f"created: {datetime.now().strftime('%Y-%m-%d')}",
        "---",
    ]

    # 正文
    body_lines = [
        "",
        f"# {name}",
        "",
        f"**类型**：{stype}",
        "",
        description,
        "",
    ]

    content = "\n".join(fm_lines) + "\n".join(body_lines)

    filepath = setting_dir / f"{_safe_filename(name)}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _write_book_index(
    title: str, summary: str, characters: list, settings: list, book_dir: Path
) -> Path:
    """生成作品索引 _index.md。"""
    lines = [
        "---",
        "type: book",
        f"tags: [book]",
        f"created: {datetime.now().strftime('%Y-%m-%d')}",
        "---",
        "",
        f"# {title}",
        "",
    ]

    if summary:
        lines.extend([f"> {summary}", ""])

    # 人物列表
    if characters:
        lines.append("## 人物")
        for char in characters:
            name = char.get("name", "未知")
            identity = char.get("identity") or ""
            line = f"- [[characters/{name}|{name}]]"
            if identity:
                line += f" — {identity}"
            lines.append(line)
        lines.append("")

    # 设定列表
    if settings:
        lines.append("## 设定")
        for setting in settings:
            name = setting.get("name", "未知")
            desc = setting.get("description") or ""
            line = f"- [[settings/{name}|{name}]]"
            if desc:
                # 只取描述的前 30 字
                short = desc[:30] + ("..." if len(desc) > 30 else "")
                line += f" — {short}"
            lines.append(line)
        lines.append("")

    filepath = book_dir / "_index.md"
    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def _safe_filename(name: str) -> str:
    """将名称转为安全的文件名（去除非法字符）。"""
    # Windows 文件名非法字符
    illegal = '<>:"/\\|?*'
    safe = name
    for ch in illegal:
        safe = safe.replace(ch, "_")
    return safe.strip()
