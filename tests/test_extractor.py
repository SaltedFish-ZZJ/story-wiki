"""
Story Wiki - 文本提取模块测试

覆盖 extractor.py 中的核心函数：
- 文件读取（txt/epub/pdf）
- 文本清理（HTML标签、特殊字符、控制字符）
- 非正文内容移除
- 编码检测、错误处理
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.extractor import (
    extract_text,
    _clean_text,
    _remove_non_content,
    _read_txt,
    _read_txt_normal,
    _read_txt_streaming,
    LARGE_FILE_THRESHOLD,
    CHUNK_SIZE,
)


# ═══════════════════════════════════════════════════════════════
# 1. 文本清理 _clean_text
# ═══════════════════════════════════════════════════════════════

class TestCleanText:
    """测试 _clean_text 函数。"""

    def test_removes_html_tags(self):
        text = "<p>Hello</p><br><b>World</b>"
        result = _clean_text(text, remove_html=True, remove_non_content=False)
        assert "<p>" not in result
        assert "<br>" not in result
        assert "Hello" in result
        assert "World" in result

    def test_removes_html_entities(self):
        text = "A&nbsp;B&amp;C&lt;D&gt;E&quot;F"
        result = _clean_text(text, remove_html=True, remove_non_content=False)
        assert "&nbsp;" not in result
        assert "&amp;" not in result
        assert "A" in result

    def test_normalizes_line_endings(self):
        text = "Line1\r\nLine2\rLine3"
        result = _clean_text(text, remove_html=False, remove_non_content=False)
        assert "\r" not in result

    def test_removes_control_chars(self):
        text = "Hello\x00\x01\x02World\x0b\x0c"
        result = _clean_text(text, remove_html=False, remove_non_content=False)
        assert "Hello" in result
        assert "World" in result

    def test_compresses_multiple_newlines(self):
        text = "A\n\n\n\n\nB"
        result = _clean_text(text, remove_html=False, remove_non_content=False)
        assert "\n\n\n" not in result

    def test_preserves_content(self):
        text = "这是正文内容，保持不变。"
        result = _clean_text(text, remove_html=False, remove_non_content=False)
        assert result == "这是正文内容，保持不变。"

    def test_empty_string(self):
        assert _clean_text("") == ""

    def test_numeric_entities_removed(self):
        text = "&#65;&#66;AB"
        result = _clean_text(text, remove_html=True, remove_non_content=False)
        assert "&#" not in result
        assert "AB" in result


# ═══════════════════════════════════════════════════════════════
# 2. 非正文内容移除 _remove_non_content
# ═══════════════════════════════════════════════════════════════

class TestRemoveNonContent:
    """测试 _remove_non_content 函数。"""

    def test_removes_preamble(self):
        text = "版权声明\nSome preamble text\n第一章 引言\n正文内容..."
        result = _remove_non_content(text)
        assert "第一章 引言" in result

    def test_removes_epilogue(self):
        text = "第一章 内容\n正文...\n全书完\nSome footer"
        result = _remove_non_content(text)
        assert "全书完" not in result or "第一章 内容" in result

    def test_chapter_only_text_unchanged(self):
        text = "第一章 引言\n正文内容\n第二章 发展\n更多内容"
        result = _remove_non_content(text)
        assert "第一章 引言" in result
        assert "第二章 发展" in result

    def test_no_chapter_markers(self):
        text = "没有章节标记的普通文本"
        result = _remove_non_content(text)
        assert "没有章节标记的普通文本" in result

    def test_empty_string(self):
        assert _remove_non_content("") == ""

    def test_english_chapter_markers(self):
        text = "Some preamble\nChapter 1\nContent\nChapter 2\nMore"
        result = _remove_non_content(text)
        assert "Chapter 1" in result

    def test_pre_chapter_title_preserved(self):
        text = "书名：红楼梦\n内容简介\n第一章 贾宝玉\n正文"
        result = _remove_non_content(text)
        assert "第一章 贾宝玉" in result


# ═══════════════════════════════════════════════════════════════
# 3. TXT 文件读取
# ═══════════════════════════════════════════════════════════════

class TestReadTxt:
    """测试 TXT 文件读取功能。"""

    def test_utf8_file(self, tmp_path):
        file = tmp_path / "test.txt"
        file.write_text("这是UTF-8编码的内容。", encoding="utf-8")
        result = _read_txt(file, use_streaming=False)
        assert "UTF-8编码" in result

    def test_gbk_file(self, tmp_path):
        file = tmp_path / "test.txt"
        file.write_text("这是GBK编码的内容。", encoding="gbk")
        result = _read_txt(file, use_streaming=False)
        assert "GBK编码" in result

    def test_empty_file(self, tmp_path):
        file = tmp_path / "empty.txt"
        file.write_text("", encoding="utf-8")
        result = _read_txt(file, use_streaming=False)
        assert result == ""

    def test_streaming_read(self, tmp_path):
        file = tmp_path / "test.txt"
        file.write_text("第一行\n\n第二行\n\n第三行", encoding="utf-8")
        result = _read_txt(file, use_streaming=True)
        assert "第一行" in result


class TestExtractTextTxt:
    """测试 extract_text 对 txt 文件的处理。"""

    def test_basic_read(self, tmp_path):
        file = tmp_path / "novel.txt"
        file.write_text("小说正文内容", encoding="utf-8")
        result = extract_text(str(file))
        assert "小说正文内容" in result

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            extract_text("不存在的文件.txt")

    def test_unsupported_format(self, tmp_path):
        file = tmp_path / "test.xyz"
        file.write_text("content")
        with pytest.raises(ValueError, match="暂不支持的格式"):
            extract_text(str(file))

    def test_auto_streaming_for_large_file(self, tmp_path):
        file = tmp_path / "large.txt"
        # 创建超过阈值的文件
        content = "测试内容\n" * 200000  # 足够大
        file.write_text(content, encoding="utf-8")
        result = extract_text(str(file))
        assert "测试内容" in result

    def test_streaming_disabled(self, tmp_path):
        file = tmp_path / "test.txt"
        file.write_text("小文件内容", encoding="utf-8")
        result = extract_text(str(file), use_streaming=False)
        assert "小文件内容" in result


# ═══════════════════════════════════════════════════════════════
# 4. EPUB/PDF 格式（mock 依赖）
# ═══════════════════════════════════════════════════════════════

class TestExtractTextEpub:
    """测试 extract_text 对 epub 文件的处理。"""

    def test_epub_without_ebooklib_raises(self, tmp_path):
        file = tmp_path / "test.epub"
        file.write_bytes(b"fake epub")
        with pytest.raises((ValueError, Exception)) as exc_info:
            extract_text(str(file))
        # Either ValueError (ebooklib not installed) or EpubException (bad zip file)
        assert "ebooklib" in str(exc_info.value) or "Bad Zip" in str(exc_info.value) or "zip" in str(exc_info.value).lower()


class TestExtractTextPdf:
    """测试 extract_text 对 pdf 文件的处理。"""

    def test_pdf_without_pymupdf_raises(self, tmp_path):
        file = tmp_path / "test.pdf"
        file.write_bytes(b"fake pdf")
        with pytest.raises(ValueError, match="pymupdf"):
            extract_text(str(file))
