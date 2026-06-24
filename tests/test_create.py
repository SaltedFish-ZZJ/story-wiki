"""
Story Wiki - 创作管线集成测试
测试 create_novel、quick_create、resume_create、preview_outline 等函数。
"""
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.interfaces import PlotOutline, ChapterContent, Character
from src.create import (
    create_novel,
    quick_create,
    resume_create,
    preview_outline,
    _load_character_objects,
    _display_outline,
    _error_result,
)


def _make_mock_vault(knowledge_base=None):
    """创建 mock VaultManager。"""
    mock_vault = MagicMock()
    mock_vault.load_all_cards.return_value = knowledge_base or {
        "characters": [
            {"name": "张三", "identity": "主角", "personality": "勇敢", "gender": "男"}
        ],
        "settings": [],
        "events": [],
    }
    mock_vault.load_character.return_value = Character(
        name="张三",
        aliases=[],
        identity="主角",
        personality="勇敢",
        gender="男",
        faction="",
        role_tags=["主角"],
        status="活跃",
        quotes=[],
        motivation="",
        current_state="",
        related_settings=[],
        relationships=[],
    )
    mock_vault.get_timeline.return_value = []
    return mock_vault


def _make_mock_outline():
    """创建 mock PlotOutline。"""
    return PlotOutline(
        title="测试作品",
        theme="测试主题",
        conflict="核心冲突",
        structure={"起": {"title": "开始", "summary": "开端", "key_events": ["事件1"]}},
        key_points=["点1", "点2"],
        ending_direction="大团圆",
    )


def _make_mock_chapter(num=1, word_count=2500):
    """创建 mock ChapterContent。"""
    return ChapterContent(
        chapter_num=num,
        title=f"第{num}章",
        content=f"这是第{num}章的内容。" * 100,
        word_count=word_count,
        characters_involved=["张三"],
        events_happened=["事件1"],
    )


# ── create_novel 测试 ──────────────────────────────────────────

def test_create_novel_empty_knowledge_base():
    """测试空知识库应返回错误。"""
    print("测试空知识库...")
    mock_vault = _make_mock_vault({"characters": [], "settings": [], "events": []})

    with patch("src.create.VaultManager", return_value=mock_vault):
        result = create_novel("测试", num_chapters=1)
        assert result["success"] is False
        assert "知识库为空" in result["error"]

    print("  [PASS] 空知识库测试通过")


def test_create_novel_outline_only():
    """测试只生成大纲模式。"""
    print("测试大纲模式...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.return_value = _make_mock_outline()

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot):
        result = create_novel("测试", num_chapters=5, outline_only=True)
        assert result["success"] is True
        assert result["chapters_generated"] == 0
        assert result["outline"] is not None
        assert result["outline"].title == "测试作品"

    print("  [PASS] 大纲模式测试通过")


def test_create_novel_outline_only_output():
    """测试大纲预览模式。"""
    print("测试大纲预览模式...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.return_value = _make_mock_outline()

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot):
        result = create_novel("测试", outline_only_output=True)
        assert result["success"] is True
        assert result["chapters_generated"] == 0

    print("  [PASS] 大纲预览模式测试通过")


def test_create_novel_vault_load_error():
    """测试知识库加载失败。"""
    print("测试知识库加载失败...")
    mock_vault = MagicMock()
    mock_vault.load_all_cards.side_effect = RuntimeError("加载失败")

    with patch("src.create.VaultManager", return_value=mock_vault):
        result = create_novel("测试", num_chapters=1)
        assert result["success"] is False
        assert "加载知识库失败" in result["error"]

    print("  [PASS] 知识库加载失败测试通过")


def test_create_novel_outline_generation_error():
    """测试大纲生成失败。"""
    print("测试大纲生成失败...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.side_effect = RuntimeError("大纲生成失败")

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot):
        result = create_novel("测试", num_chapters=1)
        assert result["success"] is False
        assert "生成大纲失败" in result["error"]

    print("  [PASS] 大纲生成失败测试通过")


