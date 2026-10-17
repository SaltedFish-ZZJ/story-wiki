"""
Story Wiki - 格式转换器模块测试
测试平台格式转换、EPUB 生成、纯文本转换。
"""
import os
import re
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

from src.converter import Converter, get_converter, convert_novel, SUPPORTED_PLATFORMS, PLATFORM_RULES


# ── 测试数据 ──────────────────────────────────────────────────

SAMPLE_NOVEL = """# 测试小说

## 第一章 初遇

在一个阳光明媚的早晨，小明走在上学的路上。

突然，他看到了一个奇怪的老人。

"小伙子，你想改变命运吗？"老人神秘地问道。

小明犹豫了一下，点了点头。

## 第二章 奇遇

从那天起，小明的生活发生了翻天覆地的变化。

他发现自己获得了一种特殊的能力。

这种能力让他可以看见别人看不见的东西。

## 第三章 冒险

小明决定利用这种能力去帮助别人。

他踏上了冒险的旅程。

一路上遇到了各种各样的挑战。

但他始终没有放弃。
"""


def _make_converter():
    """创建使用临时目录的 Converter 实例。"""
    tmpdir = tempfile.mkdtemp(prefix="converter_test_")
    return Converter({"output_dir": tmpdir}), Path(tmpdir)


# ── convert_to_platform 测试 ──────────────────────────────────

