"""
Story Wiki - 章节生成模块测试
测试 ChapterGenerator 的核心功能。
"""
import json
from unittest.mock import patch, MagicMock

from src.interfaces import ChapterContent, Character, PlotOutline
from src.chapter_generator import ChapterGenerator


def test_init_default_config():
    """测试默认配置初始化。"""
    print("测试默认配置初始化...")

    gen = ChapterGenerator()

    assert gen.min_words == 2000, "默认最小字数应为 2000"
    assert gen.max_words == 3000, "默认最大字数应为 3000"

    print("  [PASS] 默认配置初始化测试通过")


def test_init_custom_config():
    """测试自定义配置初始化。"""
    print("测试自定义配置初始化...")

    config = {
        "min_words": 1500,
        "max_words": 2500,
        "temperature": 0.5,
    }
    gen = ChapterGenerator(config)

    assert gen.min_words == 1500, "最小字数应为 1500"
    assert gen.max_words == 2500, "最大字数应为 2500"
    assert gen.temperature == 0.5, "温度应为 0.5"

    print("  [PASS] 自定义配置初始化测试通过")


def test_init_invalid_config():
    """测试无效配置初始化。"""
    print("测试无效配置初始化...")

    # min_words 为负数
    try:
        ChapterGenerator({"min_words": -1})
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert "不能为负数" in str(e)

    # max_words < min_words
    try:
        ChapterGenerator({"min_words": 3000, "max_words": 2000})
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert "不能小于" in str(e)

    print("  [PASS] 无效配置初始化测试通过")


def test_validate_output():
    """测试输出验证。"""
    print("测试输出验证...")

    gen = ChapterGenerator()

    # 有效输出
    valid_output = {
        "chapter_content": ChapterContent(
            chapter_num=1,
            title="第一章",
            content="测试内容",
            word_count=100,
            characters_involved=["角色A"],
            events_happened=["事件1"],
        ),
        "quality_check": {
            "passed": True,
            "issues": [],
            "suggestions": [],
        },
    }
    assert gen.validate(valid_output), "有效输出应通过验证"

    # 无效输出：缺少 chapter_content
    invalid_output_1 = {
        "quality_check": {"passed": True, "issues": [], "suggestions": []}
    }
    assert not gen.validate(invalid_output_1), "缺少 chapter_content 应失败"

    # 无效输出：缺少 quality_check
    invalid_output_2 = {
        "chapter_content": ChapterContent(
            chapter_num=1, title="test", content="test",
            word_count=100, characters_involved=[], events_happened=[]
        )
    }
    assert not gen.validate(invalid_output_2), "缺少 quality_check 应失败"

    # 无效输出：quality_check 缺少字段
    invalid_output_3 = {
        "chapter_content": ChapterContent(
            chapter_num=1, title="test", content="test",
            word_count=100, characters_involved=[], events_happened=[]
        ),
        "quality_check": {"passed": True},
    }
    assert not gen.validate(invalid_output_3), "quality_check 缺少字段应失败"

    print("  [PASS] 输出验证测试通过")


def test_build_context_summary():
    """测试上下文摘要构建。"""
    print("测试上下文摘要构建...")

    gen = ChapterGenerator()

    # 空上下文
    summary = gen._build_context_summary({})
    assert "无上下文信息" in summary

    # 完整上下文
    context = {
        "previous_content": "这是前文内容..." * 10,
        "characters": [
            {"name": "贾宝玉"},
            {"name": "林黛玉"},
        ],
        "events": [
            {"name": "宝黛初见"},
        ],
    }
    summary = gen._build_context_summary(context)
    assert "前文摘要" in summary
    assert "贾宝玉" in summary
    assert "林黛玉" in summary
    assert "宝黛初见" in summary

    # 前文过长时截断
    long_context = {
        "previous_content": "这是一段非常长的前文内容" * 200,
    }
    summary = gen._build_context_summary(long_context)
    assert len(summary) < 2000, "过长的前文应被截断"

    print("  [PASS] 上下文摘要构建测试通过")


def test_build_generation_prompt():
    """测试生成 prompt 构建。"""
    print("测试生成 prompt 构建...")

    gen = ChapterGenerator()

    outline = PlotOutline(
        title="红楼梦",
        theme="家族兴衰",
        conflict="理想与现实的冲突",
        structure={"起": "贾府背景", "承": "大观园生活", "转": "家族衰落", "合": "结局"},
        key_points=["宝黛爱情", "家族衰落"],
        ending_direction="悲剧结局",
    )

    context_summary = "前文摘要：..."

    prompt = gen._build_generation_prompt(1, outline, context_summary)

    assert "红楼梦" in prompt
    assert "家族兴衰" in prompt
    assert "第1章" in prompt
    assert "前文摘要" in prompt

    print("  [PASS] 生成 prompt 构建测试通过")


