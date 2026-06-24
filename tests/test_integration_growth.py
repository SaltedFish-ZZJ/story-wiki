"""
Story Wiki - 角色成长曲线集成测试

测试从知识库分析角色成长、成长曲线生成、Mermaid可视化生成，
以及与VaultManager的集成。
"""
import json
import sys
from pathlib import Path
from typing import List

import pytest

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.interfaces import Character, GrowthEvent, CharacterGrowthCurve
from src.vault_manager import VaultManager
from src.character_growth import (
    CharacterGrowthTracker,
    extract_growth_from_chapter_analysis,
    batch_extract_growth_events,
    save_all_growth_events,
)


# ── 测试数据 ──────────────────────────────────────────────────


@pytest.fixture
def sample_analysis_result():
    """返回一个标准的分析结果字典，包含成长事件数据。"""
    return {
        "title": "测试作品",
        "characters": [
            {
                "name": "林黛玉",
                "identity": "贾府表小姐",
                "personality": "敏感多愁",
                "current_state": "初入贾府，寄人篱下",
                "relationships": [
                    {"target": "贾宝玉", "nature": "恋人"},
                    {"target": "薛宝钗", "nature": "对手"},
                ],
            },
            {
                "name": "贾宝玉",
                "identity": "贾府公子",
                "personality": "叛逆多情",
                "current_state": "在贾府中嬉戏",
                "relationships": [
                    {"target": "林黛玉", "nature": "恋人"},
                ],
            },
        ],
        "events": [
            {
                "name": "宝黛初见",
                "time": "第3回",
                "participants": ["林黛玉", "贾宝玉"],
                "importance": "高",
                "description": "林黛玉初入贾府，与贾宝玉初次相见，似曾相识",
            },
            {
                "name": "黛玉葬花",
                "time": "第27回",
                "participants": ["林黛玉"],
                "importance": "高",
                "description": "林黛玉感伤身世，葬花吟诗",
            },
            {
                "name": "宝玉挨打",
                "time": "第33回",
                "participants": ["贾宝玉"],
                "importance": "高",
                "description": "贾宝玉因与戏子交往被贾政责打",
            },
        ],
        "settings": [],
        "summary": "测试作品的AI摘要",
    }


@pytest.fixture
def vault_with_characters(tmp_path):
    """创建一个包含人物卡片的测试Vault目录。"""
    book_dir = tmp_path / "测试作品"
    char_dir = book_dir / "characters"
    char_dir.mkdir(parents=True)

    # 创建林黛玉卡片
    lin_daiyu_card = """---
type: character
gender: 女
faction: 贾府
---

# 林黛玉

> 活跃

## 身份
贾府表小姐

## 性格
敏感多愁

## 人际关系
- [[characters/贾宝玉|贾宝玉]] — 恋人
- [[characters/薛宝钗|薛宝钗]] — 对手
"""
    (char_dir / "林黛玉.md").write_text(lin_daiyu_card, encoding="utf-8")

    # 创建贾宝玉卡片
    jia_baoyu_card = """---
type: character
gender: 男
faction: 贾府
---

# 贾宝玉

> 活跃

## 身份
贾府公子

## 性格
叛逆多情

## 人际关系
- [[characters/林黛玉|林黛玉]] — 恋人
"""
    (char_dir / "贾宝玉.md").write_text(jia_baoyu_card, encoding="utf-8")

    return book_dir


# ── 集成测试 ──────────────────────────────────────────────────


