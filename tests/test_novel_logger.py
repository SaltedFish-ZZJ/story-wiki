"""
Story Wiki - 小说日志模块测试
测试章节保存、知识库日志、合并输出、进度追踪、断点续写。
"""
import json
import shutil
import tempfile
from pathlib import Path

from src.interfaces import ChapterContent
from src.novel_logger import NovelLogger, _safe_filename


def _make_logger():
    """创建使用临时目录的 NovelLogger 实例。"""
    tmpdir = tempfile.mkdtemp(prefix="novel_logger_test_")
    return NovelLogger({"output_dir": tmpdir}), Path(tmpdir)


def _make_chapter(num: int, title: str = "", content: str = "", word_count: int = 0) -> ChapterContent:
    """创建测试用 ChapterContent。"""
    return ChapterContent(
        chapter_num=num,
        title=title or f"测试第{num}章",
        content=content or f"这是第{num}章的内容。" * 10,
        word_count=word_count or 2000,
        characters_involved=["角色A", "角色B"],
        events_happened=["事件1"],
    )


# ── save_chapter 测试 ──────────────────────────────────────────

def test_save_chapter_basic():
    """测试基本章节保存。"""
    print("测试章节保存...")
    logger, tmpdir = _make_logger()

    try:
        ch = _make_chapter(1, "初遇", "这是一个测试内容。" * 50, 500)
        logger.save_chapter(1, ch)

        chapter_file = tmpdir / "未命名作品" / "chapter_1.json"
        assert chapter_file.exists(), "章节文件应被创建"

        with open(chapter_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["chapter_num"] == 1
        assert data["title"] == "初遇"
        assert data["word_count"] == 500
        assert "saved_at" in data

        print("  [PASS] 基本章节保存测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_save_chapter_updates_progress():
    """测试保存章节后进度自动更新。"""
    print("测试章节保存更新进度...")
    logger, tmpdir = _make_logger()

    try:
        ch1 = _make_chapter(1, word_count=1000)
        ch2 = _make_chapter(2, word_count=2000)

        logger.save_chapter(1, ch1)
        logger.save_chapter(2, ch2)

        progress = logger.get_progress("未命名作品")
        assert progress["completed_chapters"] == 2, f"应有 2 章完成，实际: {progress['completed_chapters']}"
        assert progress["total_words"] == 3000, f"总字数应为 3000，实际: {progress['total_words']}"
        assert progress["total_chapters"] == 2

        print("  [PASS] 章节保存更新进度测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_save_chapter_invalid_num():
    """测试无效章节号。"""
    print("测试无效章节号...")
    logger, tmpdir = _make_logger()

    try:
        ch = _make_chapter(1)
        try:
            logger.save_chapter(0, ch)
            assert False, "应抛出 ValueError"
        except ValueError as e:
            assert "章节号必须" in str(e)

        try:
            logger.save_chapter(-1, ch)
            assert False, "应抛出 ValueError"
        except ValueError:
            pass

        print("  [PASS] 无效章节号测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_save_chapter_invalid_content():
    """测试无效内容类型。"""
    print("测试无效内容类型...")
    logger, tmpdir = _make_logger()

    try:
        try:
            logger.save_chapter(1, "not a ChapterContent")
            assert False, "应抛出 TypeError"
        except TypeError as e:
            assert "ChapterContent" in str(e)

        print("  [PASS] 无效内容类型测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_save_chapter_overwrite():
    """测试覆盖已保存的章节。"""
    print("测试章节覆盖...")
    logger, tmpdir = _make_logger()

    try:
        ch1 = _make_chapter(1, word_count=500)
        ch1_updated = _make_chapter(1, "初遇（修订版）", word_count=800)

        logger.save_chapter(1, ch1)
        logger.save_chapter(1, ch1_updated)

        progress = logger.get_progress("未命名作品")
        # 覆盖后总字数应更新为新字数
        assert progress["total_words"] == 800, f"覆盖后总字数应为 800，实际: {progress['total_words']}"

        chapter = logger.get_chapter("未命名作品", 1)
        assert chapter.title == "初遇（修订版）"

        print("  [PASS] 章节覆盖测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── update_knowledge_log 测试 ──────────────────────────────────

def test_update_knowledge_log_basic():
    """测试基本知识库日志更新。"""
    print("测试知识库日志更新...")
    logger, tmpdir = _make_logger()

    try:
        changes = {
            "book_title": "测试小说",
            "chapter_num": 1,
            "new_characters": ["张三", "李四"],
            "updated_characters": [],
            "new_events": ["初遇事件"],
            "new_settings": ["现代都市"],
        }
        logger.update_knowledge_log(changes)

        entries = logger.get_knowledge_log("测试小说")
        assert len(entries) == 1
        assert entries[0]["chapter_num"] == 1
        assert len(entries[0]["new_characters"]) == 2
        assert entries[0]["new_characters"] == ["张三", "李四"]
        assert entries[0]["new_events"] == ["初遇事件"]

        print("  [PASS] 知识库日志更新测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_update_knowledge_log_multiple():
    """测试多次更新知识库日志。"""
    print("测试多次知识库日志更新...")
    logger, tmpdir = _make_logger()

    try:
        changes1 = {
            "book_title": "测试小说",
            "chapter_num": 1,
            "new_characters": ["张三"],
            "new_events": [],
            "new_settings": [],
        }
        changes2 = {
            "book_title": "测试小说",
            "chapter_num": 2,
            "new_characters": ["李四"],
            "updated_characters": ["张三"],
            "new_events": ["冲突事件"],
            "new_settings": ["古代背景"],
        }

        logger.update_knowledge_log(changes1)
        logger.update_knowledge_log(changes2)

        entries = logger.get_knowledge_log("测试小说")
        assert len(entries) == 2
        assert entries[1]["chapter_num"] == 2
        assert "李四" in entries[1]["new_characters"]
        assert "张三" in entries[1]["updated_characters"]

        print("  [PASS] 多次知识库日志更新测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_update_knowledge_log_invalid():
    """测试无效的 changes 参数。"""
    print("测试无效知识库日志参数...")
    logger, tmpdir = _make_logger()

    try:
        try:
            logger.update_knowledge_log("not a dict")
            assert False, "应抛出 TypeError"
        except TypeError:
            pass

        print("  [PASS] 无效知识库日志参数测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── merge_novel 测试 ───────────────────────────────────────────

def test_merge_novel_basic():
    """测试基本合并功能。"""
    print("测试小说合并...")
    logger, tmpdir = _make_logger()

    try:
        ch1 = _make_chapter(1, "第一章", "第一章的内容。", 100)
        ch2 = _make_chapter(2, "第二章", "第二章的内容。", 200)
        ch3 = _make_chapter(3, "第三章", "第三章的内容。", 300)

        logger.save_chapter(1, ch1)
        logger.save_chapter(2, ch2)
        logger.save_chapter(3, ch3)

        result = logger.merge_novel("未命名作品")

        assert "# 未命名作品" in result
        assert "## 第 1 章 第一章" in result
        assert "## 第 2 章 第二章" in result
        assert "## 第 3 章 第三章" in result
        assert "第一章的内容。" in result
        assert "第二章的内容。" in result
        assert "第三章的内容。" in result

        # 确认章节顺序正确
        pos1 = result.index("第 1 章")
        pos2 = result.index("第 2 章")
        pos3 = result.index("第 3 章")
        assert pos1 < pos2 < pos3, "章节应按顺序排列"

        print("  [PASS] 小说合并测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_merge_novel_empty():
    """测试合并不存在的小说。"""
    print("测试合并不存在的小说...")
    logger, tmpdir = _make_logger()

    try:
        try:
            logger.merge_novel("不存在的小说")
            assert False, "应抛出 FileNotFoundError"
        except FileNotFoundError:
            pass

        print("  [PASS] 合并不存在的小说测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_merge_novel_no_chapters():
    """测试合并没有章节的小说目录。"""
    print("测试合并无章节小说...")
    logger, tmpdir = _make_logger()

    try:
        # 创建目录但不创建章节文件
        (tmpdir / "空小说").mkdir()

        try:
            logger.merge_novel("空小说")
            assert False, "应抛出 FileNotFoundError"
        except FileNotFoundError:
            pass

        print("  [PASS] 合并无章节小说测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── get_progress 测试 ──────────────────────────────────────────

def test_get_progress_empty():
    """测试获取不存在小说的进度。"""
    print("测试获取不存在小说的进度...")
    logger, tmpdir = _make_logger()

    try:
        progress = logger.get_progress("不存在的小说")
        assert progress["total_chapters"] == 0
        assert progress["completed_chapters"] == 0
        assert progress["total_words"] == 0

        print("  [PASS] 获取不存在小说的进度测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_get_progress_after_saves():
    """测试保存章节后的进度。"""
    print("测试保存章节后的进度...")
    logger, tmpdir = _make_logger()

    try:
        for i in range(1, 6):
            ch = _make_chapter(i, word_count=1000 * i)
            logger.save_chapter(i, ch)

        progress = logger.get_progress("未命名作品")
        assert progress["completed_chapters"] == 5
        assert progress["total_words"] == 15000  # 1000+2000+3000+4000+5000
        assert progress["total_chapters"] == 5
        assert progress["last_updated"] != ""

        print("  [PASS] 保存章节后的进度测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── resume_writing 测试 ────────────────────────────────────────

def test_resume_writing_empty():
    """测试无任何章节时断点续写。"""
    print("测试空项目断点续写...")
    logger, tmpdir = _make_logger()

    try:
        next_ch = logger.resume_writing("新小说")
        assert next_ch == 1, "无章节时应返回 1"

        print("  [PASS] 空项目断点续写测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_resume_writing_with_chapters():
    """测试有章节时断点续写。"""
    print("测试有章节断点续写...")
    logger, tmpdir = _make_logger()

    try:
        logger.save_chapter(1, _make_chapter(1))
        logger.save_chapter(2, _make_chapter(2))
        logger.save_chapter(3, _make_chapter(3))

        next_ch = logger.resume_writing("未命名作品")
        assert next_ch == 4, f"有 3 章时应返回 4，实际: {next_ch}"

        print("  [PASS] 有章节断点续写测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_resume_writing_non_sequential():
    """测试非连续章节的断点续写。"""
    print("测试非连续章节断点续写...")
    logger, tmpdir = _make_logger()

    try:
        # 模拟跳过章节：只保存 1、3、5
        logger.save_chapter(1, _make_chapter(1))
        logger.save_chapter(3, _make_chapter(3))
        logger.save_chapter(5, _make_chapter(5))

        next_ch = logger.resume_writing("未命名作品")
        assert next_ch == 6, f"最大章节号为 5 时应返回 6，实际: {next_ch}"

        print("  [PASS] 非连续章节断点续写测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_resume_writing_nonexistent_novel():
    """测试不存在的小说断点续写。"""
    print("测试不存在小说的断点续写...")
    logger, tmpdir = _make_logger()

    try:
        next_ch = logger.resume_writing("不存在的小说")
        assert next_ch == 1

        print("  [PASS] 不存在小说的断点续写测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── run 接口测试 ───────────────────────────────────────────────

def test_run_save_chapter():
    """测试 run 方法保存章节。"""
    print("测试 run 保存章节...")
    logger, tmpdir = _make_logger()

    try:
        ch = _make_chapter(1, word_count=500)
        result = logger.run({
            "action": "save_chapter",
            "chapter_num": 1,
            "content": ch,
        })
        assert result["success"] is True
        assert "已保存" in result["message"]

        print("  [PASS] run 保存章节测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_get_progress():
    """测试 run 方法获取进度。"""
    print("测试 run 获取进度...")
    logger, tmpdir = _make_logger()

    try:
        result = logger.run({
            "action": "get_progress",
            "book_title": "测试小说",
        })
        assert result["success"] is True
        assert "progress" in result
        assert result["progress"]["completed_chapters"] == 0

        print("  [PASS] run 获取进度测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_resume_writing():
    """测试 run 方法断点续写。"""
    print("测试 run 断点续写...")
    logger, tmpdir = _make_logger()

    try:
        logger.save_chapter(1, _make_chapter(1))

        result = logger.run({
            "action": "resume_writing",
            "book_title": "未命名作品",
        })
        assert result["success"] is True
        assert result["next_chapter"] == 2

        print("  [PASS] run 断点续写测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_merge_novel():
    """测试 run 方法合并小说。"""
    print("测试 run 合并小说...")
    logger, tmpdir = _make_logger()

    try:
        logger.save_chapter(1, _make_chapter(1, "第1章", "内容一"))
        logger.save_chapter(2, _make_chapter(2, "第2章", "内容二"))

        result = logger.run({
            "action": "merge_novel",
            "book_title": "未命名作品",
        })
        assert result["success"] is True
        assert "内容一" in result["content"]
        assert "内容二" in result["content"]

        print("  [PASS] run 合并小说测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_unknown_action():
    """测试未知 action。"""
    print("测试未知 action...")
    logger, tmpdir = _make_logger()

    try:
        result = logger.run({"action": "unknown_action"})
        assert result["success"] is False
        assert "未知" in result["error"]

        print("  [PASS] 未知 action 测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_missing_action():
    """测试缺少 action 字段。"""
    print("测试缺少 action 字段...")
    logger, tmpdir = _make_logger()

    try:
        result = logger.run({"book_title": "test"})
        assert result["success"] is False
        assert "action" in result["error"]

        print("  [PASS] 缺少 action 字段测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_not_dict():
    """测试非 dict 输入。"""
    print("测试非 dict 输入...")
    logger, tmpdir = _make_logger()

    try:
        result = logger.run("not a dict")
        assert result["success"] is False

        print("  [PASS] 非 dict 输入测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── validate 测试 ──────────────────────────────────────────────

def test_validate():
    """测试 validate 方法。"""
    print("测试 validate...")
    logger, tmpdir = _make_logger()

    try:
        assert logger.validate({"success": True, "message": "ok"}) is True
        assert logger.validate({"success": True, "content": "text"}) is True
        assert logger.validate({"success": True, "progress": {}}) is True
        assert logger.validate({"success": True, "next_chapter": 1}) is True
        assert logger.validate({"success": False, "error": "err"}) is True
        assert logger.validate({"success": True}) is False  # 缺少必要字段
        assert logger.validate("not dict") is False

        print("  [PASS] validate 测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 辅助方法测试 ───────────────────────────────────────────────

def test_list_novels():
    """测试列出小说。"""
    print("测试列出小说...")
    logger, tmpdir = _make_logger()

    try:
        assert logger.list_novels() == []

        logger.save_chapter(1, _make_chapter(1))
        novels = logger.list_novels()
        assert len(novels) == 1

        print("  [PASS] 列出小说测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_delete_novel():
    """测试删除小说。"""
    print("测试删除小说...")
    logger, tmpdir = _make_logger()

    try:
        logger.save_chapter(1, _make_chapter(1))
        assert logger.list_novels() != []

        success = logger.delete_novel("未命名作品")
        assert success is True
        assert logger.list_novels() == []

        # 删除不存在的
        success = logger.delete_novel("不存在")
        assert success is False

        print("  [PASS] 删除小说测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_get_chapter():
    """测试获取指定章节。"""
    print("测试获取指定章节...")
    logger, tmpdir = _make_logger()

    try:
        ch = _make_chapter(2, "第二章", "测试内容", 123)
        logger.save_chapter(2, ch)

        retrieved = logger.get_chapter("未命名作品", 2)
        assert retrieved is not None
        assert retrieved.chapter_num == 2
        assert retrieved.title == "第二章"
        assert retrieved.word_count == 123

        # 不存在的章节
        missing = logger.get_chapter("未命名作品", 99)
        assert missing is None

        print("  [PASS] 获取指定章节测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_safe_filename():
    """测试安全文件名生成。"""
    print("测试安全文件名...")
    assert _safe_filename("红楼梦") == "红楼梦"
    assert _safe_filename('Test<>:"/\\|?*') == "Test_________"
    assert _safe_filename("  spaces  ") == "spaces"
    print("  [PASS] 安全文件名测试通过")


# ── 运行所有测试 ───────────────────────────────────────────────

def run_all_tests():
    """运行所有测试。"""
    print("=" * 50)
    print("小说日志模块测试")
    print("=" * 50)

    tests = [
        # save_chapter
        test_save_chapter_basic,
        test_save_chapter_updates_progress,
        test_save_chapter_invalid_num,
        test_save_chapter_invalid_content,
        test_save_chapter_overwrite,
        # update_knowledge_log
        test_update_knowledge_log_basic,
        test_update_knowledge_log_multiple,
        test_update_knowledge_log_invalid,
        # merge_novel
        test_merge_novel_basic,
        test_merge_novel_empty,
        test_merge_novel_no_chapters,
        # get_progress
        test_get_progress_empty,
        test_get_progress_after_saves,
        # resume_writing
        test_resume_writing_empty,
        test_resume_writing_with_chapters,
        test_resume_writing_non_sequential,
        test_resume_writing_nonexistent_novel,
        # run
        test_run_save_chapter,
        test_run_get_progress,
        test_run_resume_writing,
        test_run_merge_novel,
        test_run_unknown_action,
        test_run_missing_action,
        test_run_not_dict,
        # validate
        test_validate,
        # 辅助
        test_list_novels,
        test_delete_novel,
        test_get_chapter,
        test_safe_filename,
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
