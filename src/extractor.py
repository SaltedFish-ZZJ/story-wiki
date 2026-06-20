"""
Story Wiki - 文本提取模块
负责读取各种格式的输入文件，返回纯文本字符串。
支持格式：.txt, .epub, .pdf
"""
from pathlib import Path


def extract_text(file_path: str) -> str:
    """
    读取文件，返回纯文本内容。

    Args:
        file_path: 文件路径（绝对或相对）

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

    return reader(path)


def _read_txt(path: Path) -> str:
    """
    读取 txt 文件，自动处理编码。
    尝试顺序：utf-8 → gbk → gb2312 → latin-1
    """
    encodings = ["utf-8", "gbk", "gb2312", "latin-1"]

    for enc in encodings:
        try:
            text = path.read_text(encoding=enc)
            return _clean_text(text)
        except (UnicodeDecodeError, UnicodeError):
            continue

    raise ValueError(f"无法识别文件编码: {path}")


def _read_epub(path: Path) -> str:
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
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        html_content = item.get_content().decode("utf-8", errors="replace")
        extractor = _HTMLTextExtractor()
        extractor.feed(html_content)
        text = extractor.get_text().strip()
        if text:
            parts.append(text)

    if not parts:
        raise ValueError("epub 文件中未提取到文本内容")

    return _clean_text("\n\n".join(parts))


def _read_pdf(path: Path) -> str:
    """
    读取 pdf 文件，逐页提取文本。
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        raise ValueError(
            "pdf 支持需要 pymupdf 库，请安装: pip install pymupdf"
        )

    doc = fitz.open(str(path))
    parts = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text()
        if text.strip():
            parts.append(text.strip())

    doc.close()

    if not parts:
        raise ValueError("pdf 文件中未提取到文本内容")

    return _clean_text("\n\n".join(parts))


def _clean_text(text: str) -> str:
    """基础文本清理。"""
    # 去除多余空行（保留单个换行）
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
    return "\n".join(cleaned).strip()