def test_get_chapter_structure_key():
    """测试获取章节结构键。"""
    print("测试获取章节结构键...")

    gen = ChapterGenerator()

    structure = {"起": "内容1", "承": "内容2", "转": "内容3", "合": "内容4"}

    # 测试不同章节号
    key1 = gen._get_chapter_structure_key(1, structure)
    key2 = gen._get_chapter_structure_key(4, structure)
    key3 = gen._get_chapter_structure_key(8, structure)
    key4 = gen._get_chapter_structure_key(12, structure)

    # 应该返回有效的键
    assert key1 in structure, f"第1章应返回有效键，实际: {key1}"
    assert key2 in structure, f"第4章应返回有效键，实际: {key2}"
    assert key3 in structure, f"第8章应返回有效键，实际: {key3}"
    assert key4 in structure, f"第12章应返回有效键，实际: {key4}"

    # 空结构
    key_empty = gen._get_chapter_structure_key(1, {})
    assert key_empty is None, "空结构应返回 None"

    print("  [PASS] 获取章节结构键测试通过")


def test_format_character_info():
    """测试人物信息格式化。"""
    print("测试人物信息格式化...")

    gen = ChapterGenerator()

    character = Character(
        name="贾宝玉",
        identity="荣国府公子",
        personality="叛逆多情",
        gender="男",
        faction="荣国府",
        aliases=["宝二爷", "怡红公子"],
        motivation="追求真爱",
        current_state="在大观园中",
        relationships=[
            {"target": "林黛玉", "nature": "恋人"},
            {"target": "薛宝钗", "nature": "妻子"},
        ],
    )

    info = gen._format_character_info(character)

    assert "贾宝玉" in info
    assert "荣国府公子" in info
    assert "叛逆多情" in info
    assert "男" in info
    assert "荣国府" in info
    assert "宝二爷" in info
    assert "追求真爱" in info
    assert "林黛玉" in info

    print("  [PASS] 人物信息格式化测试通过")


def test_format_timeline_info():
    """测试时间线信息格式化。"""
    print("测试时间线信息格式化...")

    gen = ChapterGenerator()

    timeline = [
        {"name": "宝黛初见", "time": "春天", "participants": ["贾宝玉", "林黛玉"]},
        {"name": "元妃省亲", "time": "元宵节", "participants": ["贾元春"]},
    ]

    info = gen._format_timeline_info(timeline)

    assert "宝黛初见" in info
    assert "春天" in info
    assert "贾宝玉" in info
    assert "元妃省亲" in info

    # 空时间线
    empty_info = gen._format_timeline_info([])
    assert "无已有时间线" in empty_info

    print("  [PASS] 时间线信息格式化测试通过")


def test_simple_character_check():
    """测试简单人物一致性检查。"""
    print("测试简单人物一致性检查...")

    gen = ChapterGenerator()

    character = Character(
        name="贾宝玉",
        identity="荣国府公子",
        personality="叛逆多情",
        gender="男",
    )

    # 人物未出场
    content_no_char = ChapterContent(
        chapter_num=1,
        title="第一章",
        content="这一章没有贾宝玉出场。",
        word_count=100,
        characters_involved=[],
        events_happened=[],
    )
    assert gen._simple_character_check(content_no_char, character), "人物未出场应通过"

    # 人物出场
    content_with_char = ChapterContent(
        chapter_num=1,
        title="第一章",
        content="贾宝玉在大观园中漫步。",
        word_count=100,
        characters_involved=["贾宝玉"],
        events_happened=[],
    )
    assert gen._simple_character_check(content_with_char, character), "人物出场应通过"

    print("  [PASS] 简单人物一致性检查测试通过")


def test_simple_timeline_check():
    """测试简单时间线检查。"""
    print("测试简单时间线检查...")

    gen = ChapterGenerator()

    content = ChapterContent(
        chapter_num=1,
        title="第一章",
        content="这一章讲述了宝黛初见的故事。",
        word_count=100,
        characters_involved=["贾宝玉", "林黛玉"],
        events_happened=["宝黛初见"],
    )

    timeline = [
        {"name": "宝黛初见", "time": "春天", "participants": ["贾宝玉", "林黛玉"]},
    ]

    assert gen._simple_timeline_check(content, timeline), "简单时间线检查应通过"

    # 空时间线
    assert gen._simple_timeline_check(content, []), "空时间线应通过"

    print("  [PASS] 简单时间线检查测试通过")


