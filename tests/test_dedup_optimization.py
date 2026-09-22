"""
去重优化测试 - P2
测试模糊匹配去重功能：子串匹配、去括号匹配、别名匹配
"""
import pytest
from unittest.mock import patch, MagicMock
from src.pipeline import (
    merge_characters,
    merge_settings,
    merge_events,
    merge_chapter_summaries,
)
from src.merger import (
    _find_matching_character,
    _find_matching_setting,
    _find_matching_event,
)
from src.utils import normalize_name as _normalize_name
from src.name_matcher import is_similar_name as _is_similar_name


class TestNormalizeName:
    """测试名称规范化函数。"""

    def test_remove_parentheses_cn(self):
        assert _normalize_name("富爸爸（罗伯特·清崎的父亲）") == "富爸爸"

    def test_remove_parentheses_en(self):
        assert _normalize_name("Harry (The Boy Who Lived)") == "Harry"

    def test_no_parentheses(self):
        assert _normalize_name("贾宝玉") == "贾宝玉"

    def test_empty(self):
        assert _normalize_name("") == ""


class TestIsSimilarName:
    """测试名字相似度判断。"""

    def test_exact_match(self):
        assert _is_similar_name("贾宝玉", "贾宝玉") is True

    def test_substring_cn(self):
        assert _is_similar_name("贾宝玉", "宝玉") is True

    def test_substring_reverse(self):
        assert _is_similar_name("宝玉", "贾宝玉") is True

    def test_parentheses_match(self):
        assert _is_similar_name("富爸爸", "富爸爸（罗伯特·清崎的父亲）") is True

    def test_parentheses_match_reverse(self):
        assert _is_similar_name("富爸爸（罗伯特·清崎的父亲）", "富爸爸") is True

    def test_not_similar(self):
        assert _is_similar_name("贾宝玉", "林黛玉") is False

    def test_empty(self):
        assert _is_similar_name("", "贾宝玉") is False
        assert _is_similar_name("贾宝玉", "") is False


class TestMergeCharacters:
    """测试人物合并功能。"""

    def test_merge_exact_match(self):
        existing = [{"name": "贾宝玉", "identity": "公子"}]
        new = [{"name": "贾宝玉", "personality": "叛逆"}]
        result = merge_characters(existing, new)
        assert len(result) == 1
        assert result[0]["name"] == "贾宝玉"
        assert result[0]["identity"] == "公子"
        assert result[0]["personality"] == "叛逆"

    def test_merge_substring_match(self):
        existing = [{"name": "贾宝玉", "identity": "公子"}]
        new = [{"name": "宝玉", "personality": "叛逆"}]
        result = merge_characters(existing, new)
        assert len(result) == 1
        assert result[0]["name"] in ["贾宝玉", "宝玉"]

    def test_merge_parentheses_match(self):
        existing = [{"name": "富爸爸", "identity": "罗伯特·清崎的父亲"}]
        new = [{"name": "富爸爸（罗伯特·清崎的父亲）", "personality": "智慧"}]
        result = merge_characters(existing, new)
        assert len(result) == 1
        # 应该合并为一个，使用更长的名字
        assert "富爸爸" in result[0]["name"]

    def test_merge_with_aliases(self):
        existing = [{"name": "孙悟空", "aliases": ["齐天大圣"]}]
        new = [{"name": "齐天大圣", "identity": "妖王"}]
        result = merge_characters(existing, new)
        assert len(result) == 1
        assert result[0]["name"] in ["孙悟空", "齐天大圣"]

    def test_merge_relationships(self):
        existing = [{"name": "贾宝玉", "relationships": [{"target": "林黛玉", "nature": "恋人"}]}]
        new = [{"name": "宝玉", "relationships": [{"target": "薛宝钗", "nature": "恋人"}]}]
        result = merge_characters(existing, new)
        assert len(result) == 1
        assert len(result[0]["relationships"]) == 2

    def test_no_match(self):
        existing = [{"name": "贾宝玉"}]
        new = [{"name": "林黛玉"}]
        result = merge_characters(existing, new)
        assert len(result) == 2

    def test_empty_existing(self):
        new = [{"name": "贾宝玉"}, {"name": "林黛玉"}]
        result = merge_characters([], new)
        assert len(result) == 2

    def test_empty_new(self):
        existing = [{"name": "贾宝玉"}]
        result = merge_characters(existing, [])
        assert len(result) == 1


