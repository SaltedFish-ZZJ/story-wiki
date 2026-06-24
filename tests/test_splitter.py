"""
Story Wiki - 章节切分模块测试

覆盖 splitter.py 中的核心函数：
- 中文数字解析、章节数字提取
- 章节切分、分块模式（含重叠窗口）
- 句子边界断点
"""
import pytest

from src.splitter import (
    _parse_chinese_number,
    _extract_chapter_number,
    _split_by_chunks_with_overlap,
    _find_sentence_boundary,
    split_chapters,
    get_split_summary,
    Chapter,
    OVERLAP_SIZE,
    DEFAULT_CHUNK_SIZE,
    MIN_CHUNK_SIZE,
)


# ═══════════════════════════════════════════════════════════════
# 1. 中文数字解析
# ═══════════════════════════════════════════════════════════════

class TestParseChineseNumber:
    """测试 _parse_chinese_number 函数。"""

    def test_basic_numbers(self):
        assert _parse_chinese_number("零") == 0
        assert _parse_chinese_number("一") == 1
        assert _parse_chinese_number("十") == 10
        assert _parse_chinese_number("二十") == 20
        assert _parse_chinese_number("三十五") == 35
        assert _parse_chinese_number("一百") == 100

    def test_complex_numbers(self):
        assert _parse_chinese_number("一百二十三") == 123
        assert _parse_chinese_number("二百五十六") == 256
        assert _parse_chinese_number("一千零一") == 1001

    def test_empty_string_returns_zero(self):
        assert _parse_chinese_number("") == 0

    def test_unknown_chars_skipped(self):
        # 未知字符被跳过，只计算中文数字
        assert _parse_chinese_number("abc") == 0
        assert _parse_chinese_number("十abc") == 10


# ═══════════════════════════════════════════════════════════════
# 2. 章节数字提取
# ═══════════════════════════════════════════════════════════════

class TestExtractChapterNumber:
    """测试 _extract_chapter_number 函数。"""

    def test_chinese_number(self):
        assert _extract_chapter_number("第一章 贾宝玉") == 1
        assert _extract_chapter_number("第二十回 林黛玉") == 20

    def test_arabic_number(self):
        assert _extract_chapter_number("Chapter 1") == 1
        assert _extract_chapter_number("Chapter 20") == 20

    def test_no_number_returns_zero(self):
        assert _extract_chapter_number("序章") == 0

    def test_empty_returns_zero(self):
        assert _extract_chapter_number("") == 0


# ═══════════════════════════════════════════════════════════════
# 3. 章节切分
# ═══════════════════════════════════════════════════════════════

class TestSplitChapters:
    """测试 split_chapters 函数。"""

    def test_chapter_pattern_split(self):
        # 需要至少 2 个匹配且正文 ≥ MIN_CHAPTER_CHARS 才会按章节切分
        body = "正文内容" * 60  # 240字 > MIN_CHAPTER_CHARS(200)
        text = f"第一章 引言\n{body}\n第二章 发展\n{body}"
        chapters = split_chapters(text)
        assert len(chapters) == 2
        assert chapters[0].index == 1
        assert chapters[1].index == 2

    def test_no_pattern_falls_back_to_chunks(self):
        text = "这是没有章节标记的文本。"
        chapters = split_chapters(text)
        assert len(chapters) == 1

    def test_short_text_returns_single(self):
        text = "短文本"
        chapters = split_chapters(text)
        assert len(chapters) == 1
        assert chapters[0].title == "全文"

    def test_empty_text_returns_empty(self):
        assert split_chapters("") == []
        assert split_chapters("   ") == []

    def test_char_count_auto_computed(self):
        text = "AB测试"
        chapters = split_chapters(text)
        assert chapters[0].char_count == len("AB测试")

    def test_chapter_title_auto_set(self):
        text = "AB测试"
        chapters = split_chapters(text)
        assert chapters[0].chapter_title == "全文"

    def test_custom_chunk_size(self):
        # _split_by_chunks 先按 \n\n 分段，每段需 >= MIN_CHUNK_SIZE 才会 flush
        # 用分段文本确保分段逻辑触发
        paragraph = "这是测试段落内容" * 30  # ~270字
        text = "\n\n".join([paragraph] * 20)  # 20段，每段270字
        chapters = split_chapters(text, chunk_size=400)
        assert len(chapters) > 1


# ═══════════════════════════════════════════════════════════════
# 4. 重叠分块
# ═══════════════════════════════════════════════════════════════

