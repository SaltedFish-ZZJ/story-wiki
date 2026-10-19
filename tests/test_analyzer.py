"""
Story Wiki - AI 分析模块测试

覆盖 analyzer.py 中的所有核心函数：
- 内存监控、请求体检查
- 名称映射、名称解析
- 引用清理、模糊匹配
- 人物排序、势力分组、关系去重
- 上下文构建、上下文摘要生成
"""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.analyzer import (
    _get_memory_usage,
    _check_request_size,
    _build_name_map,
    _resolve_name,
    _clean_character_refs,
    _clean_setting_refs,
    _is_name_pair,
    _merge_similar_characters,
    _postprocess_result,
    _char_summary,
    _rank_characters,
    _group_by_faction,
    _format_faction_groups,
    _dedupe_relationships,
    _setting_summary,
    _build_chapter_context,
    generate_context_summary,
    analyze_text,
    analyze_chapter,
)
from src.name_matcher import _merge_group, _find_clusters


# ═══════════════════════════════════════════════════════════════
# 1. 内存监控与请求体检查
# ═══════════════════════════════════════════════════════════════

class TestMemoryUsage:
    """测试 _get_memory_usage 函数。"""

    def test_returns_dict(self):
        result = _get_memory_usage()
        assert isinstance(result, dict)
        assert "rss_mb" in result
        assert "vms_mb" in result

    def test_values_are_floats(self):
        result = _get_memory_usage()
        assert isinstance(result["rss_mb"], (int, float))
        assert isinstance(result["vms_mb"], (int, float))


class TestCheckRequestSize:
    """测试 _check_request_size 函数。"""

    def test_normal_payload(self):
        payload = {"model": "test", "messages": [{"role": "user", "content": "hello"}]}
        is_ok, msg = _check_request_size(payload)
        assert is_ok is True
        assert msg == ""

    def test_large_payload_warning(self):
        # 创建一个足够大的 payload 触发警告（>10MB）
        large_content = "x" * (11 * 1024 * 1024)  # 11MB
        payload = {"content": large_content}
        is_ok, msg = _check_request_size(payload)
        assert is_ok is True
        assert "⚠️" in msg or "请求体较大" in msg

    def test_empty_payload(self):
        is_ok, msg = _check_request_size({})
        assert is_ok is True


# ═══════════════════════════════════════════════════════════════
# 2. 名称映射与名称解析
# ═══════════════════════════════════════════════════════════════

class TestBuildNameMap:
    """测试 _build_name_map 函数。"""

    def test_basic_mapping(self):
        characters = [
            {"name": "贾宝玉", "aliases": ["宝玉", "宝二爷"]},
            {"name": "林黛玉", "aliases": ["黛玉"]},
        ]
        name_map = _build_name_map(characters)
        assert name_map["贾宝玉"] == "贾宝玉"
        assert name_map["宝玉"] == "贾宝玉"
        assert name_map["宝二爷"] == "贾宝玉"
        assert name_map["林黛玉"] == "林黛玉"
        assert name_map["黛玉"] == "林黛玉"

    def test_empty_characters(self):
        assert _build_name_map([]) == {}

    def test_no_aliases(self):
        characters = [{"name": "张三"}]
        name_map = _build_name_map(characters)
        assert name_map["张三"] == "张三"
        assert len(name_map) == 1

    def test_empty_name_ignored(self):
        characters = [{"name": "", "aliases": ["别名"]}]
        name_map = _build_name_map(characters)
        # 空名字的角色不参与映射
        assert "别名" not in name_map


class TestResolveName:
    """测试 _resolve_name 函数。"""

    def test_exact_match(self):
        name_map = {"贾宝玉": "贾宝玉", "宝玉": "贾宝玉"}
        assert _resolve_name("贾宝玉", name_map) == "贾宝玉"

    def test_alias_match(self):
        name_map = {"贾宝玉": "贾宝玉", "宝玉": "贾宝玉"}
        assert _resolve_name("宝玉", name_map) == "贾宝玉"

    def test_unknown_name_returns_original(self):
        name_map = {"贾宝玉": "贾宝玉"}
        assert _resolve_name("王熙凤", name_map) == "王熙凤"