class TestGrowthEventExtraction:
    """测试从分析结果中提取成长事件。"""

    def test_extract_growth_events_from_analysis(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试从章节分析结果中提取成长事件。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        events = tracker.extract_growth_events_from_analysis(
            sample_analysis_result, chapter="第1章"
        )

        # 应该提取到多个成长事件
        assert len(events) > 0

        # 检查事件类型
        event_types = {e.growth_type for e in events}
        assert "状态" in event_types  # 从 current_state 提取
        assert "关系" in event_types  # 从 relationships 提取

    def test_extract_high_importance_events(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试提取高重要性事件。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        events = tracker.extract_growth_events_from_analysis(
            sample_analysis_result, chapter="第1章"
        )

        # 找出高重要性事件
        high_sig_events = [e for e in events if e.significance == "高"]
        assert len(high_sig_events) >= 2  # 宝黛初见、黛玉葬花等

    def test_growth_type_inference(self, sample_analysis_result, vault_with_characters, tmp_path):
        """测试成长类型推断。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        events = tracker.extract_growth_events_from_analysis(
            sample_analysis_result, chapter="第1章"
        )

        # 检查成长事件的类型推断
        for event in events:
            assert event.growth_type in [
                "实力", "地位", "情感", "认知", "关系", "性格", "命运", "状态", "其他"
            ]


class TestGrowthCurveGeneration:
    """测试成长曲线生成。"""

    def test_get_growth_curve_with_events(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试获取有成长事件的角色曲线。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        # 先提取并保存成长事件
        events = tracker.extract_growth_events_from_analysis(
            sample_analysis_result, chapter="第1章"
        )
        tracker.save_growth_events("林黛玉", events)

        # 获取成长曲线
        curve = tracker.get_character_growth_curve("林黛玉")

        assert curve is not None
        assert isinstance(curve, CharacterGrowthCurve)
        assert curve.character_name == "林黛玉"
        assert len(curve.growth_events) > 0
        assert curve.summary != ""
        assert curve.overall_trend != ""

    def test_get_growth_curve_empty(self, vault_with_characters, tmp_path):
        """测试获取没有成长事件的角色曲线。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        curve = tracker.get_character_growth_curve("贾宝玉")

        assert curve is not None
        assert isinstance(curve, CharacterGrowthCurve)
        assert curve.character_name == "贾宝玉"
        assert len(curve.growth_events) == 0
        assert "暂无成长记录" in curve.summary

    def test_get_growth_curve_nonexistent(self, vault_with_characters, tmp_path):
        """测试获取不存在角色的成长曲线。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        curve = tracker.get_character_growth_curve("不存在的角色")

        assert curve is None

    def test_growth_phases_analysis(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试成长阶段分析。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        events = tracker.extract_growth_events_from_analysis(
            sample_analysis_result, chapter="第1章"
        )
        tracker.save_growth_events("林黛玉", events)

        curve = tracker.get_character_growth_curve("林黛玉")

        assert curve is not None
        assert isinstance(curve.growth_phases, list)
        # 应该有至少一个成长阶段
        if curve.growth_events:
            assert len(curve.growth_phases) > 0


class TestGrowthChartVisualization:
    """测试成长曲线图表数据生成。"""

    def test_generate_chart_data(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试生成图表数据。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        events = tracker.extract_growth_events_from_analysis(
            sample_analysis_result, chapter="第1章"
        )
        tracker.save_growth_events("林黛玉", events)

        chart_data = tracker.generate_growth_chart_data("林黛玉")

        assert isinstance(chart_data, dict)
        assert "character_name" in chart_data
        assert "summary" in chart_data
        assert "overall_trend" in chart_data
        assert "timeline" in chart_data
        assert "growth_phases" in chart_data
        assert "total_events" in chart_data
        assert chart_data["total_events"] > 0

    def test_chart_data_nonexistent_character(self, vault_with_characters, tmp_path):
        """测试不存在角色的图表数据。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        chart_data = tracker.generate_growth_chart_data("不存在的角色")

        assert isinstance(chart_data, dict)
        assert "error" in chart_data

    def test_chart_timeline_structure(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试图表时间线结构。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        events = tracker.extract_growth_events_from_analysis(
            sample_analysis_result, chapter="第1章"
        )
        tracker.save_growth_events("林黛玉", events)

        chart_data = tracker.generate_growth_chart_data("林黛玉")

        assert isinstance(chart_data["timeline"], list)
        for chapter_data in chart_data["timeline"]:
            assert "chapter" in chapter_data
            assert "events" in chapter_data
            assert "total" in chapter_data
            assert "high_significance" in chapter_data


class TestBatchGrowthExtraction:
    """测试批量成长事件提取。"""

    def test_batch_extract_growth_events(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试从多个章节分析结果中批量提取成长事件。"""
        chapter_analyses = [
            sample_analysis_result,
            sample_analysis_result,  # 模拟第二章
        ]

        character_events = batch_extract_growth_events(
            vault_with_characters.parent, "测试作品", chapter_analyses
        )

        assert isinstance(character_events, dict)
        assert len(character_events) > 0

        # 检查每个角色的事件列表
        for char_name, events in character_events.items():
            assert isinstance(events, list)
            assert len(events) > 0

    def test_save_all_growth_events(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试保存所有成长事件到知识库。"""
        chapter_analyses = [sample_analysis_result]

        character_events = batch_extract_growth_events(
            vault_with_characters.parent, "测试作品", chapter_analyses
        )

        # 保存事件
        save_all_growth_events(
            vault_with_characters.parent, "测试作品", character_events
        )

        # 验证保存成功 - 读取人物卡片文件
        char_file = vault_with_characters / "characters" / "林黛玉.md"
        assert char_file.exists()


class TestVaultManagerIntegration:
    """测试与VaultManager的集成。"""

    def test_vault_manager_load_character(
        self, vault_with_characters, tmp_path
    ):
        """测试VaultManager加载人物。"""
        vm = VaultManager({
            "vault_dir": str(vault_with_characters.parent),
            "book_title": "测试作品",
        })

        character = vm.load_character("林黛玉")

        assert character is not None
        assert isinstance(character, Character)
        assert character.name == "林黛玉"
        assert character.identity == "贾府表小姐"

    def test_vault_manager_update_character(
        self, vault_with_characters, tmp_path
    ):
        """测试VaultManager更新人物。"""
        vm = VaultManager({
            "vault_dir": str(vault_with_characters.parent),
            "book_title": "测试作品",
        })

        # 更新人物状态
        updates = {
            "current_state": "状态更新后的描述",
            "growth_events": [
                {
                    "chapter": "第1章",
                    "event_name": "测试成长事件",
                    "growth_type": "认知",
                    "significance": "高",
                }
            ],
        }
        vm.update_character("林黛玉", updates)

        # 验证更新
        character = vm.load_character("林黛玉")
        assert character.current_state == "状态更新后的描述"
        assert len(character.growth_events) == 1

    def test_character_growth_tracker_with_vault(
        self, vault_with_characters, tmp_path
    ):
        """测试CharacterGrowthTracker与VaultManager集成。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        # 验证tracker内部有vault_manager
        assert tracker.vault_manager is not None

        # 验证可以加载人物
        character = tracker.vault_manager.load_character("林黛玉")
        assert character is not None

    def test_growth_events_persistence(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试成长事件的持久化。"""
        tracker1 = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        # 提取并保存
        events = tracker1.extract_growth_events_from_analysis(
            sample_analysis_result, chapter="第1章"
        )
        tracker1.save_growth_events("林黛玉", events)

        # 创建新的tracker实例验证持久化
        tracker2 = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")
        curve = tracker2.get_character_growth_curve("林黛玉")

        assert curve is not None
        assert len(curve.growth_events) > 0


class TestHelperFunctions:
    """测试辅助函数。"""

    def test_extract_growth_from_chapter_analysis(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试从章节内容中提取成长事件的辅助函数。"""
        events = extract_growth_from_chapter_analysis(
            sample_analysis_result, chapter_num=1
        )

        assert isinstance(events, list)
        assert len(events) > 0
        for event in events:
            assert isinstance(event, GrowthEvent)

    def test_growth_event_to_dict(self, vault_with_characters, tmp_path):
        """测试成长事件字典转换。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        event = GrowthEvent(
            chapter="第1章",
            time="第3回",
            event_name="宝黛初见",
            description="初见似曾相识",
            state_before="",
            state_after="",
            growth_type="情感",
            significance="高",
        )

        event_dict = tracker._growth_event_to_dict(event)

        assert isinstance(event_dict, dict)
        assert event_dict["chapter"] == "第1章"
        assert event_dict["event_name"] == "宝黛初见"
        assert event_dict["growth_type"] == "情感"
        assert event_dict["significance"] == "高"

    def test_dict_to_growth_event(self, vault_with_characters, tmp_path):
        """测试字典转成长事件。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        event_dict = {
            "chapter": "第2章",
            "time": "",
            "event_name": "测试事件",
            "description": "测试描述",
            "state_before": "",
            "state_after": "新状态",
            "growth_type": "实力",
            "significance": "中",
        }

        event = tracker._dict_to_growth_event(event_dict)

        assert isinstance(event, GrowthEvent)
        assert event.chapter == "第2章"
        assert event.event_name == "测试事件"
        assert event.growth_type == "实力"


class TestGrowthTrendAndSummary:
    """测试成长趋势和摘要生成。"""

    def test_trend_description(self, sample_analysis_result, vault_with_characters, tmp_path):
        """测试趋势描述生成。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        events = tracker.extract_growth_events_from_analysis(
            sample_analysis_result, chapter="第1章"
        )
        tracker.save_growth_events("林黛玉", events)

        curve = tracker.get_character_growth_curve("林黛玉")

        # 趋势描述应包含关键信息
        assert curve.overall_trend != ""
        assert "成长事件" in curve.overall_trend or "发展" in curve.overall_trend

    def test_growth_summary(
        self, sample_analysis_result, vault_with_characters, tmp_path
    ):
        """测试成长摘要生成。"""
        tracker = CharacterGrowthTracker(vault_with_characters.parent, "测试作品")

        events = tracker.extract_growth_events_from_analysis(
            sample_analysis_result, chapter="第1章"
        )
        tracker.save_growth_events("林黛玉", events)

        curve = tracker.get_character_growth_curve("林黛玉")

        # 摘要应包含角色名和事件统计
        assert curve.summary != ""
        assert "林黛玉" in curve.summary
        assert "成长事件" in curve.summary
