"""
Story Wiki - 角色成长曲线模块测试
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.interfaces import Character, GrowthEvent, CharacterGrowthCurve, Event
from src.character_growth import (
    CharacterGrowthTracker,
    extract_growth_from_chapter_analysis,
    batch_extract_growth_events,
    save_all_growth_events,
    analyze_character_growth,
    extract_growth_events,
    classify_growth_type,
    划分成长阶段,
    generate_growth_curve,
    render_growth_mermaid,
    GROWTH_TYPES,
)


class TestGrowthEvent:
    """测试 GrowthEvent 数据结构"""

    def test_create_growth_event(self):
        """测试创建 GrowthEvent 对象"""
        event = GrowthEvent(
            chapter="第1章",
            time="2024年",
            event_name="角色突破",
            description="角色突破瓶颈",
            state_before="普通",
            state_after="强者",
            growth_type="实力",
            significance="高"
        )

        assert event.chapter == "第1章"
        assert event.time == "2024年"
        assert event.event_name == "角色突破"
        assert event.growth_type == "实力"
        assert event.significance == "高"

    def test_growth_event_defaults(self):
        """测试 GrowthEvent 默认值"""
        event = GrowthEvent(event_name="测试事件")

        assert event.chapter == ""
        assert event.time == ""
        assert event.growth_type == ""
        assert event.significance == "中"


class TestCharacterGrowthCurve:
    """测试 CharacterGrowthCurve 数据结构"""

    def test_create_growth_curve(self):
        """测试创建 CharacterGrowthCurve 对象"""
        curve = CharacterGrowthCurve(
            character_name="林黛玉",
            growth_events=[],
            summary="无成长记录",
            growth_phases=[],
            overall_trend="无数据"
        )

        assert curve.character_name == "林黛玉"
        assert len(curve.growth_events) == 0
        assert curve.overall_trend == "无数据"


class TestCharacterGrowthTracker:
    """测试 CharacterGrowthTracker"""

    def test_extract_growth_events_from_analysis(self, tmp_path):
        """测试从分析结果提取成长事件"""
        tracker = CharacterGrowthTracker(vault_dir=tmp_path, book_title="测试作品")

        analysis_result = {
            "characters": [
                {
                    "name": "林黛玉",
                    "identity": "贾府表小姐",
                    "personality": "多愁善感",
                    "current_state": "与贾宝玉两情相悦",
                    "relationships": [
                        {"target": "贾宝玉", "nature": "恋人"}
                    ]
                }
            ],
            "events": [
                {
                    "name": "宝黛初见",
                    "time": "某年春天",
                    "participants": ["林黛玉", "贾宝玉"],
                    "description": "二人初次见面",
                    "importance": "高"
                }
            ],
            "summary": "林黛玉进贾府"
        }

        events = tracker.extract_growth_events_from_analysis(analysis_result, "第1章")

        assert len(events) > 0
        # 应该有状态更新、关系变化和重要事件
        event_names = [e.event_name for e in events]
        assert any("林黛玉" in name for name in event_names)

    def test_infer_growth_type(self, tmp_path):
        """测试推断成长类型"""
        tracker = CharacterGrowthTracker(vault_dir=tmp_path, book_title="测试作品")

        # 实力相关
        event1 = {"name": "修炼突破", "description": "角色实力提升"}
        assert tracker._infer_growth_type(event1) == "实力"

        # 地位相关
        event2 = {"name": "加冕为王", "description": "角色登上王位"}
        assert tracker._infer_growth_type(event2) == "地位"

        # 情感相关
        event3 = {"name": "表白心意", "description": "角色向爱人表白"}
        assert tracker._infer_growth_type(event3) == "情感"

        # 认知相关
        event4 = {"name": "领悟真谛", "description": "角色领悟人生道理"}
        assert tracker._infer_growth_type(event4) == "认知"

        # 关系相关
        event5 = {"name": "结盟成功", "description": "与其他势力结盟"}
        assert tracker._infer_growth_type(event5) == "关系"

    def test_save_and_get_growth_events(self, tmp_path):
        """测试保存和获取成长事件"""
        # 创建 Vault 结构
        vault_dir = tmp_path / "test_vault" / "test_book"
        vault_dir.mkdir(parents=True)
        char_dir = vault_dir / "characters"
        char_dir.mkdir()

        # 创建测试人物卡片
        char_file = char_dir / "林黛玉.md"
        char_file.write_text(
            """---
