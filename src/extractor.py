"""
Story Wiki - 文本提取模块
负责读取各种格式的输入文件，返回纯文本字符串。
Demo 阶段只支持 .txt。
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

    if ext == ".txt":
        return _read_txt(path)
    else:
        raise ValueError(f"暂不支持的格式: {ext}（Demo 阶段仅支持 .txt）")


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
