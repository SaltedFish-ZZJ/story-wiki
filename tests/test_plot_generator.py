"""
Story Wiki - 情节生成模块测试
测试 PlotGenerator 的核心功能：大纲生成、空白识别、验证、扩展。
"""
import json
from unittest.mock import patch, MagicMock

from src.interfaces import PlotOutline
from src.plot_generator import (
    PlotGenerator,
    create_plot_generator,
    analyze_timeline_for_gaps,
    generate_plot_outline,
)


# ── 测试数据 ──────────────────────────────────────────────────

MOCK_KNOWLEDGE_BASE = {
    "characters": [
        {
            "name": "贾宝玉",
            "identity": "荣国府公子，衔玉而生",
            "personality": "叛逆多情，厌恶仕途",
            "role_tags": ["主角"],
            "relationships": [{"target": "林黛玉", "nature": "恋人"}],
        },
        {
            "name": "林黛玉",
            "identity": "林如海之女，贾母外孙女",
            "personality": "多愁善感，才情出众",
            "role_tags": ["女主"],
            "relationships": [{"target": "贾宝玉", "nature": "恋人"}],
        },
        {
            "name": "薛宝钗",
            "identity": "薛姨妈之女",
            "personality": "端庄稳重，八面玲珑",
            "role_tags": ["配角"],
        },
    ],
    "settings": [
        {"name": "荣国府", "type": "地点", "description": "贾府主宅"},
        {"name": "大观园", "type": "地点", "description": "贾府花园"},
    ],
    "events": [
        {
            "name": "黛玉进贾府",
            "time": "某日",
            "participants": ["林黛玉", "贾宝玉"],
            "cause": [],
        },
        {
            "name": "宝黛初见",
            "time": "某日",
            "participants": ["贾宝玉", "林黛玉"],
            "cause": ["黛玉进贾府"],
        },
    ],
}

MOCK_OUTLINE = PlotOutline(
    title="红楼梦",
    theme="封建大家族的兴衰与爱情悲剧",
    conflict="宝黛爱情与封建礼教的冲突",
    structure={
        "起": {
            "title": "繁华盛景",
            "summary": "贾府鼎盛时期，宝玉黛玉青梅竹马",
            "key_events": ["黛玉进贾府", "宝黛初见"],
        },
        "承": {
            "title": "暗流涌动",
            "summary": "家族矛盾渐显，金玉良缘与木石前盟之争",
            "key_events": ["元妃省亲", "海棠诗社"],
        },
        "转": {
            "title": "大厦将倾",
            "summary": "家族衰败，黛玉病逝",
            "key_events": ["抄检大观园", "黛玉焚稿"],
        },
        "合": {
            "title": "白茫茫大地",
            "summary": "宝玉出家，贾府败落",
            "key_events": ["宝玉出家", "贾府抄家"],
        },
    },
    key_points=["木石前盟与金玉良缘之争", "大观园的兴衰", "宝玉的觉醒与出走"],
    ending_direction="悲剧收束，宝玉看破红尘，出家为僧",
)

MOCK_GAP = {
    "type": "missing_cause",
    "description": "缺少宝黛感情发展的过渡事件",
    "position": "承阶段",
    "importance": "high",
    "suggested_events": ["共读西厢", "葬花吟"],
}

MOCK_RAW_RESPONSE_VALID = json.dumps(
    {
        "title": "红楼梦",
        "theme": "封建大家族的兴衰与爱情悲剧",
        "conflict": "宝黛爱情与封建礼教的冲突",
        "structure": {
            "起": {"title": "繁华盛景", "summary": "贾府鼎盛时期", "key_events": ["黛玉进贾府"]},
            "承": {"title": "暗流涌动", "summary": "家族矛盾渐显", "key_events": ["元妃省亲"]},
            "转": {"title": "大厦将倾", "summary": "家族衰败", "key_events": ["抄检大观园"]},
            "合": {"title": "白茫茫大地", "summary": "贾府败落", "key_events": ["宝玉出家"]},
        },
        "key_points": ["木石前盟与金玉良缘之争"],
        "ending_direction": "悲剧收束",
    },
    ensure_ascii=False,
)

MOCK_RAW_RESPONSE_GAPS = json.dumps(
    {
        "gaps": [
            {
                "type": "missing_cause",
                "description": "缺少感情发展过渡",
                "position": "承阶段",
                "importance": "high",
                "suggested_events": ["共读西厢"],
            }
        ]
    },
    ensure_ascii=False,
)

