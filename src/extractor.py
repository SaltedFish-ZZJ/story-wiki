"""
Story Wiki - 文本提取模块
负责读取各种格式的输入文件，返回纯文本字符串。
支持格式：.txt, .epub, .pdf

优化：支持大文件流式读取，减少内存占用。
"""
import os
from pathlib import Path
from src.config import LARGE_FILE_THRESHOLD, CHUNK_READ_SIZE as CHUNK_SIZE
from src.logging_setup import get_logger

logger = get_logger("extractor")


def extract_text(file_path: str, use_streaming: bool = None) -> str:
    """
    读取文件，返回纯文本内容。

    Args:
        file_path: 文件路径（绝对或相对）
        use_streaming: 是否使用流式读取（None 表示自动判断）

    Returns:
        清理后的纯文本字符串

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 格式不支持
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = path.suffix.lower()
    readers = {
        ".txt": _read_txt,
        ".epub": _read_epub,
        ".pdf": _read_pdf,
    }

    reader = readers.get(ext)
    if reader is None:
        supported = ", ".join(readers.keys())
        raise ValueError(f"暂不支持的格式: {ext}（支持: {supported}）")

    # 自动判断是否使用流式读取
    if use_streaming is None:
        file_size = path.stat().st_size
        use_streaming = file_size > LARGE_FILE_THRESHOLD
        if use_streaming:
            logger.info(f"检测到大文件 ({file_size / 1024 / 1024:.1f}MB)，启用流式读取")

    return reader(path, use_streaming=use_streaming)


def _read_txt(path: Path, use_streaming: bool = False) -> str:
    """
    读取 txt 文件，自动处理编码。
    尝试顺序：utf-8 → gbk → gb2312 → latin-1

    优化：支持流式读取大文件，减少内存占用。
    """
    encodings = ["utf-8", "gbk", "gb2312", "latin-1"]

    # 先检测编码
    detected_encoding = None
    for enc in encodings:
        try:
            # 尝试读取前 10KB 检测编码
            with open(path, 'r', encoding=enc) as f:
                f.read(10240)
            detected_encoding = enc
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if detected_encoding is None:
        raise ValueError(f"无法识别文件编码: {path}")

    # 根据文件大小选择读取方式
    if use_streaming:
        return _read_txt_streaming(path, detected_encoding)
    else:
        return _read_txt_normal(path, detected_encoding)


def _read_txt_normal(path: Path, encoding: str) -> str:
    """普通读取（适合小文件）。"""
    with open(path, 'r', encoding=encoding) as f:
        text = f.read()
    return _clean_text(text)


def _read_txt_streaming(path: Path, encoding: str) -> str:
    """
    流式读取（适合大文件）。

    优化策略：
    1. 分块读取文件
    2. 边读取边清理，避免同时保存原始文本和清理后文本
    3. 使用生成器逐块处理
    """
    logger.info(f"使用流式读取，分块大小: {CHUNK_SIZE // 1024}KB")

    # 使用 io 模块进行流式读取
    import io

    cleaned_lines = []
    prev_empty = False
    total_chars = 0

    with open(path, 'r', encoding=encoding, buffering=CHUNK_SIZE) as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                if not prev_empty:
                    cleaned_lines.append("")
                    prev_empty = True
            else:
                cleaned_lines.append(stripped)
                prev_empty = False
                total_chars += len(stripped)

    # 定期打印进度
    logger.info(f"流式读取完成，共 {total_chars} 字")

    return "\n".join(cleaned_lines).strip()


def _read_epub(path: Path, use_streaming: bool = False) -> str:
    """
    读取 epub 文件，按章节顺序提取纯文本。
    epub 天然有章节结构，可直接按章节分析。
    """
    try:
        import ebooklib
        from ebooklib import epub
        from html.parser import HTMLParser
    except ImportError:
        raise ValueError(
            "epub 支持需要 ebooklib 库，请安装: pip install ebooklib"
        )

    class _HTMLTextExtractor(HTMLParser):
        """简单的 HTML → 纯文本提取器。"""
        def __init__(self):
            super().__init__()
            self._text = []
            self._skip = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag in ("script", "style"):
                self._skip = False
            if tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
                self._text.append("\n")

        def handle_data(self, data):
            if not self._skip:
                self._text.append(data)

        def get_text(self):
            return "".join(self._text)

    book = epub.read_epub(str(path), options={"ignore_ncx": True})

    # 按 spine 顺序读取所有章节
    parts = []
    total_chars = 0
    for i, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        html_content = item.get_content().decode("utf-8", errors="replace")
        extractor = _HTMLTextExtractor()
        extractor.feed(html_content)
        text = extractor.get_text().strip()
        if text:
            parts.append(text)
            total_chars += len(text)

        # 大文件进度提示
        if use_streaming and (i + 1) % 10 == 0:
            logger.info(f"已处理 {i + 1} 个章节，共 {total_chars} 字")

    if not parts:
        raise ValueError("epub 文件中未提取到文本内容")

    logger.info(f"epub 读取完成，共 {len(parts)} 个章节，{total_chars} 字")
    return _clean_text("\n\n".join(parts))


def _read_pdf(path: Path, use_streaming: bool = False) -> str:
    """
    读取 pdf 文件，逐页提取文本。
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        raise ValueError(
            "pdf 支持需要 pymupdf 库，请安装: pip install pymupdf"
        )

    try:
        doc = fitz.open(str(path))
    except (RuntimeError, ValueError) as exc:
        raise ValueError(f"无法读取 pdf 文件，文件可能已损坏或格式不受支持: {path}") from exc
    parts = []
    total_chars = 0
    total_pages = len(doc)

    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        text = page.get_text()
        if text.strip():
            parts.append(text.strip())
            total_chars += len(text.strip())

        # 大文件进度提示
        if use_streaming and (page_num + 1) % 50 == 0:
            logger.info(f"已处理 {page_num + 1}/{total_pages} 页，共 {total_chars} 字")

    doc.close()

    if not parts:
        raise ValueError("pdf 文件中未提取到文本内容")

    logger.info(f"pdf 读取完成，共 {total_pages} 页，{total_chars} 字")
    return _clean_text("\n\n".join(parts))