def test_create_novel_full_pipeline():
    """测试完整创作管线。"""
    print("测试完整管线...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.return_value = _make_mock_outline()

    mock_chapter_gen = MagicMock()
    mock_chapter_gen.generate_chapter.return_value = _make_mock_chapter(1, 2500)
    mock_chapter_gen.quality_check.return_value = {"passed": True, "issues": [], "suggestions": []}

    mock_logger = MagicMock()
    mock_logger.merge_novel.return_value = "# 测试作品\n\n第1章内容"

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot), \
         patch("src.create.ChapterGenerator", return_value=mock_chapter_gen), \
         patch("src.create.NovelLogger", return_value=mock_logger):
        result = create_novel("测试", num_chapters=1, incremental=False)
        assert result["success"] is True
        assert result["chapters_generated"] == 1
        assert result["total_words"] == 2500
        mock_logger.save_chapter.assert_called_once()
        mock_logger.merge_novel.assert_called_once()

    print("  [PASS] 完整管线测试通过")


def test_create_novel_chapter_generation_failure():
    """测试章节生成失败。"""
    print("测试章节生成失败...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.return_value = _make_mock_outline()

    mock_chapter_gen = MagicMock()
    mock_chapter_gen.generate_chapter.side_effect = RuntimeError("生成失败")

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot), \
         patch("src.create.ChapterGenerator", return_value=mock_chapter_gen):
        result = create_novel("测试", num_chapters=1, incremental=False)
        assert result["success"] is False
        assert "生成失败" in result["error"]

    print("  [PASS] 章节生成失败测试通过")


def test_create_novel_with_chapter_range():
    """测试指定章节范围。"""
    print("测试章节范围...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.return_value = _make_mock_outline()

    mock_chapter_gen = MagicMock()
    mock_chapter_gen.generate_chapter.return_value = _make_mock_chapter(3, 2000)
    mock_chapter_gen.quality_check.return_value = {"passed": True, "issues": [], "suggestions": []}

    mock_logger = MagicMock()

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot), \
         patch("src.create.ChapterGenerator", return_value=mock_chapter_gen), \
         patch("src.create.NovelLogger", return_value=mock_logger):
        result = create_novel("测试", chapter_range=(3, 4))
        assert result["success"] is True
        assert result["chapters_generated"] == 2  # 3 和 4 两章

    print("  [PASS] 章节范围测试通过")


def test_create_novel_incremental_resume():
    """测试增量模式断点续写。"""
    print("测试增量续写...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.return_value = _make_mock_outline()

    mock_chapter_gen = MagicMock()
    mock_chapter_gen.generate_chapter.return_value = _make_mock_chapter(6, 2500)
    mock_chapter_gen.quality_check.return_value = {"passed": True, "issues": [], "suggestions": []}

    mock_logger = MagicMock()
    mock_logger.resume_writing.return_value = 6  # 从第6章续写

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot), \
         patch("src.create.ChapterGenerator", return_value=mock_chapter_gen), \
         patch("src.create.NovelLogger", return_value=mock_logger):
        result = create_novel("测试", num_chapters=3, incremental=True)
        assert result["success"] is True
        # 从第6章开始，生成3章 = 6, 7, 8
        assert result["chapters_generated"] == 3

    print("  [PASS] 增量续写测试通过")


# ── quick_create 测试 ──────────────────────────────────────────

def test_quick_create():
    """测试快速创作。"""
    print("测试快速创作...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.return_value = _make_mock_outline()

    mock_chapter_gen = MagicMock()
    mock_chapter_gen.generate_chapter.return_value = _make_mock_chapter(1, 2000)
    mock_chapter_gen.quality_check.return_value = {"passed": True, "issues": [], "suggestions": []}

    mock_logger = MagicMock()

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot), \
         patch("src.create.ChapterGenerator", return_value=mock_chapter_gen), \
         patch("src.create.NovelLogger", return_value=mock_logger):
        result = quick_create("测试", chapters=2)
        assert result["success"] is True
        assert result["chapters_generated"] == 2

    print("  [PASS] 快速创作测试通过")


# ── resume_create 测试 ──────────────────────────────────────────

def test_resume_create():
    """测试断点续写。"""
    print("测试断点续写...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.return_value = _make_mock_outline()

    mock_chapter_gen = MagicMock()
    mock_chapter_gen.generate_chapter.return_value = _make_mock_chapter(4, 2500)
    mock_chapter_gen.quality_check.return_value = {"passed": True, "issues": [], "suggestions": []}

    mock_logger = MagicMock()
    mock_logger.resume_writing.return_value = 4

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot), \
         patch("src.create.ChapterGenerator", return_value=mock_chapter_gen), \
         patch("src.create.NovelLogger", return_value=mock_logger):
        result = resume_create("测试", chapters=2)
        assert result["success"] is True
        assert result["chapters_generated"] == 2

    print("  [PASS] 断点续写测试通过")