type: character
gender: 女
tags: [character]
---

# 林黛玉

> 活跃

## 身份
贾府表小姐

## 性格
多愁善感

## 人际关系
- [[characters/贾宝玉|贾宝玉]] — 恋人
""",
            encoding="utf-8"
        )

        # 初始化追踪器
        tracker = CharacterGrowthTracker(
            vault_dir=tmp_path / "test_vault",
            book_title="test_book"
        )

        # 创建成长事件
        events = [
            GrowthEvent(
                chapter="第1章",
                time="春天",
                event_name="林黛玉进贾府",
                description="林黛玉初入贾府",
                state_before="",
                state_after="贾府表小姐",
                growth_type="地位",
                significance="高"
            )
        ]

        # 保存成长事件
        tracker.save_growth_events("林黛玉", events)

        # 获取成长曲线
        curve = tracker.get_character_growth_curve("林黛玉")

        assert curve is not None
        assert curve.character_name == "林黛玉"
        assert len(curve.growth_events) == 1
        assert curve.growth_events[0].event_name == "林黛玉进贾府"

    def test_generate_growth_chart_data(self, tmp_path):
        """测试生成成长曲线图表数据"""
        # 创建 Vault 结构
        vault_dir = tmp_path / "test_vault" / "test_book"
        vault_dir.mkdir(parents=True)
        char_dir = vault_dir / "characters"
        char_dir.mkdir()

        # 创建测试人物卡片
        char_file = char_dir / "林黛玉.md"
        char_file.write_text(
            """---
type: character
gender: 女
tags: [character]
---

# 林黛玉

> 活跃

## 身份
贾府表小姐

## 性格
多愁善感

## 成长轨迹
### 林黛玉进贾府
章节: 第1章
时间: 春天
成长类型: 地位
重要性: 高
描述: 林黛玉初入贾府
状态后: 贾府表小姐