# ═══════════════════════════════════════════════════════════════
# 3. 引用清理
# ═══════════════════════════════════════════════════════════════

class TestCleanCharacterRefs:
    """测试 _clean_character_refs 函数。"""

    def test_removes_invalid_relationships(self):
        characters = [
            {
                "name": "A",
                "relationships": [
                    {"target": "B", "nature": "朋友"},
                    {"target": "不存在的人", "nature": "敌对"},
                ],
                "related_settings": ["设定1", "设定2"],
            }
        ]
        name_map = {"A": "A", "B": "B"}
        setting_names = {"设定1"}

        _clean_character_refs(characters, setting_names, name_map)
        rels = characters[0]["relationships"]
        assert len(rels) == 1
        assert rels[0]["target"] == "B"
        assert characters[0]["related_settings"] == ["设定1"]

    def test_empty_characters(self):
        _clean_character_refs([], set(), {})


class TestCleanSettingRefs:
    """测试 _clean_setting_refs 函数。"""

    def test_removes_invalid_references(self):
        settings = [
            {
                "name": "设定1",
                "related_characters": ["A", "不存在的人"],
                "related_settings": ["设定2", "不存在的设定"],
            }
        ]
        char_names = {"A"}
        setting_names = {"设定1", "设定2"}

        _clean_setting_refs(settings, char_names, setting_names)
        assert settings[0]["related_characters"] == ["A"]
        assert settings[0]["related_settings"] == ["设定2"]

    def test_removes_self_reference(self):
        settings = [
            {
                "name": "设定1",
                "related_characters": [],
                "related_settings": ["设定1"],
            }
        ]
        _clean_setting_refs(settings, set(), {"设定1"})
        assert settings[0]["related_settings"] == []


# ═══════════════════════════════════════════════════════════════
# 4. 模糊匹配与人物合并
# ═══════════════════════════════════════════════════════════════

class TestIsNamePair:
    """测试 _is_name_pair 函数。"""

    def test_exact_substring(self):
        assert _is_name_pair("宝玉", "贾宝玉") is True

    def test_reverse_substring(self):
        assert _is_name_pair("贾宝玉", "宝玉") is True

    def test_not_substring(self):
        assert _is_name_pair("林黛玉", "贾宝玉") is False

    def test_empty_name(self):
        assert _is_name_pair("", "宝玉") is False
        assert _is_name_pair("宝玉", "") is False

    def test_single_char_too_short(self):
        assert _is_name_pair("玉", "宝玉") is False

    def test_length_diff_too_large(self):
        # "林" 是 "林黛玉" 的前缀，但长度差异 > 60%
        assert _is_name_pair("林", "林黛玉") is False


class TestMergeGroup:
    """测试 _merge_group 函数。"""

    def test_merges_names_and_relationships(self):
        group = [
            {
                "name": "宝玉",
                "aliases": ["宝二爷"],
                "relationships": [{"target": "黛玉", "nature": "恋人"}],
                "related_settings": ["大观园"],
            },
            {
                "name": "贾宝玉",
                "aliases": ["怡红公子"],
                "relationships": [{"target": "黛玉", "nature": "恋人"}, {"target": "宝钗", "nature": "朋友"}],
                "related_settings": ["荣国府"],
            },
        ]
        merged = _merge_group(group)
        # 最长名字作为标准名
        assert merged["name"] == "贾宝玉"
        # 别名合并去重
        aliases = set(merged["aliases"])
        assert "宝玉" in aliases
        assert "宝二爷" in aliases
        assert "怡红公子" in aliases
        # 关系合并去重
        rel_targets = {r["target"] for r in merged["relationships"]}
        assert "黛玉" in rel_targets
        assert "宝钗" in rel_targets
        # 设定合并
        assert set(merged["related_settings"]) == {"大观园", "荣国府"}


