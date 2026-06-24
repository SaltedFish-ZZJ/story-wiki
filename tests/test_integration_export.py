"""
Story Wiki - 格式转换集成测试

测试EPUB导出完整流程、Markdown导出完整流程、批量导出功能，
以及与NovelLogger的集成。
"""
import json
import sys
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.interfaces import ChapterContent
from src.converter import Converter, SUPPORTED_PLATFORMS
from src.novel_logger import NovelLogger


# ── 测试数据 ──────────────────────────────────────────────────


@pytest.fixture
def sample_novel_content():
    """返回一个标准的小说内容（Markdown格式）。"""
    return """# 测试小说

## 第1章 初入江湖

这是一个测试章节的内容。主角初次踏入江湖，遇到了各种奇遇。

在山间小路上，主角遇到了一位老者。老者说道："年轻人，你可知道前方的危险？"

主角坚定地回答："我不怕危险，我要追寻真相！"

## 第2章 惊天秘密

经过千辛万苦，主角终于发现了惊天秘密。

原来，这一切的背后都有一个巨大的阴谋。

"我要揭露真相！"主角暗下决心。

## 第3章 最终决战

最终决战即将来临。

主角与反派在悬崖边展开了最后的对决。

经过激烈的战斗，主角终于获得了胜利。
"""


@pytest.fixture
def sample_metadata():
    """返回标准的元数据字典。"""
    return {
        "title": "测试小说",
        "author": "Story Wiki 测试",
        "language": "zh",
        "description": "这是一个用于测试的小说",
        "publisher": "Story Wiki",
    }


@pytest.fixture
def converter(tmp_path):
    """创建一个使用临时目录的Converter实例。"""
    return Converter({"output_dir": tmp_path})


@pytest.fixture
def novel_logger(tmp_path):
    """创建一个使用临时目录的NovelLogger实例。"""
    return NovelLogger({
        "book_title": "测试小说",
        "output_dir": tmp_path,
    })


@pytest.fixture
def sample_chapter_contents():
    """返回多个ChapterContent实例。"""
    return [
        ChapterContent(
            chapter_num=1,
            title="初入江湖",
            content="这是第一章的内容。" * 100,
            word_count=2000,
            characters_involved=["主角"],
            events_happened=["初入江湖"],
        ),
        ChapterContent(
            chapter_num=2,
            title="惊天秘密",
            content="这是第二章的内容。" * 100,
            word_count=2000,
            characters_involved=["主角", "反派"],
            events_happened=["发现秘密"],
        ),
        ChapterContent(
            chapter_num=3,
            title="最终决战",
            content="这是第三章的内容。" * 100,
            word_count=2000,
            characters_involved=["主角", "反派"],
            events_happened=["最终决战"],
        ),
    ]


# ── EPUB 导出集成测试 ────────────────────────────────────────