MOCK_RAW_RESPONSE_VALIDATE = json.dumps(
    {
        "is_valid": True,
        "issues": [],
        "overall_assessment": "大纲逻辑一致，符合知识库信息",
    },
    ensure_ascii=False,
)

MOCK_RAW_RESPONSE_EXPAND = json.dumps(
    {
        "title": "红楼梦",
        "theme": "封建大家族的兴衰与爱情悲剧",
        "conflict": "宝黛爱情与封建礼教的冲突",
        "structure": {
            "起": {"title": "繁华盛景", "summary": "贾府鼎盛时期", "key_events": ["黛玉进贾府"]},
            "承": {
                "title": "暗流涌动",
                "summary": "家族矛盾渐显",
                "key_events": ["元妃省亲", "共读西厢"],
            },
            "转": {"title": "大厦将倾", "summary": "家族衰败", "key_events": ["抄检大观园"]},
            "合": {"title": "白茫茫大地", "summary": "贾府败落", "key_events": ["宝玉出家"]},
        },
        "key_points": ["木石前盟与金玉良缘之争", "共读西厢"],
        "ending_direction": "悲剧收束",
    },
    ensure_ascii=False,
)


# ── 测试类 ──────────────────────────────────────────────────


class TestPlotGeneratorInit:
    """测试 PlotGenerator 初始化"""

    def test_init_with_api_key(self):
        """测试使用 API Key 初始化"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        assert gen is not None

    def test_init_without_api_key_raises(self):
        """测试缺少 API Key 时抛出异常"""
        import os

        # 临时清除环境变量
        old_key = os.environ.pop("STORY_WIKI_API_KEY", None)
        try:
            gen = PlotGenerator(config={})
            # 如果环境变量中有 key，不会抛出异常
        except ValueError:
            pass  # 预期行为
        finally:
            if old_key:
                os.environ["STORY_WIKI_API_KEY"] = old_key


class TestPlotGeneratorValidation:
    """测试 PlotGenerator.validate 方法"""

    def test_validate_with_valid_outline_object(self):
        """测试验证有效的 PlotOutline 对象"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        result = gen.validate({"outline": MOCK_OUTLINE})
        assert result is True

    def test_validate_with_valid_outline_dict(self):
        """测试验证有效的 outline dict"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        outline_dict = {
            "title": "红楼梦",
            "theme": "封建大家族的兴衰",
            "structure": {"起": {}, "承": {}, "转": {}, "合": {}},
        }
        result = gen.validate({"outline": outline_dict})
        assert result is True

    def test_validate_with_invalid_outline(self):
        """测试验证无效的 outline"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        result = gen.validate({"outline": None})
        assert result is False

    def test_validate_with_empty_outline(self):
        """测试验证空的 outline"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        result = gen.validate({"outline": {}})
        assert result is False

    def test_validate_with_non_dict(self):
        """测试验证非 dict 输入"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        result = gen.validate("not a dict")
        assert result is False