def _clean_text(text: str, remove_html: bool = True, remove_non_content: bool = True) -> str:
    """
    文本清理（DeepSeek 建议增强）。

    优化：
    1. 清理 HTML 标签（支持网页复制内容）
    2. 清理特殊字符（&nbsp;、\r 等）
    3. 识别并移除非正文内容（卷首/卷尾）
    4. 统一换行格式
    """
    import re

    # 1. 清理 HTML 标签（DeepSeek 建议）
    if remove_html:
        # 移除 HTML 标签
        text = re.sub(r'<[^>]*>', '', text)
        # 移除 HTML 实体
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'&#\d+;', '', text)

    # 2. 清理特殊字符
    text = text.replace('\r\n', '\n')  # 统一换行
    text = text.replace('\r', '\n')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)  # 移除控制字符

    # 3. 统一换行（多个连续换行压缩为两个）
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 4. 去除多余空行（保留单个换行）
    lines = text.splitlines()
    cleaned = []
    prev_empty = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not prev_empty:
                cleaned.append("")
                prev_empty = True
        else:
            cleaned.append(stripped)
            prev_empty = False

    text = "\n".join(cleaned).strip()

    # 5. 识别并移除非正文内容（DeepSeek 建议）
    if remove_non_content:
        text = _remove_non_content(text)

    return text


def _remove_non_content(text: str) -> str:
    """
    移除非正文内容（卷首/卷尾）。

    DeepSeek 建议：去掉书籍开头/结尾的非正文内容（如版权声明、注释），
    可通过识别"第*回""Chapter"等关键词判断正文起点。
    """
    import re

    # 查找正文起点（第一个"第X回"或"第X章"）
    content_start_patterns = [
        r'第[一二三四五六七八九十百千\d]+[回章节]',
        r'Chapter\s+\d+',
        r'序章|序幕|楔子|引子|前言',
    ]

    content_start = 0
    for pattern in content_start_patterns:
        match = re.search(pattern, text)
        if match:
            # 找到正文起点，但保留前面的标题行
            # 向前查找行首
            line_start = text.rfind('\n', 0, match.start())
            if line_start == -1:
                line_start = 0
            else:
                line_start += 1
            content_start = line_start
            break

    # 查找正文终点（最后一个"第X回"或"第X章"之后的内容）
    content_end = len(text)
    for pattern in content_start_patterns:
        matches = list(re.finditer(pattern, text))
        if matches:
            # 找到最后一个章节标记
            last_match = matches[-1]
            # 找到该章节的结束位置（下一个章节标记或文本末尾）
            next_line = text.find('\n', last_match.end())
            if next_line == -1:
                content_end = len(text)
            else:
                # 保留该章节内容，但移除后面的非正文
                # 查找可能的结束标记
                end_patterns = [
                    r'全书完|完结|终|完本|大结局',
                    r'THE END|The End|END',
                    r'版权|版权所有|Copyright',
                ]
                for end_pattern in end_patterns:
                    end_match = re.search(end_pattern, text[next_line:], re.IGNORECASE)
                    if end_match:
                        content_end = next_line + end_match.start()
                        break
            break

    if content_start > 0 or content_end < len(text):
        logger.info(f"移除非正文内容：前 {content_start} 字，后 {len(text) - content_end} 字")
        text = text[content_start:content_end].strip()

    return text
