"""
Story Wiki - 质量检测器模块测试
测试逻辑一致性、字数检查、重复检测、敏感词检测。
"""
import shutil
import tempfile
from pathlib import Path

from src.interfaces import ChapterContent, Character, Event
from src.quality_checker import QualityChecker, get_quality_checker, check_chapter_quality


# ── 测试数据 ──────────────────────────────────────────────────

def _make_chapter(num: int = 1, content: str = "", word_count: int = 2500) -> ChapterContent:
    """创建测试用 ChapterContent。"""
    if not content:
        content = "这是一个测试内容。" * 100
    return ChapterContent(
        chapter_num=num,
        title=f"测试第{num}章",
        content=content,
        word_count=word_count,
        characters_involved=["角色A", "角色B"],
        events_happened=["事件1"],
    )


def _make_character(name: str = "角色A", personality: str = "勇敢") -> Character:
    """创建测试用 Character。"""
    return Character(
        name=name,
        personality=personality,
        gender="男",
    )


def _make_event(name: str = "事件1", chapter: str = "测试第1章") -> Event:
    """创建测试用 Event。"""
    return Event(
        name=name,
        chapter=chapter,
        participants=["角色A"],
    )


def _make_checker():
    """创建使用临时目录的 QualityChecker 实例。"""
    tmpdir = tempfile.mkdtemp(prefix="quality_checker_test_")
    # 创建敏感词文件
    words_file = Path(tmpdir) / "sensitive_words.txt"
    words_file.write_text("# 测试敏感词\n敏感词A\n敏感词B\n暴力词\n", encoding="utf-8")
    return QualityChecker({"sensitive_words_path": words_file}), Path(tmpdir)


# ── check_logic_consistency 测试 ──────────────────────────────