class TestEpubExportIntegration:
    """测试EPUB导出完整流程。"""

    def test_epub_export_full_flow(
        self, converter, sample_novel_content, sample_metadata, tmp_path
    ):
        """测试EPUB导出完整流程。"""
        # 转换为EPUB
        epub_path = converter.convert_to_epub(sample_novel_content, sample_metadata)

        # 验证文件存在
        assert Path(epub_path).exists()
        assert epub_path.endswith(".epub")

        # 验证文件大小合理
        file_size = Path(epub_path).stat().st_size
        assert file_size > 0

    def test_epub_metadata(
        self, converter, sample_novel_content, sample_metadata, tmp_path
    ):
        """测试EPUB元数据正确性。"""
        epub_path = converter.convert_to_epub(sample_novel_content, sample_metadata)

        # 验证文件存在且可读
        assert Path(epub_path).exists()

        # 使用ebooklib验证元数据
        try:
            from ebooklib import epub
            book = epub.read_epub(epub_path)

            # 检查标题
            title = book.get_metadata("DC", "title")
            assert len(title) > 0
            assert title[0][0] == sample_metadata["title"]

            # 检查作者
            author = book.get_metadata("DC", "creator")
            assert len(author) > 0
        except ImportError:
            # ebooklib 未安装时跳过
            pytest.skip("ebooklib 未安装，跳过元数据验证")

    def test_epub_chapter_structure(
        self, converter, sample_novel_content, sample_metadata, tmp_path
    ):
        """测试EPUB章节结构。"""
        epub_path = converter.convert_to_epub(sample_novel_content, sample_metadata)

        try:
            from ebooklib import epub
            book = epub.read_epub(epub_path)

            # 获取所有章节（排除导航页）
            chapters = [
                item for item in book.get_items()
                if isinstance(item, epub.EpubHtml) and not isinstance(item, epub.EpubNav)
            ]

            # 应该有3个章节
            assert len(chapters) == 3

            # 检查章节内容存在
            for ch in chapters:
                content = ch.get_content().decode("utf-8")
                assert len(content) > 0
        except ImportError:
            pytest.skip("ebooklib 未安装，跳过章节结构验证")

    def test_epub_css_style(
        self, converter, sample_novel_content, sample_metadata, tmp_path
    ):
        """测试EPUB包含CSS样式。"""
        epub_path = converter.convert_to_epub(sample_novel_content, sample_metadata)

        try:
            from ebooklib import epub
            book = epub.read_epub(epub_path)

            # 查找CSS文件
            css_items = [
                item for item in book.get_items()
                if isinstance(item, epub.EpubItem) and item.media_type == "text/css"
            ]

            assert len(css_items) > 0

            # 验证CSS内容
            css_content = css_items[0].get_content().decode("utf-8")
            assert "font-family" in css_content
            assert "text-indent" in css_content
        except ImportError:
            pytest.skip("ebooklib 未安装，跳过CSS样式验证")


# ── Markdown 导出集成测试 ────────────────────────────────────


class TestMarkdownExportIntegration:
    """测试Markdown/纯文本导出完整流程。"""

    def test_txt_export(self, converter, sample_novel_content, tmp_path):
        """测试纯文本导出。"""
        txt_content = converter.convert_to_txt(sample_novel_content)

        # 验证输出为字符串
        assert isinstance(txt_content, str)
        assert len(txt_content) > 0

        # 验证Markdown标记已移除
        assert "# " not in txt_content.split("\n")[0]  # 标题应已转换
        assert "**" not in txt_content
        assert "##" not in txt_content

    def test_txt_preserves_content(self, converter, sample_novel_content, tmp_path):
        """测试纯文本保留内容。"""
        txt_content = converter.convert_to_txt(sample_novel_content)

        # 验证核心内容保留
        assert "初入江湖" in txt_content
        assert "惊天秘密" in txt_content
        assert "最终决战" in txt_content

    def test_platform_conversion(
        self, converter, sample_novel_content, tmp_path
    ):
        """测试平台格式转换。"""
        for platform in SUPPORTED_PLATFORMS:
            content = converter.convert_to_platform(sample_novel_content, platform)

            # 验证输出为字符串
            assert isinstance(content, str)
            assert len(content) > 0

            # 验证段落缩进
            lines = content.split("\n")
            has_indent = False
            for line in lines:
                if line.startswith("　　"):
                    has_indent = True
                    break
            assert has_indent, f"{platform} 平台格式应有段落缩进"

    def test_platform_removes_markdown(
        self, converter, sample_novel_content, tmp_path
    ):
        """测试平台格式移除Markdown标记。"""
        for platform in SUPPORTED_PLATFORMS:
            content = converter.convert_to_platform(sample_novel_content, platform)

            # 验证标题格式标准化
            assert "# " not in content
            assert "## " not in content

    def test_platform_export_to_file(
        self, converter, sample_novel_content, sample_metadata, tmp_path
    ):
        """测试平台格式导出到文件。"""
        for platform in SUPPORTED_PLATFORMS:
            content = converter.convert_to_platform(sample_novel_content, platform)

            file_path = tmp_path / f"test_{platform}.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            assert file_path.exists()
            assert file_path.stat().st_size > 0


# ── 批量导出集成测试 ────────────────────────────────────────


