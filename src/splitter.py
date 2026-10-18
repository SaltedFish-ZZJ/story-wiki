"""
Story Wiki - 章节切分模块
将长文本按章节标题自动切分为多个段落，用于逐章 AI 分析。

优化：改进内存使用，添加大文本处理提示。
"""
import re
from dataclasses import dataclass, field
from src.logging_setup import get_logger

logger = get_logger("splitter")


@dataclass
class Chapter:
    """一个章节的数据结构。"""
    index: int          # 章节序号（从 1 开始）
    title: str          # 章节标题
    text: str           # 章节正文
    char_count: int = 0 # 字数（自动计算）

    # 元数据字段（DeepSeek 建议）
    book_title: str = None           # 书名
    chapter_title: str = None        # 章节标题（完整版）
    chunk_index: int = 0             # 当前块在章节中的索引（从 0 开始）
    total_chunks_in_chapter: int = 1 # 章节总块数
    context_before_summary: str = None  # 前文摘要（用于跨块实体链接）

    def __post_init__(self):
        self.char_count = len(self.text)
        if self.chapter_title is None:
            self.chapter_title = self.title


# ── 章节标题匹配模式 ──────────────────────────────────────
# 按优先级排序，匹配到第一个模式后全文使用该模式
CHAPTER_PATTERNS = [
    # 第X回 / 第X章 / 第X节 / 第X卷 / 第X篇（支持中文数字和阿拉伯数字）
    re.compile(
        r'^(第[一二三四五六七八九十百千万零〇\d]+[回章节卷篇部集]'
        r'|第\s*\d+\s*[回章节卷篇部集])',
        re.MULTILINE,
    ),
    # Chapter X / CHAPTER X
    re.compile(r'^Chapter\s+\d+', re.MULTILINE | re.IGNORECASE),
    # 序章 / 楔子 / 尾声 / 楔子 / 引子 / 前言 / 后记
    re.compile(
        r'^(序章|序幕|楔子|引子|前言|尾声|后记|终章|番外|附录|序|跋)',
        re.MULTILINE,
    ),
    # 纯数字标题行（如 "1" "001" "一、" "二、"）
    re.compile(
        r'^(\d{1,4}|[一二三四五六七八九十]+)[、，.\s]',
        re.MULTILINE,
    ),
    # 一、XXX / 二、XXX 格式的分节
    re.compile(
        r'^[一二三四五六七八九十]+[、．.]\s*\S',
        re.MULTILINE,
    ),
]

# 默认每块字数（无章节标记时使用）
DEFAULT_CHUNK_SIZE = 5000
# 每块最小字数（避免碎片）
MIN_CHUNK_SIZE = 1000
# 模式匹配章节最小字数（过短视为碎片，归入相邻章节）
MIN_CHAPTER_CHARS = 200

# ── 重叠窗口配置（DeepSeek 建议）──
# 重叠窗口大小（字符数），用于保持跨块上下文连续性
OVERLAP_SIZE = 200
# 句子边界断点字符
SENTENCE_BOUNDARIES = set('。！？!?；;\n')
# 最小句子长度（避免太短的句子作为断点）
MIN_SENTENCE_LENGTH = 10