# ── preview_outline 测试 ──────────────────────────────────────────

def test_preview_outline():
    """测试大纲预览。"""
    print("测试大纲预览...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.return_value = _make_mock_outline()

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot):
        result = preview_outline("测试")
        assert result["success"] is True
        assert result["chapters_generated"] == 0
        assert result["outline"].title == "测试作品"

    print("  [PASS] 大纲预览测试通过")


# ── _load_character_objects 测试 ──────────────────────────────────

def test_load_character_objects():
    """测试 Character 对象加载。"""
    print("测试 Character 对象加载...")
    mock_vault = _make_mock_vault()
    knowledge_base = {
        "characters": [
            {"name": "张三"},
            {"name": "李四"},
        ]
    }

    # mock_vault.load_character 对 "张三" 返回对象，"李四" 返回 None
    def mock_load(name):
        if name == "张三":
            return Character(
                name="张三", aliases=[], identity="", personality="",
                gender="男", faction="", role_tags=[], status="活跃",
                quotes=[], motivation="", current_state="",
                related_settings=[], relationships=[],
            )
        return None

    mock_vault.load_character.side_effect = mock_load
    characters = _load_character_objects(mock_vault, knowledge_base)
    assert len(characters) == 1
    assert characters[0].name == "张三"

    print("  [PASS] Character 对象加载测试通过")


# ── _display_outline 测试 ──────────────────────────────────────────

def test_display_outline():
    """测试大纲显示（不抛异常即可）。"""
    print("测试大纲显示...")
    outline = _make_mock_outline()
    _display_outline(outline, 5)
    print("  [PASS] 大纲显示测试通过")


# ── _error_result 测试 ──────────────────────────────────────────

def test_error_result():
    """测试错误结果构建。"""
    print("测试错误结果构建...")
    result = _error_result("测试作品", "出错了", 2, 5000)
    assert result["success"] is False
    assert result["book_title"] == "测试作品"
    assert result["error"] == "出错了"
    assert result["chapters_generated"] == 2
    assert result["total_words"] == 5000
    assert result["output_dir"] == ""
    print("  [PASS] 错误结果构建测试通过")


# ── 质量检查问题不阻塞 ──────────────────────────────────────────

def test_quality_check_warning_does_not_block():
    """测试质量检查问题只警告不阻塞。"""
    print("测试质量检查不阻塞...")
    mock_vault = _make_mock_vault()
    mock_plot = MagicMock()
    mock_plot.generate_outline.return_value = _make_mock_outline()

    mock_chapter_gen = MagicMock()
    mock_chapter_gen.generate_chapter.return_value = _make_mock_chapter(1, 1500)  # 字数不足
    mock_chapter_gen.quality_check.return_value = {
        "passed": False,
        "issues": [{"type": "字数", "detail": "字数不足", "suggestion": "扩充内容"}],
        "suggestions": [],
    }

    mock_logger = MagicMock()

    with patch("src.create.VaultManager", return_value=mock_vault), \
         patch("src.create.PlotGenerator", return_value=mock_plot), \
         patch("src.create.ChapterGenerator", return_value=mock_chapter_gen), \
         patch("src.create.NovelLogger", return_value=mock_logger):
        result = create_novel("测试", num_chapters=1, incremental=False)
        # 质量问题不阻塞，应成功生成
        assert result["success"] is True
        assert result["chapters_generated"] == 1

    print("  [PASS] 质量检查不阻塞测试通过")


# ── 运行所有测试 ───────────────────────────────────────────────

def run_all_tests():
    """运行所有测试。"""
    print("=" * 50)
    print("创作管线集成测试")
    print("=" * 50)

    tests = [
        test_create_novel_empty_knowledge_base,
        test_create_novel_outline_only,
        test_create_novel_outline_only_output,
        test_create_novel_vault_load_error,
        test_create_novel_outline_generation_error,
        test_create_novel_full_pipeline,
        test_create_novel_chapter_generation_failure,
        test_create_novel_with_chapter_range,
        test_create_novel_incremental_resume,
        test_quick_create,
        test_resume_create,
        test_preview_outline,
        test_load_character_objects,
        test_display_outline,
        test_error_result,
        test_quality_check_warning_does_not_block,
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