class TestSplitByChunksWithOverlap:
    """测试 _split_by_chunks_with_overlap 函数。"""

    def test_basic_split(self):
        text = "这是一个测试文本" * 200  # 较长文本
        chunks = _split_by_chunks_with_overlap(text, chunk_size=500, overlap=50)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.chunk_index >= 0
            assert chunk.total_chunks_in_chapter == len(chunks)

    def test_short_text_single_chunk(self):
        text = "短文本"
        chunks = _split_by_chunks_with_overlap(text, chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks_in_chapter == 1

    def test_overlap_between_chunks(self):
        # 创建可预测的文本
        text = "A" * 100 + "B" * 100 + "C" * 100
        chunks = _split_by_chunks_with_overlap(text, chunk_size=120, overlap=30)
        assert len(chunks) >= 2

    def test_default_overlap(self):
        text = "内容" * 3000
        chunks = _split_by_chunks_with_overlap(text, chunk_size=1000)
        assert len(chunks) > 1

    def test_metadata_fields(self):
        text = "内容" * 3000
        chunks = _split_by_chunks_with_overlap(text, chunk_size=1000, overlap=100)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.total_chunks_in_chapter == len(chunks)

    def test_empty_returns_single_empty(self):
        # 函数不会过滤空文本，会返回一个空章节
        chunks = _split_by_chunks_with_overlap("")
        assert len(chunks) == 1
        assert chunks[0].text == ""


# ═══════════════════════════════════════════════════════════════
# 5. 句子边界断点
# ═══════════════════════════════════════════════════════════════

class TestFindSentenceBoundary:
    """测试 _find_sentence_boundary 函数。"""

    def test_chinese_period(self):
        text = "这是第一句话。这是第二句话。"
        boundary = _find_sentence_boundary(text, 10, direction=-1)
        # 应该在 "。" 之后
        assert text[boundary - 1] == "。"

    def test_english_period(self):
        text = "First sentence. Second sentence."
        boundary = _find_sentence_boundary(text, 15, direction=-1)
        assert text[boundary - 1] == "."

    def test_exclamation_mark(self):
        text = "好厉害！真了不起"
        boundary = _find_sentence_boundary(text, 4, direction=-1)
        assert text[boundary - 1] == "！"

    def test_no_boundary_returns_position(self):
        text = "无句号的短文本"
        boundary = _find_sentence_boundary(text, 3, direction=-1)
        assert boundary == 3

    def test_direction_forward(self):
        text = "前面的内容。后面的内容。"
        boundary = _find_sentence_boundary(text, 5, direction=1)
        # 应该找到第一个 "。" + 1
        assert boundary > 5

    def test_newline_as_boundary(self):
        text = "第一行\n第二行"
        boundary = _find_sentence_boundary(text, 5, direction=-1)
        assert text[boundary - 1] == "\n"


# ═══════════════════════════════════════════════════════════════
# 6. Chapter 数据类
# ═══════════════════════════════════════════════════════════════

class TestChapterDataclass:
    """测试 Chapter 数据类。"""

    def test_creation(self):
        chapter = Chapter(index=1, title="第一章", text="正文内容")
        assert chapter.index == 1
        assert chapter.title == "第一章"
        assert chapter.text == "正文内容"
        assert chapter.char_count == 4  # __post_init__ 自动计算

    def test_post_init_sets_char_count(self):
        chapter = Chapter(index=1, title="t", text="这是一段测试文本")
        assert chapter.char_count == len("这是一段测试文本")

    def test_post_init_sets_chapter_title(self):
        chapter = Chapter(index=1, title="我的章节", text="内容")
        assert chapter.chapter_title == "我的章节"

    def test_preserves_explicit_chapter_title(self):
        chapter = Chapter(index=1, title="t", text="内容", chapter_title="完整标题")
        assert chapter.chapter_title == "完整标题"

    def test_metadata_fields(self):
        chapter = Chapter(
            index=1, title="t", text="内容",
            book_title="红楼梦", chunk_index=2,
            total_chunks_in_chapter=5,
        )
        assert chapter.book_title == "红楼梦"
        assert chapter.chunk_index == 2
        assert chapter.total_chunks_in_chapter == 5


# ═══════════════════════════════════════════════════════════════
# 7. 切分摘要
# ═══════════════════════════════════════════════════════════════

class TestGetSplitSummary:
    """测试 get_split_summary 函数。"""

    def test_empty_chapters(self):
        assert get_split_summary([]) == "无章节"

    def test_basic_summary(self):
        chapters = [
            Chapter(index=1, title="第一章", text="内容一"),
            Chapter(index=2, title="第二章", text="内容二"),
        ]
        summary = get_split_summary(chapters)
        assert "2 个章节" in summary
        assert "第一章" in summary
        assert "第二章" in summary

    def test_total_chars(self):
        chapters = [Chapter(index=1, title="t", text="ABCD")]
        summary = get_split_summary(chapters)
        assert "4" in summary  # 字数