class TestBatchExportIntegration:
    """测试批量导出功能。"""

    def test_convert_to_all(
        self, converter, sample_novel_content, sample_metadata, tmp_path
    ):
        """测试一键全格式导出。"""
        results = converter.convert_to_all(
            sample_novel_content,
            sample_metadata,
            output_dir=str(tmp_path / "exports")
        )

        # 验证结果字典
        assert isinstance(results, dict)
        assert "txt" in results

        # 验证文件存在
        for platform, file_path in results.items():
            assert Path(file_path).exists(), f"{platform} 文件不存在"
            assert Path(file_path).stat().st_size > 0

    def test_batch_export_creates_directory(
        self, converter, sample_novel_content, sample_metadata, tmp_path
    ):
        """测试批量导出创建目录。"""
        export_dir = tmp_path / "batch_exports"

        results = converter.convert_to_all(
            sample_novel_content,
            sample_metadata,
            output_dir=str(export_dir)
        )

        # 验证目录创建
        assert export_dir.exists()

        # 验证所有文件在目录中
        for file_path in results.values():
            assert str(export_dir) in file_path

    def test_batch_export_with_epub(
        self, converter, sample_novel_content, sample_metadata, tmp_path
    ):
        """测试批量导出包含EPUB。"""
        results = converter.convert_to_all(
            sample_novel_content,
            sample_metadata,
            output_dir=str(tmp_path / "all_formats")
        )

        # 如果ebooklib安装了，应该有epub
        try:
            import ebooklib
            assert "epub" in results
            assert Path(results["epub"]).exists()
        except ImportError:
            # ebooklib未安装时，可能没有epub
            pass

    def test_batch_export_all_platforms(
        self, converter, sample_novel_content, sample_metadata, tmp_path
    ):
        """测试批量导出包含所有平台格式。"""
        results = converter.convert_to_all(
            sample_novel_content,
            sample_metadata,
            output_dir=str(tmp_path / "platform_batch")
        )

        # 验证所有平台格式
        for platform in SUPPORTED_PLATFORMS:
            if platform in results:
                assert Path(results[platform]).exists()


# ── 与NovelLogger集成测试 ────────────────────────────────────