### 宝黛相恋
章节: 第5章
时间: 夏天
成长类型: 情感
重要性: 高
描述: 林黛玉与贾宝玉互生情愫
状态后: 与贾宝玉相恋
""",
            encoding="utf-8"
        )

        # 初始化追踪器
        tracker = CharacterGrowthTracker(
            vault_dir=tmp_path / "test_vault",
            book_title="test_book"
        )

        # 生成图表数据
        chart_data = tracker.generate_growth_chart_data("林黛玉")

        assert "character_name" in chart_data
        assert "timeline" in chart_data
        assert "growth_phases" in chart_data
        assert chart_data["total_events"] == 2


class TestHelperFunctions:
    """测试辅助函数"""

    def test_extract_growth_from_chapter_analysis(self):
        """测试从章节分析中提取成长事件"""
        chapter_content = {
            "characters": [
                {
                    "name": "张三",
                    "current_state": "功力大增",
                    "relationships": [{"target": "李四", "nature": "师徒"}]
                }
            ],
            "events": [
                {
                    "name": "修炼突破",
                    "time": "某天",
                    "participants": ["张三"],
                    "importance": "高",
                    "description": "张三突破瓶颈"
                }
            ],
            "summary": "张三修炼"
        }

        events = extract_growth_from_chapter_analysis(chapter_content, 1)

        assert len(events) > 0


class TestGrowthTypes:
    """测试成长类型定义"""

    def test_growth_types_complete(self):
        """测试成长类型定义完整"""
        expected_types = ["实力", "地位", "情感", "认知", "关系", "性格", "命运"]
        for gtype in expected_types:
            assert gtype in GROWTH_TYPES


# ── 新增测试：核心函数测试 ──

class TestClassifyGrowthType:
    """测试 classify_growth_type 函数"""

    def test_classify_strength(self):
        """测试实力类型分类"""
        event = {"name": "修炼突破", "description": "角色实力大幅提升"}
        assert classify_growth_type(event) == "实力"

    def test_classify_status(self):
        """测试地位类型分类"""
        event = {"name": "加冕为王", "description": "角色登上王位"}
        assert classify_growth_type(event) == "地位"

    def test_classify_emotion(self):
        """测试情感类型分类"""
        event = {"name": "表白心意", "description": "角色向爱人表白"}
        assert classify_growth_type(event) == "情感"

    def test_classify_cognition(self):
        """测试认知类型分类"""
        event = {"name": "领悟真谛", "description": "角色领悟人生道理"}
        assert classify_growth_type(event) == "认知"

    def test_classify_relationship(self):
        """测试关系类型分类"""
        event = {"name": "结盟成功", "description": "与其他势力结盟"}
        assert classify_growth_type(event) == "关系"

    def test_classify_personality(self):
        """测试性格类型分类"""
        event = {"name": "性格转变", "description": "角色性格发生改变"}
        assert classify_growth_type(event) == "性格"

    def test_classify_fate(self):
        """测试命运类型分类"""
        event = {"name": "命运转折", "description": "角色命运发生重大转折"}
        assert classify_growth_type(event) == "命运"

    def test_classify_other(self):
        """测试其他类型分类"""
        event = {"name": "日常琐事", "description": "普通事件"}
        assert classify_growth_type(event) == "其他"

    def test_classify_combined_keywords(self):
        """测试组合关键词分类"""
        # 应该优先匹配认知（在关键词列表中排在前面）
        event = {"name": "觉醒并修炼", "description": "角色觉醒后开始修炼"}
        # 根据关键词优先级，应该匹配认知（觉醒在认知关键词列表中）
        result = classify_growth_type(event)
        assert result in ["认知", "实力"]  # 两个都可能匹配


class TestExtractGrowthEvents:
    """测试 extract_growth_events 函数"""

    def test_extract_from_event_objects(self):
        """测试从Event对象提取成长事件"""
        events = [
            Event(
                name="宝黛初见",
                time="春天",
                participants=["林黛玉", "贾宝玉"],
                description="二人初次见面",
                chapter="第1章",
                importance="高"
            ),
            Event(
                name="修炼突破",
                time="夏天",
                participants=["张三"],
                description="张三突破瓶颈",
                chapter="第2章",
                importance="高"
            )
        ]

        growth_events = extract_growth_events(events, "林黛玉")

        assert len(growth_events) == 1
        assert growth_events[0].event_name == "宝黛初见"
        assert growth_events[0].chapter == "第1章"

    def test_extract_from_dict_events(self):
        """测试从dict格式事件提取成长事件"""
        events = [
            {
                "name": "宝黛初见",
                "time": "春天",
                "participants": ["林黛玉", "贾宝玉"],
                "description": "二人初次见面",
                "chapter": "第1章",
                "importance": "高"
            }
        ]

        growth_events = extract_growth_events(events, "林黛玉")

        assert len(growth_events) == 1
        assert growth_events[0].event_name == "宝黛初见"

    def test_extract_no_match(self):
        """测试无匹配事件"""
        events = [
            Event(
                name="他人事件",
                participants=["其他人"],
                description="与主角无关"
            )
        ]

        growth_events = extract_growth_events(events, "林黛玉")

        assert len(growth_events) == 0

    def test_extract_sort_by_chapter(self):
        """测试按章节排序"""
        events = [
            Event(name="事件2", participants=["林黛玉"], chapter="第2章"),
            Event(name="事件1", participants=["林黛玉"], chapter="第1章"),
            Event(name="事件3", participants=["林黛玉"], chapter="第3章"),
        ]

        growth_events = extract_growth_events(events, "林黛玉")

        assert len(growth_events) == 3
        assert growth_events[0].chapter == "第1章"
        assert growth_events[1].chapter == "第2章"
        assert growth_events[2].chapter == "第3章"


class Test划分成长阶段:
    """测试 划分成长阶段 函数"""

    def test划分空列表(self):
        """测试空列表"""
        phases = 划分成长阶段([])
        assert phases == []

    def test划分单事件(self):
        """测试单个事件"""
        events = [
            GrowthEvent(
                event_name="修炼突破",
                chapter="第1章",
                growth_type="实力",
                significance="高"
            )
        ]

        phases = 划分成长阶段(events)

        assert len(phases) == 1
        assert phases[0]["type"] == "实力"
        assert phases[0]["events_count"] == 1
        assert phases[0]["high_significance_count"] == 1

    def test划分多类型事件(self):
        """测试多种类型事件"""
        events = [
            GrowthEvent(event_name="修炼突破", chapter="第1章", growth_type="实力", significance="高"),
            GrowthEvent(event_name="表白心意", chapter="第2章", growth_type="情感", significance="高"),
            GrowthEvent(event_name="结盟成功", chapter="第3章", growth_type="关系", significance="中"),
            GrowthEvent(event_name="第二次修炼", chapter="第4章", growth_type="实力", significance="中"),
        ]

        phases = 划分成长阶段(events)

        assert len(phases) == 3  # 实力、情感、关系

        # 检查实力阶段
        strength_phase = next(p for p in phases if p["type"] == "实力")
        assert strength_phase["events_count"] == 2
        assert strength_phase["start_chapter"] == "第1章"
        assert strength_phase["end_chapter"] == "第4章"

    def test划分按章节排序(self):
        """测试按章节排序"""
        events = [
            GrowthEvent(event_name="事件3", chapter="第3章", growth_type="实力"),
            GrowthEvent(event_name="事件1", chapter="第1章", growth_type="实力"),
            GrowthEvent(event_name="事件2", chapter="第2章", growth_type="实力"),
        ]

        phases = 划分成长阶段(events)

        assert len(phases) == 1
        assert phases[0]["start_chapter"] == "第1章"
        assert phases[0]["end_chapter"] == "第3章"


class TestGenerateGrowthCurve:
    """测试 generate_growth_curve 函数"""

    def test生成空曲线(self):
        """测试生成空曲线"""
        curve = generate_growth_curve("林黛玉", [])

        assert curve.character_name == "林黛玉"
        assert len(curve.growth_events) == 0
        assert curve.overall_trend == "无数据"
        assert "暂无成长记录" in curve.summary

    def test生成有事件曲线(self):
        """测试生成有事件的曲线"""
        events = [
            GrowthEvent(event_name="进贾府", chapter="第1章", growth_type="地位", significance="高"),
            GrowthEvent(event_name="宝黛相恋", chapter="第5章", growth_type="情感", significance="高"),
            GrowthEvent(event_name="诗社夺魁", chapter="第8章", growth_type="实力", significance="中"),
        ]

        curve = generate_growth_curve("林黛玉", events)

        assert curve.character_name == "林黛玉"
        assert len(curve.growth_events) == 3
        assert len(curve.growth_phases) == 3  # 地位、情感、实力
        assert "经历3个成长事件" in curve.summary

    def test自定义阶段(self):
        """测试使用自定义阶段"""
        events = [
            GrowthEvent(event_name="事件1", chapter="第1章", growth_type="实力"),
        ]
        custom_phases = [
            {
                "start_chapter": "第1章",
                "end_chapter": "第1章",
                "type": "自定义阶段",
                "events_count": 1,
                "high_significance_count": 0,
                "description": "自定义阶段描述"
            }
        ]

        curve = generate_growth_curve("林黛玉", events, growth_phases=custom_phases)

        assert len(curve.growth_phases) == 1
        assert curve.growth_phases[0]["type"] == "自定义阶段"


class TestRenderGrowthMermaid:
    """测试 render_growth_mermaid 函数"""

    def test渲染空曲线(self):
        """测试渲染空曲线"""
        curve = CharacterGrowthCurve(
            character_name="林黛玉",
            growth_events=[],
            summary="无成长记录",
            growth_phases=[],
            overall_trend="无数据"
        )

        mermaid = render_growth_mermaid(curve)

        assert "```mermaid" in mermaid
        assert "timeline" in mermaid
        assert "林黛玉成长曲线" in mermaid

    def test渲染有事件曲线(self):
        """测试渲染有事件的曲线"""
        events = [
            GrowthEvent(
                event_name="进贾府",
                chapter="第1章",
                growth_type="地位",
                significance="高",
                description="林黛玉进入贾府"
            ),
            GrowthEvent(
                event_name="宝黛相恋",
                chapter="第5章",
                growth_type="情感",
                significance="高",
                description="与贾宝玉互生情愫"
            ),
        ]
        phases = [
            {
                "start_chapter": "第1章",
                "end_chapter": "第5章",
                "type": "地位",
                "events_count": 1,
                "high_significance_count": 1,
                "description": "地位成长阶段"
            },
            {
                "start_chapter": "第5章",
                "end_chapter": "第5章",
                "type": "情感",
                "events_count": 1,
                "high_significance_count": 1,
                "description": "情感成长阶段"
            },
        ]

        curve = CharacterGrowthCurve(
            character_name="林黛玉",
            growth_events=events,
            summary="成长摘要",
            growth_phases=phases,
            overall_trend="整体趋势"
        )

        mermaid = render_growth_mermaid(curve)

        assert "```mermaid" in mermaid
        assert "timeline" in mermaid
        assert "第1章" in mermaid
        assert "第5章" in mermaid
        assert "[地位]" in mermaid  # 地位标签
        assert "[情感]" in mermaid  # 情感标签
        assert "★" in mermaid  # 高重要性标记

    def test渲染自定义标题(self):
        """测试渲染自定义标题"""
        curve = CharacterGrowthCurve(
            character_name="林黛玉",
            growth_events=[],
            summary="无成长记录",
            growth_phases=[],
            overall_trend="无数据"
        )

        mermaid = render_growth_mermaid(curve, title="自定义标题")

        assert "自定义标题" in mermaid
        assert "林黛玉成长曲线" not in mermaid


class TestAnalyzeCharacterGrowth:
    """测试 analyze_character_growth 函数"""

    def test分析不存在角色(self):
        """测试分析不存在的角色"""
        knowledge_base = {
            "characters": [],
            "events": []
        }

        with pytest.raises(ValueError, match="不存在"):
            analyze_character_growth("不存在的角色", knowledge_base, use_ai=False)

    def test分析无事件角色(self):
        """测试分析无事件的角色"""
        knowledge_base = {
            "characters": [{"name": "林黛玉"}],
            "events": []
        }

        curve = analyze_character_growth("林黛玉", knowledge_base, use_ai=False)

        assert curve.character_name == "林黛玉"
        assert len(curve.growth_events) == 0

    def test分析有事件角色(self):
        """测试分析有事件的角色"""
        knowledge_base = {
            "characters": [{"name": "林黛玉"}],
            "events": [
                Event(
                    name="宝黛初见",
                    participants=["林黛玉", "贾宝玉"],
                    chapter="第1章",
                    importance="高"
                ),
                Event(
                    name="诗社夺魁",
                    participants=["林黛玉"],
                    chapter="第5章",
                    importance="中"
                ),
            ]
        }

        curve = analyze_character_growth("林黛玉", knowledge_base, use_ai=False)

        assert curve.character_name == "林黛玉"
        assert len(curve.growth_events) == 2
        assert len(curve.growth_phases) > 0

    @patch('src.api_client.call_api')
    def testAI分析(self, mock_ai):
        """测试AI分析功能"""
        # 模拟AI响应
        mock_ai.return_value = json.dumps({
            "events_analysis": [
                {
                    "event_name": "宝黛初见",
                    "suggested_type": "情感",
                    "significance": "高",
                    "impact": "重要转折点"
                }
            ],
            "growth_trend": "情感成长为主",
            "key_turning_points": ["宝黛初见"]
        })

        knowledge_base = {
            "characters": [{"name": "林黛玉"}],
            "events": [
                Event(
                    name="宝黛初见",
                    participants=["林黛玉"],
                    chapter="第1章",
                    importance="高"
                ),
            ]
        }

        curve = analyze_character_growth("林黛玉", knowledge_base, use_ai=True)

        assert curve.character_name == "林黛玉"
        assert len(curve.growth_events) == 1
        # AI应该将类型改为情感
        assert curve.growth_events[0].growth_type == "情感"


class TestBatchFunctions:
    """测试批量处理函数"""

    def test_batch_extract_growth_events(self, tmp_path):
        """测试批量提取成长事件"""
        vault_dir = tmp_path / "test_vault"
        vault_dir.mkdir()

        chapter_analyses = [
            {
                "characters": [
                    {
                        "name": "张三",
                        "current_state": "功力大增",
                        "relationships": []
                    }
                ],
                "events": [
                    {
                        "name": "修炼突破",
                        "participants": ["张三"],
                        "importance": "高",
                        "description": "张三突破瓶颈"
                    }
                ]
            }
        ]

        character_events = batch_extract_growth_events(vault_dir, "测试作品", chapter_analyses)

        assert "张三" in character_events
        assert len(character_events["张三"]) > 0

    def test_save_all_growth_events(self, tmp_path):
        """测试保存所有成长事件"""
        # 创建 Vault 结构
        vault_dir = tmp_path / "test_vault" / "test_book"
        vault_dir.mkdir(parents=True)
        char_dir = vault_dir / "characters"
        char_dir.mkdir()

        # 创建测试人物卡片
        char_file = char_dir / "张三.md"
        char_file.write_text(
            """---
