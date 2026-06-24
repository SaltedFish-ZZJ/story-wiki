"""
Story Wiki - 公共工具函数模块
抽取自 analyzer / generator / vault_manager / pipeline / novel_logger 等模块的
重复函数，统一维护。
"""
import json
import re
from datetime import datetime


# ── 文件名工具 ──────────────────────────────────────────────────

def safe_filename(name: str) -> str:
    """
    将名称转为安全的文件名（去除非法字符）。

    Args:
        name: 原始名称

    Returns:
        安全的文件名字符串
    """
    illegal = '<>:"/\\|?*'
    safe = name
    for ch in illegal:
        safe = safe.replace(ch, "_")
    return safe.strip()


# ── 名称工具 ──────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """
    去除括号内容和空格，用于模糊匹配。

    Args:
        name: 原始名称（如 "贾宝玉（主角）"）

    Returns:
        标准化名称（如 "贾宝玉"）
    """
    return re.sub(r'[（\(][^）\)]*[）\)]', '', name).strip()


# ── 日期工具 ──────────────────────────────────────────────────

def today_str() -> str:
    """返回今天的日期字符串（YYYY-MM-DD）。"""
    return datetime.now().strftime("%Y-%m-%d")


# ── 文本统计 ─────────────────────────────────────────────────

def count_words(text: str) -> int:
    """
    统计文本字数：中文字符数 + 英文单词数。

    Args:
        text: 待统计文本

    Returns:
        字数
    """
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    return chinese_chars + english_words


# ── Obsidian Frontmatter ─────────────────────────────────────

def frontmatter(fields: list) -> list[str]:
    """
    构建 Obsidian frontmatter 块（含开头结尾 ---），自动过滤 None 值。

    Args:
        fields: YAML 格式的字段列表，如 ["type: character", "name: 张三"]

    Returns:
        完整的 frontmatter 行列表
    """
    return ["---"] + [f for f in fields if f is not None] + ["---"]


# ── AI 响应解析 ─────────────────────────────────────────────

def parse_ai_response(raw: str) -> dict:
    """
    解析 AI 返回的 JSON，带多种容错策略。

    策略：
    1. 直接解析
    2. 提取 ```json ... ``` 中的内容
    3. 提取第一个 { ... } 块

    Args:
        raw: AI 返回的原始文本

    Returns:
        解析后的 dict

    Raises:
        ValueError: 所有解析策略均失败
    """
    if not raw or not raw.strip():
        raise ValueError("AI 返回内容为空")

    # 策略 1：直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 策略 2：提取 ```json ... ``` 中的内容
    match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 策略 3：提取第一个 { ... } 块
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError("所有解析策略均失败")