class TestFindClusters:
    """测试 _find_clusters 函数。"""

    def test_basic_clustering(self):
        characters = [
            {"name": "宝玉"},
            {"name": "贾宝玉"},
            {"name": "林黛玉"},
            {"name": "黛玉"},
        ]
        clusters = _find_clusters(characters)
        # 应该分两组：[宝玉, 贾宝玉] 和 [林黛玉, 黛玉]
        assert len(clusters) == 2
        for cluster in clusters:
            assert len(cluster) == 2

    def test_no_duplicates(self):
        characters = [{"name": "A"}, {"name": "B"}, {"name": "C"}]
        clusters = _find_clusters(characters)
        assert len(clusters) == 3


class TestMergeSimilarCharacters:
    """测试 _merge_similar_characters 函数。"""

    def test_merges_similar(self):
        characters = [
            {"name": "宝玉", "aliases": [], "relationships": [], "related_settings": []},
            {"name": "贾宝玉", "aliases": ["宝二爷"], "relationships": [], "related_settings": []},
            {"name": "林黛玉", "aliases": [], "relationships": [], "related_settings": []},
        ]
        result = _merge_similar_characters(characters)
        assert len(result) == 2  # 宝玉和贾宝玉应该合并

    def test_single_character(self):
        characters = [{"name": "A"}]
        result = _merge_similar_characters(characters)
        assert len(result) == 1

    def test_empty_list(self):
        assert _merge_similar_characters([]) == []


class TestPostprocessResult:
    """测试 _postprocess_result 函数。"""

    def test_basic_postprocess(self):
        result = {
            "characters": [
                {"name": "宝玉", "aliases": [], "relationships": [], "related_settings": ["大观园"]},
                {"name": "贾宝玉", "aliases": ["宝二爷"], "relationships": [], "related_settings": ["荣国府"]},
            ],
            "settings": [
                {"name": "大观园", "type": "地点", "related_characters": [], "related_settings": []},
            ],
        }
        processed = _postprocess_result(result)
        # 宝玉和贾宝玉应该合并
        assert len(processed["characters"]) == 1
        assert processed["characters"][0]["name"] == "贾宝玉"


# ═══════════════════════════════════════════════════════════════
# 5. 人物排序与势力分组
# ═══════════════════════════════════════════════════════════════

class TestCharSummary:
    """测试 _char_summary 函数。"""

    def test_full_info(self):
        c = {"name": "贾宝玉", "identity": "荣国府公子", "faction": "荣国府"}
        summary = _char_summary(c)
        assert "贾宝玉" in summary
        assert "荣国府公子" in summary
        assert "荣国府" in summary

    def test_minimal_info(self):
        c = {"name": "路人甲"}
        summary = _char_summary(c)
        assert "路人甲" in summary


class TestRankCharacters:
    """测试 _rank_characters 函数。"""

    def test主角_before_配角(self):
        characters = [
            {"name": "配角", "role_tags": ["配角"], "relationships": [], "status": "活跃"},
            {"name": "主角", "role_tags": ["主角"], "relationships": [], "status": "活跃"},
        ]
        main, minor = _rank_characters(characters)
        assert main[0]["name"] == "主角"

    def test_empty(self):
        main, minor = _rank_characters([])
        assert main == []
        assert minor == []

    def test_fewer_than_20_all_main(self):
        characters = [{"name": f"角色{i}", "role_tags": [], "relationships": [], "status": "活跃"} for i in range(15)]
        main, minor = _rank_characters(characters)
        assert len(main) == 15
        assert len(minor) == 0

    def test_more_than_20_split(self):
        characters = [{"name": f"角色{i}", "role_tags": [], "relationships": [], "status": "活跃"} for i in range(25)]
        main, minor = _rank_characters(characters)
        assert len(main) == 20
        assert len(minor) == 5


class TestGroupByFaction:
    """测试 _group_by_faction 函数。"""

    def test_basic_grouping(self):
        chars = [
            {"name": "A", "faction": "荣国府"},
            {"name": "B", "faction": "荣国府"},
            {"name": "C", "faction": "宁国府"},
        ]
        groups = _group_by_faction(chars)
        assert "荣国府" in groups
        assert "宁国府" in groups
        assert set(groups["荣国府"]) == {"A", "B"}

    def test_no_faction_goes_to_other(self):
        chars = [{"name": "A", "faction": None}]
        groups = _group_by_faction(chars)
        assert "其他" in groups