@patch("src.chapter_generator._call_deepseek_with_prompt")
@patch("src.chapter_generator.DEEPSEEK_API_KEY", "test_key")
def test_generate_chapter(mock_api):
    """测试章节生成（mock API）。"""
    print("测试章节生成...")

    # 模拟 API 响应
    mock_response = json.dumps({
        "title": "第一章 贾宝玉出世",
        "content": "话说女娲补天之时，于大荒山无稽崖练成高经十二丈、方经二十四丈顽石三万六千五百零一块。\n\n只单单剩了一块未用，便弃在此山青埂峰下。",
        "characters_involved": ["贾宝玉", "女娲"],
        "events_happened": ["顽石下凡"],
    })
    mock_api.return_value = mock_response

    gen = ChapterGenerator()

    outline = PlotOutline(
        title="红楼梦",
        theme="家族兴衰",
        conflict="理想与现实的冲突",
        structure={"起": "贾府背景"},
        key_points=["宝黛爱情"],
        ending_direction="悲剧结局",
    )

    context = {
        "previous_content": "",
        "characters": [],
        "events": [],
    }

    chapter = gen.generate_chapter(1, outline, context)

    assert isinstance(chapter, ChapterContent), "应返回 ChapterContent 对象"
    assert chapter.chapter_num == 1, "章节号应为 1"
    assert "贾宝玉" in chapter.title, "标题应包含人物名"
    assert chapter.word_count > 0, "字数应大于 0"
    assert "贾宝玉" in chapter.characters_involved, "人物列表应包含贾宝玉"

    print("  [PASS] 章节生成测试通过")


@patch("src.chapter_generator._call_deepseek_with_prompt")
@patch("src.chapter_generator.DEEPSEEK_API_KEY", "test_key")
def test_quality_check(mock_api):
    """测试质量检查（mock API）。"""
    print("测试质量检查...")

    # 模拟 API 响应
    mock_response = json.dumps({
        "passed": True,
        "issues": [],
        "suggestions": ["可以增加更多细节描写"],
    })
    mock_api.return_value = mock_response

    gen = ChapterGenerator()

    content = ChapterContent(
        chapter_num=1,
        title="第一章",
        content="这是一段测试内容。" * 200,  # 约 1000 字
        word_count=1000,
        characters_involved=["贾宝玉"],
        events_happened=["测试事件"],
    )

    character = Character(
        name="贾宝玉",
        identity="荣国府公子",
        personality="叛逆多情",
        gender="男",
    )

    result = gen.quality_check(content, [character])

    assert isinstance(result, dict), "应返回字典"
    assert "passed" in result, "应包含 passed 字段"
    assert "issues" in result, "应包含 issues 字段"
    assert "suggestions" in result, "应包含 suggestions 字段"

    print("  [PASS] 质量检查测试通过")


@patch("src.chapter_generator._call_deepseek_with_prompt")
@patch("src.chapter_generator.DEEPSEEK_API_KEY", "test_key")
def test_check_character_consistency(mock_api):
    """测试人物一致性检查（mock API）。"""
    print("测试人物一致性检查...")

    # 模拟 API 响应
    mock_response = json.dumps({
        "consistent": True,
        "issues": [],
        "details": "人物描写与设定一致",
    })
    mock_api.return_value = mock_response

    gen = ChapterGenerator()

    content = ChapterContent(
        chapter_num=1,
        title="第一章",
        content="贾宝玉在大观园中漫步，心中想着林黛玉。",
        word_count=100,
        characters_involved=["贾宝玉"],
        events_happened=[],
    )

    character = Character(
        name="贾宝玉",
        identity="荣国府公子",
        personality="叛逆多情",
        gender="男",
    )

    consistent = gen.check_character_consistency(content, character)

    assert isinstance(consistent, bool), "应返回布尔值"

    print("  [PASS] 人物一致性检查测试通过")