type: character
gender: 男
tags: [character]
---

# 张三

> 活跃

## 身份
战士

## 性格
勇敢
""",
            encoding="utf-8"
        )

        character_events = {
            "张三": [
                GrowthEvent(
                    event_name="修炼突破",
                    chapter="第1章",
                    growth_type="实力",
                    significance="高"
                )
            ]
        }

        save_all_growth_events(tmp_path / "test_vault", "test_book", character_events)

        # 验证文件已更新
        char_content = char_file.read_text(encoding="utf-8")
        assert "成长轨迹" in char_content or "growth_events" in char_content


class TestEdgeCases:
    """测试边界情况"""

    def test_classify_growth_type_empty(self):
        """测试空事件分类"""
        event = {"name": "", "description": ""}
        result = classify_growth_type(event)
        assert result == "其他"

    def test划分成长阶段无章节(self):
        """测试无章节事件的阶段划分"""
        events = [
            GrowthEvent(event_name="事件1", chapter="", growth_type="实力"),
            GrowthEvent(event_name="事件2", chapter="", growth_type="实力"),
        ]

        phases = 划分成长阶段(events)

        assert len(phases) == 1
        assert phases[0]["start_chapter"] == ""
        assert phases[0]["end_chapter"] == ""

    def test_extract_growth_events_mixed_format(self):
        """测试混合格式事件提取"""
        events = [
            Event(name="事件1", participants=["林黛玉"], chapter="第1章"),
            {
                "name": "事件2",
                "participants": ["林黛玉"],
                "chapter": "第2章"
            }
        ]

        growth_events = extract_growth_events(events, "林黛玉")

        assert len(growth_events) == 2

    def test_growth_curve_serialization(self):
        """测试成长曲线序列化"""
        events = [
            GrowthEvent(event_name="事件1", chapter="第1章", growth_type="实力")
        ]
        curve = generate_growth_curve("林黛玉", events)

        # 测试可以转换为字典
        curve_dict = {
            "character_name": curve.character_name,
            "growth_events": [
                {
                    "event_name": e.event_name,
                    "chapter": e.chapter,
                    "growth_type": e.growth_type
                }
                for e in curve.growth_events
            ],
            "summary": curve.summary,
            "growth_phases": curve.growth_phases,
            "overall_trend": curve.overall_trend,
        }

        assert curve_dict["character_name"] == "林黛玉"
        assert len(curve_dict["growth_events"]) == 1