def test_check_logic_consistency_pass():
    """测试逻辑一致性检查通过。"""
    print("测试逻辑一致性检查通过...")
    checker, tmpdir = _make_checker()

    try:
        content = _make_chapter()
        # 添加两个角色都在列表中
        characters = [_make_character("角色A"), _make_character("角色B")]
        events = [_make_event()]

        result = checker.check_logic_consistency(content, characters, events)

        assert result["passed"] is True
        assert len(result["issues"]) == 0

        print("  [PASS] 逻辑一致性检查通过测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_check_logic_consistency_unknown_character():
    """测试检测到未知人物。"""
    print("测试检测未知人物...")
    checker, tmpdir = _make_checker()

    try:
        # 创建章节，手动设置 characters_involved
        content = _make_chapter()
        content.characters_involved = ["角色A", "未知角色"]
        characters = [_make_character("角色A")]
        events = []

        result = checker.check_logic_consistency(content, characters, events)

        assert result["passed"] is False
        assert any("未知角色" in issue for issue in result["issues"])

        print("  [PASS] 检测未知人物测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── check_word_count 测试 ─────────────────────────────────────

def test_check_word_count_pass():
    """测试字数检查通过。"""
    print("测试字数检查通过...")
    checker, tmpdir = _make_checker()

    try:
        content = _make_chapter(word_count=2500)
        passed = checker.check_word_count(content, 2000, 3000)
        assert passed is True

        print("  [PASS] 字数检查通过测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_check_word_count_too_short():
    """测试字数过少。"""
    print("测试字数过少...")
    checker, tmpdir = _make_checker()

    try:
        content = _make_chapter(word_count=1000)
        passed = checker.check_word_count(content, 2000, 3000)
        assert passed is False

        print("  [PASS] 字数过少测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_check_word_count_too_long():
    """测试字数过多。"""
    print("测试字数过多...")
    checker, tmpdir = _make_checker()

    try:
        content = _make_chapter(word_count=5000)
        passed = checker.check_word_count(content, 2000, 3000)
        assert passed is False

        print("  [PASS] 字数过多测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_check_word_count_calculate():
    """测试自动计算字数。"""
    print("测试自动计算字数...")
    checker, tmpdir = _make_checker()

    try:
        # "这是测试内容。" * 100 = 600字符（每个句子6个中文字符）
        content = _make_chapter(word_count=0, content="这是测试内容。" * 100)
        word_count = checker._count_words(content.content)
        # 600个中文字符
        assert word_count == 600

        passed = checker.check_word_count(content, 100, 800)
        assert passed is True

        print("  [PASS] 自动计算字数测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── check_duplicates 测试 ─────────────────────────────────────

def test_check_duplicates_none():
    """测试无重复内容。"""
    print("测试无重复内容...")
    checker, tmpdir = _make_checker()

    try:
        content = _make_chapter(content="这是全新的内容，完全没有重复。" * 50)
        prev_chapters = ["这是之前的内容，完全不同的故事。" * 50]

        has_dup = checker.check_duplicates(content, prev_chapters)
        assert has_dup is False

        print("  [PASS] 无重复内容测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_check_duplicates_found():
    """测试检测到重复内容。"""
    print("测试检测重复内容...")
    checker, tmpdir = _make_checker()

    try:
        # 创建大量重复内容
        repeated_text = "这是重复的内容片段，用于测试重复检测功能。" * 50
        content = _make_chapter(content=repeated_text)
        prev_chapters = [repeated_text]

        has_dup = checker.check_duplicates(content, prev_chapters)
        assert has_dup is True

        print("  [PASS] 检测重复内容测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_check_duplicates_no_previous():
    """测试无前文内容。"""
    print("测试无前文内容...")
    checker, tmpdir = _make_checker()

    try:
        content = _make_chapter()
        has_dup = checker.check_duplicates(content, [])
        assert has_dup is False

        print("  [PASS] 无前文内容测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── check_sensitive_words 测试 ────────────────────────────────

def test_check_sensitive_words_none():
    """测试无敏感词。"""
    print("测试无敏感词...")
    checker, tmpdir = _make_checker()

    try:
        content = _make_chapter(content="这是正常的内容，没有任何敏感词。" * 50)
        found = checker.check_sensitive_words(content)
        assert len(found) == 0

        print("  [PASS] 无敏感词测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_check_sensitive_words_found():
    """测试检测到敏感词。"""
    print("测试检测敏感词...")
    checker, tmpdir = _make_checker()

    try:
        content = _make_chapter(content="这里包含敏感词A和敏感词B的内容。" * 50)
        found = checker.check_sensitive_words(content)

        assert "敏感词A" in found
        assert "敏感词B" in found

        print("  [PASS] 检测敏感词测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_check_sensitive_words_multiple():
    """测试检测多个敏感词。"""
    print("测试检测多个敏感词...")
    checker, tmpdir = _make_checker()

    try:
        content = _make_chapter(content="这里包含敏感词A和暴力词的内容。" * 50)
        found = checker.check_sensitive_words(content)

        assert "敏感词A" in found
        assert "暴力词" in found
        assert len(found) >= 2

        print("  [PASS] 检测多个敏感词测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── full_check 测试 ───────────────────────────────────────────

def test_full_check_pass():
    """测试全量检查通过。"""
    print("测试全量检查通过...")
    checker, tmpdir = _make_checker()

    try:
        content = _make_chapter(content="这是正常的内容。" * 100)
        # 添加两个角色都在列表中
        characters = [_make_character("角色A"), _make_character("角色B")]
        events = [_make_event()]

        result = checker.full_check(content, characters, events, [])

        assert result["passed"] is True
        assert result["word_count_ok"] is True
        assert result["has_duplicates"] is False
        assert len(result["sensitive_words"]) == 0
        assert len(result["logic_issues"]) == 0

        print("  [PASS] 全量检查通过测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_full_check_multiple_issues():
    """测试全量检查发现多个问题。"""
    print("测试全量检查多个问题...")
    checker, tmpdir = _make_checker()

    try:
        # 创建一个有问题的内容：字数少 + 敏感词
        content = _make_chapter(
            content="包含敏感词A的内容。" * 20,
            word_count=500
        )

        result = checker.full_check(content, [], [], [])

        assert result["passed"] is False
        assert result["word_count_ok"] is False
        assert len(result["sensitive_words"]) > 0
        assert len(result["all_issues"]) > 0

        print("  [PASS] 全量检查多个问题测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── run 接口测试 ──────────────────────────────────────────────

def test_run_check_words():
    """测试 run 方法字数检查。"""
    print("测试 run 字数检查...")
    checker, tmpdir = _make_checker()

    try:
        result = checker.run({
            "action": "check_words",
            "content": _make_chapter(word_count=2500),
        })
        assert result["success"] is True
        assert result["passed"] is True

        print("  [PASS] run 字数检查测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_check_sensitive():
    """测试 run 方法敏感词检查。"""
    print("测试 run 敏感词检查...")
    checker, tmpdir = _make_checker()

    try:
        result = checker.run({
            "action": "check_sensitive",
            "content": _make_chapter(content="包含敏感词A的内容。" * 50),
        })
        assert result["success"] is True
        assert "敏感词A" in result["sensitive_words"]

        print("  [PASS] run 敏感词检查测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_full_check():
    """测试 run 方法全量检查。"""
    print("测试 run 全量检查...")
    checker, tmpdir = _make_checker()

    try:
        result = checker.run({
            "action": "full_check",
            "content": _make_chapter(content="正常内容。" * 100),
        })
        assert result["success"] is True
        assert "result" in result

        print("  [PASS] run 全量检查测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_unknown_action():
    """测试未知 action。"""
    print("测试未知 action...")
    checker, tmpdir = _make_checker()

    try:
        result = checker.run({"action": "unknown_action"})
        assert result["success"] is False
        assert "未知" in result["error"]

        print("  [PASS] 未知 action 测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── validate 测试 ─────────────────────────────────────────────

def test_validate():
    """测试 validate 方法。"""
    print("测试 validate...")
    checker, tmpdir = _make_checker()

    try:
        assert checker.validate({"success": True, "result": {}}) is True
        assert checker.validate({"success": True, "passed": True}) is True
        assert checker.validate({"success": True, "has_duplicates": False}) is True
        assert checker.validate({"success": True, "sensitive_words": []}) is True
        assert checker.validate({"success": False, "error": "err"}) is True
        assert checker.validate({"success": True}) is False
        assert checker.validate("not dict") is False

        print("  [PASS] validate 测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 便捷函数测试 ──────────────────────────────────────────────

def test_get_quality_checker():
    """测试 get_quality_checker 便捷函数。"""
    print("测试 get_quality_checker...")
    checker = get_quality_checker()
    assert isinstance(checker, QualityChecker)
    print("  [PASS] get_quality_checker 测试通过")


def test_check_chapter_quality():
    """测试 check_chapter_quality 便捷函数。"""
    print("测试 check_chapter_quality...")
    tmpdir = tempfile.mkdtemp(prefix="check_chapter_quality_test_")

    try:
        # 创建敏感词文件
        words_file = Path(tmpdir) / "sensitive_words.txt"
        words_file.write_text("", encoding="utf-8")

        content = _make_chapter(content="正常内容。" * 100)
        characters = [_make_character()]
        events = [_make_event()]

        result = check_chapter_quality(content, characters, events, [])

        assert "passed" in result
        assert "word_count" in result

        print("  [PASS] check_chapter_quality 测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 辅助方法测试 ──────────────────────────────────────────────

def test_count_words():
    """测试字数统计。"""
    print("测试字数统计...")
    checker, tmpdir = _make_checker()

    try:
        # 中文字符
        count = checker._count_words("这是测试内容")
        assert count == 6

        # 混合内容：4中文字符 + "Hello" + "World" = 6
        count = checker._count_words("这是Hello World测试")
        assert count == 6  # 4中文 + 2英文单词

        # 纯英文
        count = checker._count_words("Hello World")
        assert count == 2

        print("  [PASS] 字数统计测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_extract_windows():
    """测试滑动窗口提取。"""
    print("测试滑动窗口提取...")
    checker, tmpdir = _make_checker()

    try:
        text = "abcdefghij"
        windows = checker._extract_windows(text, 3)

        assert len(windows) == 8  # 10 - 3 + 1 = 8
        assert "abc" in windows
        assert "hij" in windows

        print("  [PASS] 滑动窗口提取测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_load_sensitive_words():
    """测试加载敏感词词库。"""
    print("测试加载敏感词词库...")
    checker, tmpdir = _make_checker()

    try:
        words = checker._load_sensitive_words()
        assert "敏感词A" in words
        assert "敏感词B" in words
        assert "暴力词" in words
        # 注释和空行不应被加载
        assert "# 测试敏感词" not in words

        # 测试缓存
        words2 = checker._load_sensitive_words()
        assert words is words2  # 应该返回同一个缓存对象

        print("  [PASS] 加载敏感词词库测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 运行所有测试 ──────────────────────────────────────────────

def run_all_tests():
    """运行所有测试。"""
    print("=" * 50)
    print("质量检测器模块测试")
    print("=" * 50)

    tests = [
        # check_logic_consistency
        test_check_logic_consistency_pass,
        test_check_logic_consistency_unknown_character,
        # check_word_count
        test_check_word_count_pass,
        test_check_word_count_too_short,
        test_check_word_count_too_long,
        test_check_word_count_calculate,
        # check_duplicates
        test_check_duplicates_none,
        test_check_duplicates_found,
        test_check_duplicates_no_previous,
        # check_sensitive_words
        test_check_sensitive_words_none,
        test_check_sensitive_words_found,
        test_check_sensitive_words_multiple,
        # full_check
        test_full_check_pass,
        test_full_check_multiple_issues,
        # run
        test_run_check_words,
        test_run_check_sensitive,
        test_run_full_check,
        test_run_unknown_action,
        # validate
        test_validate,
        # 便捷函数
        test_get_quality_checker,
        test_check_chapter_quality,
        # 辅助方法
        test_count_words,
        test_extract_windows,
        test_load_sensitive_words,
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
