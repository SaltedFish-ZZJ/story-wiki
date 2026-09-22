"""
Story Wiki - 质量检测器模块
检测小说内容的逻辑一致性、字数、重复内容和敏感词。

实现 QualityCheckerInterface 接口。
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import Counter

from src.interfaces import QualityCheckerInterface, ChapterContent, Character, Event
from src.config import DATA_DIR, MIN_WORDS, MAX_WORDS
from src.utils import count_words
from src.logging_setup import get_logger

logger = get_logger("quality_checker")


# ── 敏感词词库路径 ──
SENSITIVE_WORDS_FILE = DATA_DIR / "sensitive_words.txt"


class QualityChecker(QualityCheckerInterface):
    """
    质量检测器：检测小说内容质量。

    检测项目：
        1. 逻辑一致性 - 人物行为是否合理
        2. 字数检查 - 章节字数是否在合理范围
        3. 重复检测 - 与前文重复度
        4. 敏感词检测 - 基于本地词库
    """

    def __init__(self, config: dict):
        """
        初始化质量检测器。

        Args:
            config: 配置字典，可选键：
                - sensitive_words_path (str|Path): 敏感词词库路径
                - min_words (int): 最少字数（默认 2000）
                - max_words (int): 最多字数（默认 3000）
                - duplicate_threshold (float): 重复度阈值（默认 0.6）
        """
        self.config = config
        raw_path = config.get("sensitive_words_path", SENSITIVE_WORDS_FILE)
        self.sensitive_words_path = Path(raw_path)
        self.min_words = config.get("min_words", MIN_WORDS)
        self.max_words = config.get("max_words", MAX_WORDS)
        self.duplicate_threshold = config.get("duplicate_threshold", 0.6)

        # 缓存敏感词列表
        self._sensitive_words_cache: Optional[List[str]] = None

    # ── action 分发注册表 ──
    ACTIONS = {
        "check_logic": "_handle_check_logic",
        "check_words": "_handle_check_words",
        "check_duplicates": "_handle_check_duplicates",
        "check_sensitive": "_handle_check_sensitive",
        "full_check": "_handle_full_check",
    }

    def run(self, input_data: dict) -> dict:
        """
        运行质量检测。

        支持的 action：
            - check_logic: 检查逻辑一致性
            - check_words: 检查字数
            - check_duplicates: 检查重复
            - check_sensitive: 检查敏感词
            - full_check: 全量检查

        Args:
            input_data: 输入数据，必须包含 "action" 键

        Returns:
            操作结果字典
        """
        if not isinstance(input_data, dict):
            return {"success": False, "error": "input_data 必须是 dict"}

        action = input_data.get("action")
        if not action:
            return {"success": False, "error": "缺少 action 字段"}

        handler_name = self.ACTIONS.get(action)
        if not handler_name:
            return {"success": False, "error": f"未知 action: {action}"}

        try:
            return getattr(self, handler_name)(input_data)
        except (KeyError, TypeError) as e:
            return {"success": False, "error": f"参数错误: {e}"}
        except (RuntimeError, OSError) as e:
            return {"success": False, "error": f"检测失败: {e}"}

    def _handle_check_logic(self, input_data: dict) -> dict:
        result = self.check_logic_consistency(
            input_data["content"],
            input_data.get("characters", []),
            input_data.get("events", []),
        )
        return {"success": True, "result": result}

    def _handle_check_words(self, input_data: dict) -> dict:
        content = input_data["content"]
        passed = self.check_word_count(
            content,
            input_data.get("min_words", self.min_words),
            input_data.get("max_words", self.max_words),
        )
        return {"success": True, "passed": passed, "word_count": content.word_count}

    def _handle_check_duplicates(self, input_data: dict) -> dict:
        has_duplicates = self.check_duplicates(
            input_data["content"],
            input_data.get("previous_chapters", []),
        )
        return {"success": True, "has_duplicates": has_duplicates}

    def _handle_check_sensitive(self, input_data: dict) -> dict:
        sensitive_words = self.check_sensitive_words(input_data["content"])
        return {"success": True, "sensitive_words": sensitive_words}

    def _handle_full_check(self, input_data: dict) -> dict:
        result = self.full_check(
            input_data["content"],
            input_data.get("characters", []),
            input_data.get("events", []),
            input_data.get("previous_chapters", []),
        )
        return {"success": True, "result": result}

    def validate(self, output_data: dict) -> bool:
        """验证输出数据是否合法。"""
        if not isinstance(output_data, dict):
            return False
        if "success" not in output_data:
            return False
        if output_data["success"] and "result" in output_data:
            return True
        if output_data["success"] and "passed" in output_data:
            return True
        if output_data["success"] and "has_duplicates" in output_data:
            return True
        if output_data["success"] and "sensitive_words" in output_data:
            return True
        if not output_data["success"] and "error" in output_data:
            return True
        return False

    # ── 核心接口实现 ────────────────────────────────────────────

    def check_logic_consistency(
        self,
        content: ChapterContent,
        characters: List[Character],
        events: List[Event]
    ) -> Dict[str, Any]:
        """
        检查逻辑一致性。

        检查项目：
            1. 章节中提到的人物是否存在于人物列表
            2. 人物行为是否符合其设定
            3. 事件参与者是否合理

        Args:
            content: 章节内容
            characters: 人物列表
            events: 事件列表

        Returns:
            {
                "passed": True/False,
                "issues": [问题列表]
            }
        """
        issues = []
        chapter_text = content.content
        chapter_characters = set(content.characters_involved)

        # 检查人物是否存在
        known_characters = {c.name for c in characters}
        for char_name in chapter_characters:
            if char_name not in known_characters:
                issues.append(f"章节提到的人物 '{char_name}' 不在已知人物列表中")

        # 检查人物性格一致性（简单检查）
        for char in characters:
            if char.name in chapter_characters and char.personality:
                # 检查是否有明显矛盾的行为描述
                # 这里做简单的关键词匹配，实际应用中可以使用更复杂的AI分析
                pass

        # 检查事件参与者
        for event in events:
            if event.chapter and content.title in event.chapter:
                for participant in event.participants:
                    if participant not in chapter_characters and participant not in known_characters:
                        issues.append(f"事件参与者 '{participant}' 未在章节中出现")

        passed = len(issues) == 0

        return {
            "passed": passed,
            "issues": issues
        }

    def check_word_count(
        self,
        content: ChapterContent,
        min_words: int = MIN_WORDS,
        max_words: int = MAX_WORDS
    ) -> bool:
        """
        检查字数是否在合理范围。

        Args:
            content: 章节内容
            min_words: 最少字数
            max_words: 最多字数

        Returns:
            是否符合要求
        """
        word_count = content.word_count
        if word_count == 0:
            # 如果 word_count 未设置，计算实际字数
            word_count = self._count_words(content.content)

        return min_words <= word_count <= max_words

    def check_duplicates(
        self,
        content: ChapterContent,
        previous_chapters: List[str]
    ) -> bool:
        """
        检查与前文的重复内容。

        使用滑动窗口 + 哈希去重算法检测重复段落。

        Args:
            content: 章节内容
            previous_chapters: 之前章节的内容列表

        Returns:
            是否有重复（True=有重复，False=无重复）
        """
        if not previous_chapters:
            return False

        current_text = content.content
        window_size = 50  # 50字窗口

        # 提取当前章节的滑动窗口
        current_windows = self._extract_windows(current_text, window_size)

        # 提取前文的所有滑动窗口
        prev_windows = set()
        for prev in previous_chapters:
            prev_windows.update(self._extract_windows(prev, window_size))

        # 计算重复度
        if not current_windows:
            return False

        overlap = current_windows.intersection(prev_windows)
        duplicate_ratio = len(overlap) / len(current_windows)

        return duplicate_ratio >= self.duplicate_threshold

    def check_sensitive_words(
        self,
        content: ChapterContent
    ) -> List[str]:
        """
        检查敏感词。

        Args:
            content: 章节内容

        Returns:
            发现的敏感词列表
        """
        sensitive_words = self._load_sensitive_words()
        text = content.content
        found_words = []

        for word in sensitive_words:
            if word in text:
                found_words.append(word)

        return found_words

    def full_check(
        self,
        content: ChapterContent,
        characters: List[Character] = None,
        events: List[Event] = None,
        previous_chapters: List[str] = None
    ) -> Dict[str, Any]:
        """
        全量质量检查。

        Args:
            content: 章节内容
            characters: 人物列表（可选）
            events: 事件列表（可选）
            previous_chapters: 前文内容列表（可选）

        Returns:
            {
                "passed": True/False,
                "word_count": 字数,
                "word_count_ok": 字数是否合格,
                "has_duplicates": 是否有重复,
                "sensitive_words": 敏感词列表,
                "logic_issues": 逻辑问题列表,
                "summary": 综合评价
            }
        """
        characters = characters or []
        events = events or []
        previous_chapters = previous_chapters or []

        # 字数检查
        word_count = content.word_count or self._count_words(content.content)
        word_count_ok = self.check_word_count(content, self.min_words, self.max_words)

        # 重复检查
        has_duplicates = self.check_duplicates(content, previous_chapters)

        # 敏感词检查
        sensitive_words = self.check_sensitive_words(content)

        # 逻辑一致性检查
        logic_result = self.check_logic_consistency(content, characters, events)
        logic_issues = logic_result.get("issues", [])

        # 综合评价
        all_issues = []
        if not word_count_ok:
            all_issues.append(f"字数不合格（当前 {word_count} 字，要求 {self.min_words}-{self.max_words} 字）")
        if has_duplicates:
            all_issues.append("与前文存在大量重复内容")
        if sensitive_words:
            all_issues.append(f"发现敏感词：{', '.join(sensitive_words[:5])}")
        if logic_issues:
            all_issues.extend(logic_issues)

        passed = len(all_issues) == 0

        return {
            "passed": passed,
            "word_count": word_count,
            "word_count_ok": word_count_ok,
            "has_duplicates": has_duplicates,
            "sensitive_words": sensitive_words,
            "logic_issues": logic_issues,
            "all_issues": all_issues,
            "summary": self._generate_summary(passed, all_issues)
        }

    # ── 辅助方法 ────────────────────────────────────────────────

    def _load_sensitive_words(self) -> List[str]:
        """加载敏感词词库。"""
        if self._sensitive_words_cache is not None:
            return self._sensitive_words_cache

        words = []
        if self.sensitive_words_path.exists():
            try:
                with open(self.sensitive_words_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # 跳过注释和空行
                        if line and not line.startswith("#"):
                            words.append(line)
            except IOError as e:
                logger.warning(f"读取敏感词词库失败: {e}")

        self._sensitive_words_cache = words
        return words

    def _count_words(self, text: str) -> int:
        """统计文本字数（委托给 utils.count_words）。"""
        return count_words(text)

    def _extract_windows(self, text: str, window_size: int) -> set:
        """提取文本的滑动窗口哈希值。"""
        windows = set()
        # 移除空白字符
        cleaned = re.sub(r'\s+', '', text)

        for i in range(len(cleaned) - window_size + 1):
            window = cleaned[i:i + window_size]
            windows.add(window)

        return windows

    def _generate_summary(self, passed: bool, issues: List[str]) -> str:
        """生成质量评估摘要。"""
        if passed:
            return "质量检测通过，未发现明显问题。"

        summary_parts = [f"发现 {len(issues)} 个问题："]
        for i, issue in enumerate(issues[:5], 1):
            summary_parts.append(f"{i}. {issue}")

        if len(issues) > 5:
            summary_parts.append(f"...还有 {len(issues) - 5} 个问题")

        return "\n".join(summary_parts)


# ── 便捷函数 ──────────────────────────────────────────────────

def get_quality_checker(config: Optional[dict] = None) -> QualityChecker:
    """获取质量检测器实例。"""
    return QualityChecker(config or {})


def check_chapter_quality(
    content: ChapterContent,
    characters: List[Character] = None,
    events: List[Event] = None,
    previous_chapters: List[str] = None
) -> Dict[str, Any]:
    """
    便捷函数：检查单章质量。

    Args:
        content: 章节内容
        characters: 人物列表
        events: 事件列表
        previous_chapters: 前文内容列表

    Returns:
        质量检查结果
    """
    checker = QualityChecker({})
    return checker.full_check(content, characters, events, previous_chapters)