class TestFormatFactionGroups:
    """测试 _format_faction_groups 函数。"""

    def test_basic_format(self):
        groups = {"荣国府": ["A", "B"], "宁国府": ["C"]}
        result = _format_faction_groups(groups)
        assert "荣国府" in result
        assert "A" in result
        assert "、" in result


# ═══════════════════════════════════════════════════════════════
# 6. 关系去重与设定摘要
# ═══════════════════════════════════════════════════════════════

class TestDedupeRelationships:
    """测试 _dedupe_relationships 函数。"""

    def test_dedupes_same_relationship(self):
        characters = [
            {
                "name": "A", "role_tags": ["主角"],
                "relationships": [{"target": "B", "nature": "朋友"}],
            },
            {
                "name": "B", "role_tags": ["配角"],
                "relationships": [{"target": "A", "nature": "朋友"}],
            },
        ]
        result = _dedupe_relationships(characters)
        assert len(result) == 1  # A—朋友—B 和 B—朋友—A 应去重

    def test_empty(self):
        assert _dedupe_relationships([]) == []


class TestSettingSummary:
    """测试 _setting_summary 函数。"""

    def test_with_type(self):
        s = {"name": "大观园", "type": "地点"}
        assert _setting_summary(s) == "大观园（地点）"

    def test_without_type(self):
        s = {"name": "大观园"}
        assert _setting_summary(s) == "大观园"


# ═══════════════════════════════════════════════════════════════
# 7. 上下文构建与摘要生成
# ═══════════════════════════════════════════════════════════════

class TestBuildChapterContext:
    """测试 _build_chapter_context 函数。"""

    def test_empty_context(self):
        result = _build_chapter_context([], [])
        assert "暂无已知信息" in result

    def test_with_characters(self):
        characters = [
            {
                "name": "贾宝玉", "identity": "公子", "faction": "荣国府",
                "role_tags": ["主角"], "relationships": [{"target": "林黛玉", "nature": "恋人"}],
                "status": "活跃",
            },
        ]
        result = _build_chapter_context(characters, [])
        assert "贾宝玉" in result

    def test_with_events(self):
        events = [{"name": "宝黛初见"}]
        result = _build_chapter_context([], [], events)
        assert "宝黛初见" in result


class TestGenerateContextSummary:
    """测试 generate_context_summary 函数。"""

    def test_basic_summary(self):
        analysis = {
            "characters": [
                {
                    "name": "贾宝玉", "identity": "公子", "role_tags": ["主角"],
                    "relationships": [{"target": "A", "nature": "朋友"}], "status": "活跃",
                },
            ],
            "settings": [{"name": "大观园", "type": "地点"}],
            "events": [{"name": "宝黛初见", "importance": "高"}],
            "chapter_summary": "本章介绍了主要人物。",
        }
        summary = generate_context_summary(analysis)
        assert "贾宝玉" in summary
        assert "大观园" in summary
        assert "宝黛初见" in summary
        assert "本章介绍了主要人物" in summary

    def test_empty_analysis(self):
        summary = generate_context_summary({})
        assert summary == ""

    def test_max_length(self):
        analysis = {
            "characters": [
                {"name": f"人物{i}", "role_tags": [], "relationships": [], "status": "活跃"}
                for i in range(20)
            ],
        }
        summary = generate_context_summary(analysis, max_length=50)
        assert len(summary) <= 50


# ═══════════════════════════════════════════════════════════════
# 8. API 调用（mock）
# ═══════════════════════════════════════════════════════════════