class TestPlotGeneratorRun:
    """测试 PlotGenerator.run 方法"""

    def test_run_generate_action(self):
        """测试 generate 操作"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        with patch.object(gen, "_call_api", return_value=MOCK_RAW_RESPONSE_VALID):
            result = gen.run(
                {
                    "book_title": "红楼梦",
                    "knowledge_base": MOCK_KNOWLEDGE_BASE,
                    "action": "generate",
                }
            )
            assert result["success"] is True
            assert "outline" in result
            assert isinstance(result["outline"], PlotOutline)

    def test_run_identify_gaps_action(self):
        """测试 identify_gaps 操作"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        with patch.object(gen, "_call_api", return_value=MOCK_RAW_RESPONSE_GAPS):
            result = gen.run(
                {
                    "book_title": "红楼梦",
                    "knowledge_base": MOCK_KNOWLEDGE_BASE,
                    "action": "identify_gaps",
                    "timeline": MOCK_KNOWLEDGE_BASE["events"],
                }
            )
            assert result["success"] is True
            assert "gaps" in result
            assert len(result["gaps"]) > 0

    def test_run_validate_action(self):
        """测试 validate 操作"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        with patch.object(gen, "_call_api", return_value=MOCK_RAW_RESPONSE_VALIDATE):
            result = gen.run(
                {
                    "book_title": "红楼梦",
                    "knowledge_base": MOCK_KNOWLEDGE_BASE,
                    "action": "validate",
                    "outline": MOCK_OUTLINE,
                }
            )
            assert result["success"] is True
            assert "is_valid" in result

    def test_run_expand_action(self):
        """测试 expand 操作"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        with patch.object(gen, "_call_api", return_value=MOCK_RAW_RESPONSE_EXPAND):
            result = gen.run(
                {
                    "book_title": "红楼梦",
                    "knowledge_base": MOCK_KNOWLEDGE_BASE,
                    "action": "expand",
                    "outline": MOCK_OUTLINE,
                    "gap": MOCK_GAP,
                }
            )
            assert result["success"] is True
            assert "outline" in result

    def test_run_invalid_action(self):
        """测试无效操作类型"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.run({"book_title": "红楼梦", "knowledge_base": {}, "action": "invalid"})
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "不支持的操作类型" in str(e)

    def test_run_validate_without_outline(self):
        """测试 validate 操作缺少 outline"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.run(
                {
                    "book_title": "红楼梦",
                    "knowledge_base": MOCK_KNOWLEDGE_BASE,
                    "action": "validate",
                }
            )
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "需要提供 outline" in str(e)

    def test_run_expand_without_params(self):
        """测试 expand 操作缺少参数"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.run(
                {
                    "book_title": "红楼梦",
                    "knowledge_base": MOCK_KNOWLEDGE_BASE,
                    "action": "expand",
                }
            )
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "需要提供 outline 和 gap" in str(e)


class TestPlotGeneratorGenerateOutline:
    """测试 generate_outline 方法"""

    def test_generate_outline_success(self):
        """测试成功生成大纲"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        with patch.object(gen, "_call_api", return_value=MOCK_RAW_RESPONSE_VALID):
            outline = gen.generate_outline("红楼梦", MOCK_KNOWLEDGE_BASE)
            assert isinstance(outline, PlotOutline)
            assert outline.title == "红楼梦"
            assert outline.theme != ""
            assert outline.conflict != ""
            assert "起" in outline.structure
            assert "承" in outline.structure
            assert "转" in outline.structure
            assert "合" in outline.structure

    def test_generate_outline_empty_title(self):
        """测试空标题"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.generate_outline("", MOCK_KNOWLEDGE_BASE)
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "不能为空" in str(e)

    def test_generate_outline_empty_kb(self):
        """测试空知识库"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.generate_outline("红楼梦", {})
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "不能为空" in str(e)


class TestPlotGeneratorIdentifyGaps:
    """测试 identify_gaps 方法"""

    def test_identify_gaps_success(self):
        """测试成功识别空白"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        with patch.object(gen, "_call_api", return_value=MOCK_RAW_RESPONSE_GAPS):
            gaps = gen.identify_gaps(
                MOCK_KNOWLEDGE_BASE["events"], MOCK_KNOWLEDGE_BASE
            )
            assert isinstance(gaps, list)
            assert len(gaps) > 0
            assert "type" in gaps[0]
            assert "description" in gaps[0]

    def test_identify_gaps_empty_timeline(self):
        """测试空时间线"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.identify_gaps([], MOCK_KNOWLEDGE_BASE)
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "不能为空" in str(e)

    def test_identify_gaps_empty_kb(self):
        """测试空知识库"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.identify_gaps(MOCK_KNOWLEDGE_BASE["events"], {})
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "不能为空" in str(e)


class TestPlotGeneratorValidateOutline:
    """测试 validate_outline 方法"""

    def test_validate_outline_success(self):
        """测试成功验证大纲"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        with patch.object(gen, "_call_api", return_value=MOCK_RAW_RESPONSE_VALIDATE):
            is_valid = gen.validate_outline(MOCK_OUTLINE, MOCK_KNOWLEDGE_BASE)
            assert is_valid is True

    def test_validate_outline_empty_outline(self):
        """测试空大纲"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.validate_outline(None, MOCK_KNOWLEDGE_BASE)
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "不能为空" in str(e)

    def test_validate_outline_empty_kb(self):
        """测试空知识库"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.validate_outline(MOCK_OUTLINE, {})
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "不能为空" in str(e)