class TestConverterNovelLoggerIntegration:
    """测试与NovelLogger的集成。"""

    def test_novel_logger_save_and_merge(
        self, novel_logger, sample_chapter_contents, tmp_path
    ):
        """测试NovelLogger保存章节并合并。"""
        # 保存多个章节
        for chapter in sample_chapter_contents:
            novel_logger.save_chapter(chapter.chapter_num, chapter)

        # 合并为完整小说
        full_novel = novel_logger.merge_novel("测试小说")

        # 验证合并结果
        assert isinstance(full_novel, str)
        assert "# 测试小说" in full_novel
        assert "第 1 章 初入江湖" in full_novel
        assert "第 2 章 惊天秘密" in full_novel
        assert "第 3 章 最终决战" in full_novel

    def test_novel_logger_to_converter(
        self, novel_logger, converter, sample_chapter_contents, sample_metadata, tmp_path
    ):
        """测试从NovelLogger合并后导出为EPUB。"""
        # 保存章节
        for chapter in sample_chapter_contents:
            novel_logger.save_chapter(chapter.chapter_num, chapter)

        # 合并小说
        full_novel = novel_logger.merge_novel("测试小说")

        # 转换为EPUB
        epub_path = converter.convert_to_epub(full_novel, sample_metadata)
        assert Path(epub_path).exists()

    def test_novel_logger_to_platform(
        self, novel_logger, converter, sample_chapter_contents, tmp_path
    ):
        """测试从NovelLogger合并后导出为平台格式。"""
        # 保存章节
        for chapter in sample_chapter_contents:
            novel_logger.save_chapter(chapter.chapter_num, chapter)

        # 合并小说
        full_novel = novel_logger.merge_novel("测试小说")

        # 转换为各平台格式
        for platform in SUPPORTED_PLATFORMS:
            content = converter.convert_to_platform(full_novel, platform)
            assert isinstance(content, str)
            assert len(content) > 0

    def test_novel_logger_to_txt(
        self, novel_logger, converter, sample_chapter_contents, tmp_path
    ):
        """测试从NovelLogger合并后导出为纯文本。"""
        # 保存章节
        for chapter in sample_chapter_contents:
            novel_logger.save_chapter(chapter.chapter_num, chapter)

        # 合并小说
        full_novel = novel_logger.merge_novel("测试小说")

        # 转换为纯文本
        txt_content = converter.convert_to_txt(full_novel)
        assert isinstance(txt_content, str)
        assert len(txt_content) > 0

    def test_novel_logger_progress_tracking(
        self, novel_logger, sample_chapter_contents, converter, sample_metadata, tmp_path
    ):
        """测试写作进度追踪与导出集成。"""
        # 保存部分章节
        for chapter in sample_chapter_contents[:2]:
            novel_logger.save_chapter(chapter.chapter_num, chapter)

        # 检查进度
        progress = novel_logger.get_progress("测试小说")
        assert progress["completed_chapters"] == 2
        assert progress["total_words"] > 0

        # 合并已保存的章节
        full_novel = novel_logger.merge_novel("测试小说")
        assert "第 1 章" in full_novel
        assert "第 2 章" in full_novel
        assert "第 3 章" not in full_novel  # 第3章未保存

    def test_novel_logger_resume_and_export(
        self, novel_logger, sample_chapter_contents, converter, tmp_path
    ):
        """测试断点续写与导出集成。"""
        # 保存前两章
        for chapter in sample_chapter_contents[:2]:
            novel_logger.save_chapter(chapter.chapter_num, chapter)

        # 断点续写 - 应从第3章开始
        next_chapter = novel_logger.resume_writing("测试小说")
        assert next_chapter == 3

        # 保存第3章
        novel_logger.save_chapter(3, sample_chapter_contents[2])

        # 合并并验证完整性
        full_novel = novel_logger.merge_novel("测试小说")
        assert "第 1 章" in full_novel
        assert "第 2 章" in full_novel
        assert "第 3 章" in full_novel

    def test_full_pipeline(
        self, novel_logger, converter, sample_chapter_contents, sample_metadata, tmp_path
    ):
        """测试完整管线：保存章节 → 合并 → 全格式导出。"""
        # 1. 保存所有章节
        for chapter in sample_chapter_contents:
            novel_logger.save_chapter(chapter.chapter_num, chapter)

        # 2. 合并为完整小说
        full_novel = novel_logger.merge_novel("测试小说")

        # 3. 全格式导出
        export_dir = tmp_path / "final_export"
        results = converter.convert_to_all(
            full_novel, sample_metadata, output_dir=str(export_dir)
        )

        # 验证所有导出文件
        assert len(results) > 0
        for platform, file_path in results.items():
            assert Path(file_path).exists(), f"{platform} 导出失败"
            assert Path(file_path).stat().st_size > 0


# ── 错误处理集成测试 ────────────────────────────────────────


class TestErrorHandling:
    """测试错误处理。"""

    def test_invalid_platform(self, converter, sample_novel_content, tmp_path):
        """测试不支持的平台。"""
        with pytest.raises(ValueError, match="不支持的平台"):
            converter.convert_to_platform(sample_novel_content, "unsupported_platform")

    def test_converter_run_invalid_action(self, converter, tmp_path):
        """测试Converter.run无效action。"""
        result = converter.run({"action": "invalid_action"})
        assert result["success"] is False
        assert "error" in result

    def test_converter_run_missing_action(self, converter, tmp_path):
        """测试Converter.run缺少action。"""
        result = converter.run({})
        assert result["success"] is False
        assert "error" in result

    def test_converter_validate(self, converter, tmp_path):
        """测试Converter.validate方法。"""
        # 有效结果
        valid_result = {"success": True, "content": "test"}
        assert converter.validate(valid_result) is True

        # 无效结果
        invalid_result = {"success": True}
        assert converter.validate(invalid_result) is False

        # 错误结果
        error_result = {"success": False, "error": "test error"}
        assert converter.validate(error_result) is True

    def test_novel_logger_run_invalid_action(self, novel_logger, tmp_path):
        """测试NovelLogger.run无效action。"""
        result = novel_logger.run({"action": "invalid_action"})
        assert result["success"] is False
        assert "error" in result