class TestMergeSettings:
    """测试设定合并功能。"""

    def test_merge_exact_match(self):
        existing = [{"name": "荣国府", "description": "贾府"}]
        new = [{"name": "荣国府", "description": "贾府，又称荣禧堂"}]
        result = merge_settings(existing, new)
        assert len(result) == 1
        assert len(result[0]["description"]) > len(existing[0]["description"])

    def test_merge_substring_match(self):
        existing = [{"name": "花果山"}]
        new = [{"name": "花果山水帘洞"}]
        result = merge_settings(existing, new)
        assert len(result) == 1

    def test_merge_parentheses_match(self):
        existing = [{"name": "大观园"}]
        new = [{"name": "大观园（又名省亲别墅）"}]
        result = merge_settings(existing, new)
        assert len(result) == 1

    def test_no_match(self):
        existing = [{"name": "荣国府"}]
        new = [{"name": "宁国府"}]
        result = merge_settings(existing, new)
        assert len(result) == 2


class TestMergeEvents:
    """测试事件合并功能。"""

    def test_merge_exact_match(self):
        existing = [{"name": "黛玉进贾府", "participants": ["林黛玉"]}]
        new = [{"name": "黛玉进贾府", "participants": ["贾宝玉"]}]
        result = merge_events(existing, new)
        assert len(result) == 1
        assert len(result[0]["participants"]) == 2

    def test_merge_substring_match(self):
        existing = [{"name": "大闹天宫", "participants": ["孙悟空"]}]
        new = [{"name": "孙悟空大闹天宫", "participants": ["二郎神"]}]
        result = merge_events(existing, new)
        assert len(result) == 1
        assert len(result[0]["participants"]) == 2

    def test_merge_parentheses_match(self):
        existing = [{"name": "黛玉葬花"}]
        new = [{"name": "黛玉葬花（又名葬花吟）"}]
        result = merge_events(existing, new)
        assert len(result) == 1

    def test_no_match(self):
        existing = [{"name": "黛玉进贾府"}]
        new = [{"name": "宝钗扑蝶"}]
        result = merge_events(existing, new)
        assert len(result) == 2


class TestMergeChapterSummaries:
    """测试章节摘要合并功能。"""

    def test_empty_summaries(self):
        """空摘要列表返回空字符串。"""
        result = merge_chapter_summaries("测试作品", [])
        assert result == ""

    def test_single_summary(self):
        """单章摘要直接返回。"""
        result = merge_chapter_summaries("测试作品", ["第一章摘要"])
        assert result == "第一章摘要"

    @patch("src.pipeline.call_api")
    def test_merge_multiple_summaries(self, mock_api):
        """多章摘要调用AI合并。"""
        mock_api.return_value = "这是合并后的全书概要。"
        summaries = ["第1章摘要", "第2章摘要", "第3章摘要"]
        result = merge_chapter_summaries("测试作品", summaries)
        assert result == "这是合并后的全书概要。"
        assert mock_api.called

    @patch("src.pipeline.call_api")
    def test_merge_with_markdown_code_block(self, mock_api):
        """AI返回带代码块标记时自动清理。"""
        mock_api.return_value = '```\n这是合并后的全书概要。\n```'
        summaries = ["第1章摘要", "第2章摘要"]
        result = merge_chapter_summaries("测试作品", summaries)
        assert result == "这是合并后的全书概要。"

    @patch("src.pipeline.call_api")
    def test_merge_with_quotes(self, mock_api):
        """AI返回带引号时自动清理。"""
        mock_api.return_value = '"这是合并后的全书概要。"'
        summaries = ["第1章摘要", "第2章摘要"]
        result = merge_chapter_summaries("测试作品", summaries)
        assert result == "这是合并后的全书概要。"

    @patch("src.pipeline.call_api")
    def test_merge_fallback_on_error(self, mock_api):
        """AI调用失败时回退到简单拼接。"""
        mock_api.side_effect = RuntimeError("API Error")
        summaries = ["第1章摘要", "第2章摘要"]
        result = merge_chapter_summaries("测试作品", summaries)
        # 回退到简单拼接
        assert "第1章摘要" in result
        assert "第2章摘要" in result
        assert "；" in result

    @patch("src.pipeline.call_api")
    def test_merge_limits_summaries(self, mock_api):
        """超过30章时只处理前30章。"""
        mock_api.return_value = "合并概要"
        summaries = [f"第{i}章摘要" for i in range(40)]
        result = merge_chapter_summaries("测试作品", summaries)
        assert result == "合并概要"
        # 检查调用时只传了30章
        call_args = mock_api.call_args
        user_prompt = call_args[0][1]
        assert "第30章" in user_prompt
        assert "第31章" not in user_prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