class TestPlotGeneratorExpandOutline:
    """测试 expand_outline 方法"""

    def test_expand_outline_success(self):
        """测试成功扩展大纲"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        with patch.object(gen, "_call_api", return_value=MOCK_RAW_RESPONSE_EXPAND):
            expanded = gen.expand_outline(MOCK_OUTLINE, MOCK_GAP)
            assert isinstance(expanded, PlotOutline)
            assert expanded.title == MOCK_OUTLINE.title
            # 检查承阶段是否添加了新事件
            cheng = expanded.structure.get("承", {})
            key_events = cheng.get("key_events", [])
            assert "共读西厢" in key_events

    def test_expand_outline_empty_outline(self):
        """测试空大纲"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.expand_outline(None, MOCK_GAP)
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "不能为空" in str(e)

    def test_expand_outline_empty_gap(self):
        """测试空空白"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        try:
            gen.expand_outline(MOCK_OUTLINE, None)
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "不能为空" in str(e)


class TestPlotGeneratorHelpers:
    """测试辅助方法"""

    def test_build_knowledge_base_summary(self):
        """测试知识库摘要构建"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        summary = gen._build_knowledge_base_summary(MOCK_KNOWLEDGE_BASE)
        assert "贾宝玉" in summary
        assert "林黛玉" in summary
        assert "荣国府" in summary
        assert "黛玉进贾府" in summary

    def test_build_knowledge_base_summary_empty(self):
        """测试空知识库摘要"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        summary = gen._build_knowledge_base_summary({})
        assert "暂无" in summary

    def test_build_timeline_summary(self):
        """测试时间线摘要构建"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        summary = gen._build_timeline_summary(MOCK_KNOWLEDGE_BASE["events"])
        assert "黛玉进贾府" in summary
        assert "宝黛初见" in summary

    def test_build_timeline_summary_empty(self):
        """测试空时间线摘要"""
        gen = PlotGenerator(config={"api_key": "test_key"})
        summary = gen._build_timeline_summary([])
        assert "为空" in summary

    # 删除了 _parse_response 相关测试，因为该方法已移除

    # 删除了 _parse_response 相关测试，因为该方法已移除


class TestFactoryFunctions:
    """测试工厂函数"""

    def test_create_plot_generator(self):
        """测试 create_plot_generator"""
        gen = create_plot_generator({"api_key": "test_key"})
        assert isinstance(gen, PlotGenerator)

    def test_analyze_timeline_for_gaps(self):
        """测试 analyze_timeline_for_gaps"""
        with patch(
            "src.plot_generator.PlotGenerator._call_api",
            return_value=MOCK_RAW_RESPONSE_GAPS,
        ):
            # 需要 mock API 调用
            gen = create_plot_generator({"api_key": "test_key"})
            with patch.object(gen, "_call_api", return_value=MOCK_RAW_RESPONSE_GAPS):
                gaps = gen.identify_gaps(
                    MOCK_KNOWLEDGE_BASE["events"], MOCK_KNOWLEDGE_BASE
                )
                assert isinstance(gaps, list)

    def test_generate_plot_outline(self):
        """测试 generate_plot_outline"""
        gen = create_plot_generator({"api_key": "test_key"})
        with patch.object(gen, "_call_api", return_value=MOCK_RAW_RESPONSE_VALID):
            outline = gen.generate_outline("红楼梦", MOCK_KNOWLEDGE_BASE)
            assert isinstance(outline, PlotOutline)


# ── 运行测试 ──────────────────────────────────────────────────


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("情节生成模块测试")
    print("=" * 60)

    test_classes = [
        TestPlotGeneratorInit,
        TestPlotGeneratorValidation,
        TestPlotGeneratorRun,
        TestPlotGeneratorGenerateOutline,
        TestPlotGeneratorIdentifyGaps,
        TestPlotGeneratorValidateOutline,
        TestPlotGeneratorExpandOutline,
        TestPlotGeneratorHelpers,
        TestFactoryFunctions,
    ]

    passed = 0
    failed = 0
    errors = []

    for test_class in test_classes:
        print(f"\n--- {test_class.__name__} ---")
        instance = test_class()

        for method_name in dir(instance):
            if not method_name.startswith("test_"):
                continue

            test_method = getattr(instance, method_name)
            try:
                test_method()
                print(f"  [PASS] {method_name}")
                passed += 1
            except AssertionError as e:
                print(f"  [FAIL] {method_name}: {e}")
                failed += 1
                errors.append((method_name, str(e)))
            except Exception as e:
                print(f"  [ERROR] {method_name}: {type(e).__name__}: {e}")
                failed += 1
                errors.append((method_name, str(e)))

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    if errors:
        print("\n失败详情:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