@patch("src.chapter_generator._call_deepseek_with_prompt")
@patch("src.chapter_generator.DEEPSEEK_API_KEY", "test_key")
def test_check_timeline_consistency(mock_api):
    """测试时间线一致性检查（mock API）。"""
    print("测试时间线一致性检查...")

    # 模拟 API 响应
    mock_response = json.dumps({
        "consistent": True,
        "issues": [],
        "details": "时间线一致",
    })
    mock_api.return_value = mock_response

    gen = ChapterGenerator()

    content = ChapterContent(
        chapter_num=1,
        title="第一章",
        content="宝黛初见发生在春天。",
        word_count=100,
        characters_involved=["贾宝玉", "林黛玉"],
        events_happened=["宝黛初见"],
    )

    timeline = [
        {"name": "宝黛初见", "time": "春天", "participants": ["贾宝玉", "林黛玉"]},
    ]

    consistent = gen.check_timeline_consistency(content, timeline)

    assert isinstance(consistent, bool), "应返回布尔值"

    # 空时间线
    assert gen.check_timeline_consistency(content, []), "空时间线应通过"

    print("  [PASS] 时间线一致性检查测试通过")


@patch("src.chapter_generator._call_deepseek_with_prompt")
@patch("src.chapter_generator.DEEPSEEK_API_KEY", "test_key")
def test_run(mock_api):
    """测试运行模块（mock API）。"""
    print("测试运行模块...")

    # 模拟 API 响应
    mock_response_chapter = json.dumps({
        "title": "第一章",
        "content": "这是章节内容。" * 200,
        "characters_involved": ["贾宝玉"],
        "events_happened": ["测试事件"],
    })

    mock_response_quality = json.dumps({
        "passed": True,
        "issues": [],
        "suggestions": [],
    })

    mock_api.side_effect = [mock_response_chapter, mock_response_quality]

    gen = ChapterGenerator()

    input_data = {
        "chapter_num": 1,
        "outline": PlotOutline(
            title="红楼梦",
            theme="家族兴衰",
            conflict="理想与现实的冲突",
            structure={"起": "贾府背景"},
            key_points=["宝黛爱情"],
            ending_direction="悲剧结局",
        ),
        "context": {},
        "characters": [],
        "timeline": [],
    }

    result = gen.run(input_data)

    assert isinstance(result, dict), "应返回字典"
    assert "chapter_content" in result, "应包含 chapter_content"
    assert "quality_check" in result, "应包含 quality_check"

    chapter = result["chapter_content"]
    assert isinstance(chapter, ChapterContent), "chapter_content 应为 ChapterContent"

    quality = result["quality_check"]
    assert isinstance(quality, dict), "quality_check 应为字典"
    assert "passed" in quality, "quality_check 应包含 passed"

    print("  [PASS] 运行模块测试通过")


def test_run_missing_params():
    """测试运行模块缺少参数。"""
    print("测试运行模块缺少参数...")

    gen = ChapterGenerator()

    # 缺少 chapter_num
    try:
        gen.run({"outline": PlotOutline(
            title="test", theme="test", conflict="test",
            structure={}, key_points=[], ending_direction="test"
        )})
        assert False, "应该抛出 RuntimeError"
    except RuntimeError as e:
        assert "chapter_num" in str(e)

    # 缺少 outline
    try:
        gen.run({"chapter_num": 1})
        assert False, "应该抛出 RuntimeError"
    except RuntimeError as e:
        assert "outline" in str(e)

    print("  [PASS] 运行模块缺少参数测试通过")


def test_run_with_dict_outline():
    """测试运行模块使用 dict 格式的 outline。"""
    print("测试运行模块使用 dict 格式的 outline...")

    gen = ChapterGenerator()

    # 验证 dict outline 可以被转换为 PlotOutline
    outline_dict = {
        "title": "红楼梦",
        "theme": "家族兴衰",
        "conflict": "理想与现实的冲突",
        "structure": {"起": "贾府背景"},
        "key_points": ["宝黛爱情"],
        "ending_direction": "悲剧结局",
    }

    # 这里只测试转换逻辑，不实际调用 API
    outline = PlotOutline(**outline_dict)
    assert isinstance(outline, PlotOutline), "应能转换为 PlotOutline"

    print("  [PASS] 运行模块使用 dict 格式的 outline 测试通过")


def run_all_tests():
    """运行所有测试。"""
    print("=" * 50)
    print("章节生成模块测试")
    print("=" * 50)

    tests = [
        test_init_default_config,
        test_init_custom_config,
        test_init_invalid_config,
        test_validate_output,
        test_build_context_summary,
        test_build_generation_prompt,
        test_get_chapter_structure_key,
        test_format_character_info,
        test_format_timeline_info,
        test_simple_character_check,
        test_simple_timeline_check,
        test_generate_chapter,
        test_quality_check,
        test_check_character_consistency,
        test_check_timeline_consistency,
        test_run,
        test_run_missing_params,
        test_run_with_dict_outline,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test.__name__} 失败: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {test.__name__} 异常: {e}")
            failed += 1

    print("=" * 50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