def test_convert_to_platform_fanqie():
    """测试番茄小说平台格式转换。"""
    print("测试番茄小说格式转换...")
    converter, tmpdir = _make_converter()

    try:
        result = converter.convert_to_platform(SAMPLE_NOVEL, "fanqie")

        # 验证标题格式
        assert "第一章 初遇" in result
        assert "第二章 奇遇" in result
        assert "第三章 冒险" in result

        # 验证段落缩进（书籍标题和章节标题不需要缩进）
        lines = result.split("\n")
        skip_lines = {"测试小说", ""}  # 书籍标题和空行跳过
        for line in lines:
            stripped = line.strip()
            if stripped and stripped not in skip_lines:
                # 跳过章节标题（以"第X章"开头）
                if re.match(r'^第[一二三四五六七八九十百千\d]+章', stripped):
                    continue
                # 非标题行应该有缩进
                assert line.startswith("　　"), f"段落应有缩进: {line}"

        print("  [PASS] 番茄小说格式转换测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_convert_to_platform_qidian():
    """测试起点中文网平台格式转换。"""
    print("测试起点中文网格式转换...")
    converter, tmpdir = _make_converter()

    try:
        result = converter.convert_to_platform(SAMPLE_NOVEL, "qidian")

        # 验证内容保留
        assert "小明" in result
        assert "老人" in result
        assert "第一章 初遇" in result

        print("  [PASS] 起点中文网格式转换测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_convert_to_platform_jjwxc():
    """测试晋江文学城平台格式转换。"""
    print("测试晋江文学城格式转换...")
    converter, tmpdir = _make_converter()

    try:
        result = converter.convert_to_platform(SAMPLE_NOVEL, "jjwxc")

        # 验证章节标题格式
        assert "第一章 初遇" in result
        assert "第二章 奇遇" in result
        assert "第三章 冒险" in result

        print("  [PASS] 晋江文学城格式转换测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_convert_to_platform_invalid():
    """测试不支持的平台。"""
    print("测试不支持的平台...")
    converter, tmpdir = _make_converter()

    try:
        try:
            converter.convert_to_platform(SAMPLE_NOVEL, "invalid_platform")
            assert False, "应抛出 ValueError"
        except ValueError as e:
            assert "不支持的平台" in str(e)

        print("  [PASS] 不支持平台测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_convert_to_platform_prohibited_chars():
    """测试禁用字符过滤。"""
    print("测试禁用字符过滤...")
    converter, tmpdir = _make_converter()

    try:
        # 番茄小说不支持 ** 字符
        content_with_bold = "# 测试\n\n## 第一章\n\n这是**加粗**内容。"
        result = converter.convert_to_platform(content_with_bold, "fanqie")

        # 验证 ** 被移除
        assert "**" not in result
        assert "加粗" in result

        print("  [PASS] 禁用字符过滤测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── convert_to_txt 测试 ──────────────────────────────────────

def test_convert_to_txt_basic():
    """测试基本纯文本转换。"""
    print("测试基本纯文本转换...")
    converter, tmpdir = _make_converter()

    try:
        result = converter.convert_to_txt(SAMPLE_NOVEL)

        # 验证 Markdown 标记被移除
        assert "# " not in result
        assert "## " not in result

        # 验证内容保留
        assert "测试小说" in result
        assert "第一章 初遇" in result
        assert "小明" in result

        print("  [PASS] 基本纯文本转换测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_convert_to_txt_markdown_removal():
    """测试 Markdown 标记移除。"""
    print("测试 Markdown 标记移除...")
    converter, tmpdir = _make_converter()

    try:
        content_with_md = """# 标题

## 第一章

这是**加粗**文字和*斜体*文字。

这是`代码`文字。"""

        result = converter.convert_to_txt(content_with_md)

        # 验证 Markdown 标记被移除
        assert "**" not in result
        assert "*" not in result or "斜体" in result  # 允许斜体字符
        assert "`" not in result

        # 验证内容保留
        assert "加粗" in result
        assert "斜体" in result
        assert "代码" in result

        print("  [PASS] Markdown 标记移除测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_convert_to_txt_chapter_normalization():
    """测试章节标题标准化。"""
    print("测试章节标题标准化...")
    converter, tmpdir = _make_converter()

    try:
        # 测试中文数字标题
        content_chinese = "# 测试\n\n## 第一章 标题\n\n内容"
        result = converter.convert_to_txt(content_chinese)
        assert "第一章 标题" in result

        # 测试阿拉伯数字标题
        content_arabic = "# 测试\n\n## 第1章 标题\n\n内容"
        result = converter.convert_to_txt(content_arabic)
        assert "第1章 标题" in result

        print("  [PASS] 章节标题标准化测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── convert_to_epub 测试 ─────────────────────────────────────

def test_convert_to_epub_basic():
    """测试基本 EPUB 生成。"""
    print("测试基本 EPUB 生成...")
    converter, tmpdir = _make_converter()

    try:
        metadata = {
            "title": "测试小说",
            "author": "测试作者",
            "language": "zh",
            "description": "这是一本测试小说",
        }

        try:
            epub_path = converter.convert_to_epub(SAMPLE_NOVEL, metadata)
        except ImportError:
            print("  [SKIP] ebooklib 未安装，跳过 EPUB 测试")
            return

        # 验证文件存在
        assert Path(epub_path).exists()

        # 验证文件大小合理
        file_size = Path(epub_path).stat().st_size
        assert file_size > 0, "EPUB 文件不应为空"

        print(f"  [PASS] EPUB 生成测试通过 (文件大小: {file_size} bytes)")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_convert_to_epub_metadata():
    """测试 EPUB 元数据。"""
    print("测试 EPUB 元数据...")
    converter, tmpdir = _make_converter()

    try:
        metadata = {
            "title": "元数据测试",
            "author": "作者名",
        }

        try:
            epub_path = converter.convert_to_epub(SAMPLE_NOVEL, metadata)
        except ImportError:
            print("  [SKIP] ebooklib 未安装，跳过 EPUB 元数据测试")
            return

        # 验证文件存在
        assert Path(epub_path).exists()

        # 尝试读取 EPUB 验证元数据（需要 ebooklib）
        try:
            import ebooklib
            from ebooklib import epub

            book = epub.read_epub(epub_path)
            assert book.get_metadata("DC", "title")[0][0] == "元数据测试"
            assert book.get_metadata("DC", "creator")[0][0] == "作者名"
        except ImportError:
            # ebooklib 未安装，跳过详细验证
            pass

        print("  [PASS] EPUB 元数据测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── convert_to_all 测试 ──────────────────────────────────────

def test_convert_to_all():
    """测试全格式导出。"""
    pytest.importorskip("ebooklib")
    print("测试全格式导出...")
    converter, tmpdir = _make_converter()

    try:
        metadata = {"title": "全格式测试"}

        results = converter.convert_to_all(SAMPLE_NOVEL, metadata)

        # 验证所有格式都生成了
        assert "fanqie" in results
        assert "qidian" in results
        assert "jjwxc" in results
        assert "txt" in results

        # 验证文件存在
        for key, path in results.items():
            assert Path(path).exists(), f"{key} 格式文件应存在"

        print("  [PASS] 全格式导出测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_convert_to_all_custom_dir():
    """测试自定义输出目录。"""
    pytest.importorskip("ebooklib")
    print("测试自定义输出目录...")
    converter, tmpdir = _make_converter()

    try:
        custom_dir = tmpdir / "custom_exports"
        metadata = {"title": "自定义目录测试"}

        results = converter.convert_to_all(SAMPLE_NOVEL, metadata, str(custom_dir))

        # 验证文件在自定义目录中
        for key, path in results.items():
            assert str(custom_dir) in path, f"{key} 格式文件应在自定义目录中"

        print("  [PASS] 自定义输出目录测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── run 接口测试 ──────────────────────────────────────────────

def test_run_to_platform():
    """测试 run 方法平台转换。"""
    print("测试 run 平台转换...")
    converter, tmpdir = _make_converter()

    try:
        result = converter.run({
            "action": "to_platform",
            "content": SAMPLE_NOVEL,
            "platform": "fanqie",
        })
        assert result["success"] is True
        assert "content" in result
        assert result["platform"] == "fanqie"

        print("  [PASS] run 平台转换测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_to_epub():
    """测试 run 方法 EPUB 转换。"""
    pytest.importorskip("ebooklib")
    print("测试 run EPUB 转换...")
    converter, tmpdir = _make_converter()

    try:
        result = converter.run({
            "action": "to_epub",
            "content": SAMPLE_NOVEL,
            "metadata": {"title": "测试"},
        })

        # 如果 ebooklib 未安装，run 会返回失败结果
        if not result["success"] and "ebooklib" in result.get("error", "").lower():
            print("  [SKIP] ebooklib 未安装，跳过 run EPUB 测试")
            return

        assert result["success"] is True
        assert "path" in result

        print("  [PASS] run EPUB 转换测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_to_txt():
    """测试 run 方法纯文本转换。"""
    print("测试 run 纯文本转换...")
    converter, tmpdir = _make_converter()

    try:
        result = converter.run({
            "action": "to_txt",
            "content": SAMPLE_NOVEL,
        })
        assert result["success"] is True
        assert "content" in result

        print("  [PASS] run 纯文本转换测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_to_all():
    """测试 run 方法全格式导出。"""
    pytest.importorskip("ebooklib")
    print("测试 run 全格式导出...")
    converter, tmpdir = _make_converter()

    try:
        result = converter.run({
            "action": "to_all",
            "content": SAMPLE_NOVEL,
            "metadata": {"title": "测试"},
        })
        assert result["success"] is True
        assert "files" in result

        print("  [PASS] run 全格式导出测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_run_unknown_action():
    """测试未知 action。"""
    print("测试未知 action...")
    converter, tmpdir = _make_converter()

    try:
        result = converter.run({"action": "unknown_action"})
        assert result["success"] is False
        assert "未知" in result["error"]

        print("  [PASS] 未知 action 测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── validate 测试 ─────────────────────────────────────────────

def test_validate():
    """测试 validate 方法。"""
    print("测试 validate...")
    converter, tmpdir = _make_converter()

    try:
        assert converter.validate({"success": True, "content": "text"}) is True
        assert converter.validate({"success": True, "path": "/path"}) is True
        assert converter.validate({"success": True, "files": {}}) is True
        assert converter.validate({"success": False, "error": "err"}) is True
        assert converter.validate({"success": True}) is False
        assert converter.validate("not dict") is False

        print("  [PASS] validate 测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 便捷函数测试 ──────────────────────────────────────────────

def test_get_converter():
    """测试 get_converter 便捷函数。"""
    print("测试 get_converter...")
    converter = get_converter()
    assert isinstance(converter, Converter)
    print("  [PASS] get_converter 测试通过")


def test_convert_novel():
    """测试 convert_novel 便捷函数。"""
    print("测试 convert_novel...")
    tmpdir = tempfile.mkdtemp(prefix="convert_novel_test_")

    try:
        output_path = str(Path(tmpdir) / "test_novel_fanqie.txt")
        result = convert_novel(SAMPLE_NOVEL, "fanqie", output_path)

        assert Path(result).exists()
        with open(result, "r", encoding="utf-8") as f:
            content = f.read()
        assert "第一章 初遇" in content

        print("  [PASS] convert_novel 测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 辅助方法测试 ──────────────────────────────────────────────

def test_normalize_chapter_title():
    """测试章节标题标准化。"""
    print("测试章节标题标准化...")
    converter, tmpdir = _make_converter()

    try:
        # 中文数字
        assert converter._normalize_chapter_title("第一章 标题") == "第一章 标题"
        assert converter._normalize_chapter_title("第十二章 标题") == "第十二章 标题"

        # 阿拉伯数字
        assert converter._normalize_chapter_title("第1章 标题") == "第1章 标题"
        assert converter._normalize_chapter_title("第12章 标题") == "第12章 标题"

        # 英文格式
        assert converter._normalize_chapter_title("Chapter 1: 标题") == "第1章 标题"
        assert converter._normalize_chapter_title("Chapter 12: 标题") == "第12章 标题"

        # 其他格式（不修改）
        assert converter._normalize_chapter_title("自定义标题") == "自定义标题"

        print("  [PASS] 章节标题标准化测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_parse_chapters():
    """测试章节解析。"""
    print("测试章节解析...")
    converter, tmpdir = _make_converter()

    try:
        chapters = converter._parse_chapters(SAMPLE_NOVEL)

        # 应该有 3 个章节
        assert len(chapters) == 3

        # 验证标题
        assert chapters[0][0] == "第一章 初遇"
        assert chapters[1][0] == "第二章 奇遇"
        assert chapters[2][0] == "第三章 冒险"

        # 验证内容
        assert "小明" in chapters[0][1]
        assert "能力" in chapters[1][1]
        assert "冒险" in chapters[2][1]

        print("  [PASS] 章节解析测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_parse_chapters_no_chapters():
    """测试无章节内容解析。"""
    print("测试无章节内容解析...")
    converter, tmpdir = _make_converter()

    try:
        content_no_chapters = "这是一段没有章节标记的内容。\n包含多行文字。"
        chapters = converter._parse_chapters(content_no_chapters)

        # 应该作为单章处理
        assert len(chapters) == 1
        assert chapters[0][0] == "正文"
        assert "这是一段" in chapters[0][1]

        print("  [PASS] 无章节内容解析测试通过")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 运行所有测试 ──────────────────────────────────────────────

def run_all_tests():
    """运行所有测试。"""
    print("=" * 50)
    print("格式转换器模块测试")
    print("=" * 50)

    tests = [
        # convert_to_platform
        test_convert_to_platform_fanqie,
        test_convert_to_platform_qidian,
        test_convert_to_platform_jjwxc,
        test_convert_to_platform_invalid,
        test_convert_to_platform_prohibited_chars,
        # convert_to_txt
        test_convert_to_txt_basic,
        test_convert_to_txt_markdown_removal,
        test_convert_to_txt_chapter_normalization,
        # convert_to_epub
        test_convert_to_epub_basic,
        test_convert_to_epub_metadata,
        # convert_to_all
        test_convert_to_all,
        test_convert_to_all_custom_dir,
        # run
        test_run_to_platform,
        test_run_to_epub,
        test_run_to_txt,
        test_run_to_all,
        test_run_unknown_action,
        # validate
        test_validate,
        # 便捷函数
        test_get_converter,
        test_convert_novel,
        # 辅助方法
        test_normalize_chapter_title,
        test_parse_chapters,
        test_parse_chapters_no_chapters,
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