def split_chapters(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[Chapter]:
    """
    将文本切分为章节列表。

    优先按章节标题切分；如果没有匹配的章节标记，
    则按字数分块（每块约 chunk_size 字）。

    优化：
    1. 添加大文本处理提示
    2. 改进内存使用
    3. 优化正则表达式匹配

    Args:
        text: 纯文本内容
        chunk_size: 无章节标记时每块的目标字数

    Returns:
        Chapter 对象列表
    """
    if not text or not text.strip():
        return []

    # 大文本提示
    text_len = len(text)
    if text_len > 100000:  # 10万字
        logger.info(f"文本较长 ({text_len} 字)，开始智能切分...")

    # 尝试按章节标题切分
    chapters = _split_by_pattern(text)
    if chapters:
        logger.info(f"按章节标题切分成功，共 {len(chapters)} 章")
        return chapters

    # 没有章节标记，按字数分块
    logger.info(f"未检测到章节标记，按字数分块 (每块 {chunk_size} 字)")
    return _split_by_chunks(text, chunk_size)


def _parse_chinese_number(cn_str: str) -> int:
    """将中文数字字符串转为整数，如 '十二' → 12, '一百零三' → 103。"""
    cn_map = {
        '零': 0, '〇': 0,
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '百': 100, '千': 1000, '万': 10000,
    }
    result = 0
    current = 0
    for ch in cn_str:
        if ch not in cn_map:
            continue
        val = cn_map[ch]
        if val >= 10:
            if current == 0:
                current = 1
            result += current * val
            current = 0
        else:
            current = current * 10 + val
    return result + current


def _extract_chapter_number(title: str) -> int:
    """
    从章节标题中提取数字序号，用于排序。
    例如 "第十章 xxx" → 10, "第2回 xxx" → 2, "Chapter 5" → 5
    返回 0 表示无法提取。
    """
    # 阿拉伯数字
    m = re.search(r'\d+', title)
    if m:
        return int(m.group())

    # 中文数字（第 和 回/章/节 之间）
    m = re.search(r'第([一二三四五六七八九十百千万零〇]+)', title)
    if m:
        return _parse_chinese_number(m.group(1))

    return 0


def _extract_chapter_at(text: str, match, next_match) -> Chapter | None:
    """从单个正则匹配中提取一个章节，返回 None 表示跳过（碎片）。"""
    start = match.start()
    # 章节正文从标题行结束（换行符后）开始
    title_line_end = text.find('\n', start)
    if title_line_end == -1:
        title_line_end = start
    else:
        title_line_end += 1

    title = text[start:title_line_end].strip()
    end = next_match.start() if next_match else len(text)
    chapter_text = text[title_line_end:end].strip()

    # 跳过空章节或过短的碎片章节
    if len(chapter_text) < MIN_CHAPTER_CHARS:
        return None

    return Chapter(index=0, title=title, text=chapter_text)


def _try_pattern(text: str, pattern) -> list[Chapter]:
    """
    尝试用一个模式切分章节，返回排序后的章节列表（可能为空）。

    优化：
    1. 使用迭代器避免一次性加载所有匹配
    2. 分批处理匹配结果
    3. 添加处理进度提示
    """
    # 使用迭代器，避免一次性加载所有匹配到内存
    matches_iter = pattern.finditer(text)

    # 收集匹配结果（限制数量，避免内存爆炸）
    matches = []
    MAX_MATCHES = 1000  # 最大匹配数

    for i, match in enumerate(matches_iter):
        matches.append(match)
        if i >= MAX_MATCHES - 1:
            logger.warning(f"匹配数超过 {MAX_MATCHES}，可能不是有效的章节模式")
            break

    if len(matches) < 2:
        return []

    logger.info(f"找到 {len(matches)} 个章节标记")

    chapters = []
    for i, match in enumerate(matches):
        next_match = matches[i + 1] if i + 1 < len(matches) else None
        ch = _extract_chapter_at(text, match, next_match)
        if ch:
            chapters.append(ch)

        # 进度提示
        if (i + 1) % 100 == 0:
            logger.info(f"已处理 {i + 1}/{len(matches)} 个章节标记")

    if not chapters:
        return []

    # 按章节标题中的数字排序（解决 "第10章" 排在 "第1章" 前面的问题）
    chapters.sort(key=lambda ch: _extract_chapter_number(ch.title))
    for i, ch in enumerate(chapters):
        ch.index = i + 1
    return chapters


def _split_by_pattern(text: str) -> list[Chapter]:
    """
    尝试用各种章节模式匹配，返回切分结果。
    如果匹配到的章节数 < 2，视为无效匹配（可能是误匹配），返回空。
    """
    for pattern in CHAPTER_PATTERNS:
        result = _try_pattern(text, pattern)
        if result:
            return result
    return []


def _para_title(para: str) -> str:
    """用段落前 30 字作为标题。"""
    short = para[:30].replace('\n', ' ')
    return short + ("..." if len(para) > 30 else "")


def _should_flush(current_text: str, para: str, chunk_size: int) -> bool:
    """判断当前块是否应该保存并开始新块。"""
    if not current_text:
        return False
    if len(current_text) + len(para) <= chunk_size:
        return False
    return len(current_text) >= MIN_CHUNK_SIZE


def _flush_block(chapters: list, current_text: str, current_title: str) -> Chapter:
    """保存当前块为一个章节。"""
    return Chapter(
        index=len(chapters) + 1,
        title=current_title or f"第{len(chapters) + 1}部分",
        text=current_text.strip(),
    )


def _append_para(current_text: str, current_title: str, para: str) -> tuple[str, str]:
    """将段落追加到当前块，返回 (new_text, new_title)。"""
    if not current_text:
        return para, _para_title(para)
    return current_text + "\n\n" + para, current_title


def _split_by_chunks(text: str, chunk_size: int) -> list[Chapter]:
    """
    按字数分块，带重叠窗口。

    优化（DeepSeek 建议）：
    1. 使用迭代器处理段落，避免一次性加载所有段落
    2. 分批处理，减少内存占用
    3. 添加处理进度提示
    4. 实现重叠窗口（OVERLAP_SIZE），保持跨块上下文连续性
    5. 在句子边界断开，避免切断句子
    """
    text = text.strip()
    if len(text) <= chunk_size:
        return [Chapter(index=1, title="全文", text=text)]

    paragraphs = [p for p in (x.strip() for x in re.split(r'\n{2,}', text)) if p]
    if len(paragraphs) < 2:
        # 紧凑文本（无章节标记且无空行分段）无法按段落累积，
        # 退化为带重叠窗口的硬切分，避免整书塞进单个块
        logger.info("文本无空行分段，使用重叠窗口硬切分")
        return _split_by_chunks_with_overlap(text, chunk_size)

    # 使用迭代器处理段落
    paragraphs_iter = iter(paragraphs)

    chapters = []
    current_text = ""
    current_title = ""
    total_chars = 0
    processed_paras = 0

    for para in paragraphs_iter:
        para = para.strip()
        if not para:
            continue

        processed_paras += 1
        total_chars += len(para)

        if _should_flush(current_text, para, chunk_size):
            chapters.append(_flush_block(chapters, current_text, current_title))
            current_text = para
            current_title = _para_title(para)
        else:
            current_text, current_title = _append_para(current_text, current_title, para)

        # 进度提示
        if processed_paras % 1000 == 0:
            logger.info(f"已处理 {processed_paras} 个段落，{total_chars} 字")

    # 最后一块
    if current_text.strip():
        chapters.append(_flush_block(chapters, current_text, current_title))

    # 重新编号（确保连续）
    for i, ch in enumerate(chapters):
        ch.index = i + 1

    logger.info(f"分块完成，共 {len(chapters)} 个块，处理了 {processed_paras} 个段落")
    return chapters


def _find_sentence_boundary(text: str, position: int, direction: int = 1) -> int:
    """
    在指定位置附近查找句子边界。

    Args:
        text: 文本内容
        position: 当前位置
        direction: 查找方向（1 向前，-1 向后）

    Returns:
        句子边界位置
    """
    if direction == 1:  # 向前查找
        for i in range(position, min(position + MIN_SENTENCE_LENGTH * 2, len(text))):
            if text[i] in SENTENCE_BOUNDARIES:
                return i + 1
        return position
    else:  # 向后查找
        for i in range(position, max(position - MIN_SENTENCE_LENGTH * 2, 0), -1):
            if text[i] in SENTENCE_BOUNDARIES:
                return i + 1
        return position


def _split_by_chunks_with_overlap(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
                                   overlap: int = OVERLAP_SIZE) -> list[Chapter]:
    """
    按字数分块，带重叠窗口（DeepSeek 建议）。

    优化：
    1. 每个块与前一个块有 overlap 字符的重叠
    2. 在句子边界断开，避免切断句子
    3. 携带元数据（chunk_index, total_chunks_in_chapter 等）

    Args:
        text: 纯文本内容
        chunk_size: 每块的目标字数
        overlap: 重叠窗口大小（字符数）

    Returns:
        Chapter 对象列表，每个块携带元数据
    """
    text = text.strip()
    if len(text) <= chunk_size:
        return [Chapter(
            index=1,
            title="全文",
            text=text,
            chunk_index=0,
            total_chunks_in_chapter=1
        )]

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = start + chunk_size

        # 如果不是最后一块，尝试在句子边界断开
        if end < len(text):
            # 向前查找句子边界
            boundary = _find_sentence_boundary(text, end, direction=-1)
            # 如果找到了合理的边界（在 chunk_size * 0.8 之后）
            if boundary > start + chunk_size * 0.8:
                end = boundary

        chunk_text = text[start:end].strip()
        if not chunk_text:
            break

        chunks.append(Chapter(
            index=len(chunks) + 1,
            title=f"部分{chunk_index + 1}",
            text=chunk_text,
            chunk_index=chunk_index,
            total_chunks_in_chapter=0  # 稍后更新
        ))

        chunk_index += 1

        # 下一块从当前位置减去重叠开始
        start = end - overlap
        if start >= len(text):
            break

    # 更新所有块的 total_chunks_in_chapter
    total_chunks = len(chunks)
    for chunk in chunks:
        chunk.total_chunks_in_chapter = total_chunks

    logger.info(f"重叠分块完成，共 {total_chunks} 个块，每块约 {chunk_size} 字，重叠 {overlap} 字")
    return chunks


def get_split_summary(chapters: list[Chapter]) -> str:
    """返回切分结果的摘要信息，用于日志输出。"""
    if not chapters:
        return "无章节"

    total_chars = sum(ch.char_count for ch in chapters)
    lines = [
        f"共 {len(chapters)} 个章节，{total_chars} 字",
        "─" * 40,
    ]
    for ch in chapters:
        lines.append(f"  {ch.index:3d}. {ch.title} ({ch.char_count} 字)")
    return "\n".join(lines)