class TestAnalyzeText:
    """测试 analyze_text 函数（mock API 调用）。"""

    @patch("src.analyzer._call_deepseek")
    @patch("src.analyzer._save_raw_response")
    def test_basic_analysis(self, mock_save, mock_call):
        mock_call.return_value = json.dumps({
            "title": "测试作品",
            "characters": [
                {"name": "主角", "aliases": [], "identity": "英雄", "personality": "勇敢",
                 "gender": "男", "faction": "", "role_tags": ["主角"], "status": "活跃",
                 "quotes": [], "related_settings": [], "relationships": []},
            ],
            "settings": [],
            "events": [],
            "summary": "测试摘要",
        }, ensure_ascii=False)

        result = analyze_text("测试文本内容")
        assert result["title"] == "测试作品"
        assert len(result["characters"]) == 1

    @patch("src.analyzer._call_deepseek")
    @patch("src.analyzer._save_raw_response")
    def test_title_override(self, mock_save, mock_call):
        mock_call.return_value = json.dumps({
            "title": "原始标题",
            "characters": [], "settings": [], "events": [], "summary": "",
        }, ensure_ascii=False)

        result = analyze_text("测试文本", title="自定义标题")
        assert result["title"] == "自定义标题"


class TestAnalyzeChapter:
    """测试 analyze_chapter 函数（mock API 调用）。"""

    @patch("src.analyzer._call_deepseek_with_prompt")
    @patch("src.analyzer._save_raw_response")
    def test_basic_chapter_analysis(self, mock_save, mock_call):
        mock_call.return_value = json.dumps({
            "characters": [
                {"name": "新人物", "aliases": [], "identity": "路人", "personality": "普通",
                 "gender": "男", "faction": "", "role_tags": [], "status": "活跃",
                 "quotes": [], "related_settings": [], "relationships": []},
            ],
            "settings": [],
            "events": [],
            "chapter_summary": "本章摘要",
        }, ensure_ascii=False)

        result = analyze_chapter("章节文本", chapter_title="第一章")
        assert "characters" in result
        assert result["chapter_summary"] == "本章摘要"

    @patch("src.analyzer._call_deepseek_with_prompt")
    @patch("src.analyzer._save_raw_response")
    def test_with_known_context(self, mock_save, mock_call):
        mock_call.return_value = json.dumps({
            "characters": [], "settings": [], "events": [], "chapter_summary": "",
        }, ensure_ascii=False)

        known_chars = [{"name": "已知人物", "role_tags": [], "relationships": [], "status": "活跃"}]
        result = analyze_chapter("章节文本", known_characters=known_chars)
        assert "characters" in result


class TestCausalChainPrompt:
    """因果链 prompt 加固：cause/effect 不再是「可选」，必须引导 LLM 填事件名。"""

    def test_system_prompt_requires_causal_chain(self):
        from src.analyzer import SYSTEM_PROMPT
        assert "因果链是知识库的核心价值" in SYSTEM_PROMPT
        assert "一字不差" in SYSTEM_PROMPT
        # cause/effect 的 schema 描述不再用「可选」弱化
        assert "前置事件名（可选）" not in SYSTEM_PROMPT
        assert "后果或影响（可选）" not in SYSTEM_PROMPT
        # effect 明确要求事件名而非描述文字
        assert "不是后果描述" in SYSTEM_PROMPT or "不要填描述性文字" in SYSTEM_PROMPT

    def test_chapter_prompt_requires_causal_chain(self):
        from src.analyzer import CHAPTER_SYSTEM_PROMPT
        assert "因果链是知识库的核心价值" in CHAPTER_SYSTEM_PROMPT
        assert "由那一章的 cause 回填" in CHAPTER_SYSTEM_PROMPT
        assert "前置事件名（可选）" not in CHAPTER_SYSTEM_PROMPT
        assert "导致的后果（可选）" not in CHAPTER_SYSTEM_PROMPT

    def test_chapter_prompt_injects_known_events(self):
        """跨章因果链的原料：上下文必须包含已知事件名。"""
        from src.analyzer import _build_chapter_context
        ctx = _build_chapter_context(
            known_characters=[], known_settings=[],
            known_events=[{"name": "蟠桃会"}])
        assert "已知事件" in ctx and "蟠桃会" in ctx

    def test_skill_md_aligned_with_prompt(self):
        """SKILL.md 与内置 prompt 因果链措辞一致，防止两边漂移。"""
        skill = (Path(__file__).resolve().parent.parent
                 / "skills" / "story-wiki" / "SKILL.md").read_text(encoding="utf-8")
        assert "因果链是核心价值" in skill
        assert "不是后果描述文字" in skill
