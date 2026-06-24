"""
Story Wiki - 格式转换器模块
将生成的小说转换为多平台格式（番茄/起点/晋江）、EPUB 和纯文本。

实现 ConverterInterface 接口。
"""
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.interfaces import ConverterInterface, ChapterContent
from src.config import CREATE_OUTPUT_DIR as EXPORT_DIR
from src.utils import safe_filename as _safe_filename


# ── 平台格式规则 ──
PLATFORM_RULES = {
    "fanqie": {
        "name": "番茄小说",
        "paragraph_indent": "　　",  # 两个全角空格
        "title_format": "第{num}章 {title}",
        "prohibited_chars": ["**", "##", "```", "[[", "]]"],
        "line_spacing": "\n",
    },
    "qidian": {
        "name": "起点中文网",
        "paragraph_indent": "　　",
        "title_format": "第{num}章 {title}",
        "prohibited_chars": [],
        "line_spacing": "\n",
    },
    "jjwxc": {
        "name": "晋江文学城",
        "paragraph_indent": "　　",
        "title_format": "第{num}章 {title}",
        "prohibited_chars": [],
        "line_spacing": "\n",
    },
}

SUPPORTED_PLATFORMS = list(PLATFORM_RULES.keys())


class Converter(ConverterInterface):
    """
    格式转换器：将小说内容转换为多平台格式、EPUB 和纯文本。

    文件结构：
        data/novels/{safe_title}/exports/
            {title}_fanqie.txt
            {title}_qidian.txt
            {title}_jjwxc.txt
            {title}.epub
            {title}.txt
    """

    def __init__(self, config: dict):
        """
        初始化转换器。

        Args:
            config: 配置字典，可选键：
                - output_dir (str|Path): 输出目录
        """
        self.config = config
        raw_dir = config.get("output_dir", EXPORT_DIR)
        self.output_dir = Path(raw_dir) if raw_dir else EXPORT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, input_data: dict) -> dict:
        """
        运行格式转换。

        支持的 action：
            - to_platform: 转换为平台格式
            - to_epub: 转换为 EPUB
            - to_txt: 转换为纯文本
            - to_all: 全格式导出

        Args:
            input_data: 输入数据，必须包含 "action" 键

        Returns:
            操作结果字典
        """
        if not isinstance(input_data, dict):
            return {"success": False, "error": "input_data 必须是 dict"}

        action = input_data.get("action")
        if not action:
            return {"success": False, "error": "缺少 action 字段"}

        try:
            if action == "to_platform":
                content = input_data["content"]
                platform = input_data["platform"]
                result = self.convert_to_platform(content, platform)
                return {"success": True, "content": result, "platform": platform}

            elif action == "to_epub":
                content = input_data["content"]
                metadata = input_data.get("metadata", {})
                result = self.convert_to_epub(content, metadata)
                return {"success": True, "path": result}

            elif action == "to_txt":
                content = input_data["content"]
                result = self.convert_to_txt(content)
                return {"success": True, "content": result}

            elif action == "to_all":
                content = input_data["content"]
                metadata = input_data.get("metadata", {})
                output_dir = input_data.get("output_dir")
                result = self.convert_to_all(content, metadata, output_dir)
                return {"success": True, "files": result}

            else:
                return {"success": False, "error": f"未知 action: {action}"}

        except (KeyError, TypeError) as e:
            return {"success": False, "error": f"参数错误: {e}"}
        except Exception as e:
            return {"success": False, "error": f"转换失败: {e}"}

    def validate(self, output_data: dict) -> bool:
        """验证输出数据是否合法。"""
        if not isinstance(output_data, dict):
            return False
        if "success" not in output_data:
            return False
        if output_data["success"] and ("content" in output_data or "path" in output_data or "files" in output_data):
            return True
        if not output_data["success"] and "error" in output_data:
            return True
        return False

    # ── 核心接口实现 ────────────────────────────────────────────

    def convert_to_platform(
        self,
        novel_content: str,
        platform: str
    ) -> str:
        """
        转换为平台格式。

        Args:
            novel_content: 小说内容（支持 Markdown 格式）
            platform: 目标平台（fanqie/qidian/jjwxc）

        Returns:
            转换后的内容
        """
        if platform not in PLATFORM_RULES:
            raise ValueError(f"不支持的平台: {platform}，支持的平台: {SUPPORTED_PLATFORMS}")

        rules = PLATFORM_RULES[platform]
        lines = novel_content.split("\n")
        result_lines = []
        in_title = False

        for line in lines:
            stripped = line.strip()

            # 跳过空行（保留段落间空行）
            if not stripped:
                result_lines.append("")
                in_title = False
                continue

            # 处理 Markdown 标题
            if stripped.startswith("# "):
                # 书籍标题行，不添加缩进
                title_text = stripped[2:].strip()
                result_lines.append(title_text)
                in_title = True
                continue

            if stripped.startswith("## "):
                # 章节标题，不添加缩进
                title_text = stripped[3:].strip()
                # 标准化章节标题格式
                title_text = self._normalize_chapter_title(title_text)
                result_lines.append(title_text)
                in_title = True
                continue

            # 处理段落（添加缩进）
            if in_title:
                in_title = False

            if stripped:
                # 非空行，添加缩进
                result_lines.append(rules["paragraph_indent"] + stripped)
            else:
                result_lines.append(stripped)

        # 过滤禁用字符
        content = "\n".join(result_lines)
        for char in rules.get("prohibited_chars", []):
            content = content.replace(char, "")

        return content

    def convert_to_epub(
        self,
        novel_content: str,
        metadata: dict
    ) -> str:
        """
        转换为 EPUB 格式。

        Args:
            novel_content: 小说内容（支持 Markdown 格式）
            metadata: 元数据，可选键：
                - title (str): 书名
                - author (str): 作者
                - language (str): 语言
                - description (str): 简介

        Returns:
            EPUB 文件路径
        """
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            raise ImportError("EPUB 生成需要 ebooklib 库，请运行: pip install ebooklib")

        title = metadata.get("title", "未命名作品")
        author = metadata.get("author", "Story Wiki")
        language = metadata.get("language", "zh")
        description = metadata.get("description", "")

        # 创建 EPUB 书籍
        book = epub.EpubBook()
        book.set_identifier(f"story-wiki-{_safe_filename(title)}")
        book.set_title(title)
        book.set_language(language)
        book.add_author(author)

        if description:
            book.add_metadata("DC", "description", description)

        # 解析章节内容
        chapters = self._parse_chapters(novel_content)

        # 添加章节
        epub_chapters = []
        toc = []

        for i, (ch_title, ch_content) in enumerate(chapters):
            chapter = epub.EpubHtml(
                title=ch_title,
                file_name=f"chapter_{i+1}.xhtml",
                lang=language,
            )
            # 将内容转换为 HTML
            html_content = self._content_to_html(ch_title, ch_content)
            chapter.content = html_content.encode("utf-8")
            book.add_item(chapter)
            epub_chapters.append(chapter)
            toc.append(chapter)

        # 设置目录
        book.toc = toc

        # 添加导航文件
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # 设置书脊
        book.spine = ["nav"] + epub_chapters

        # 生成文件名
        safe_title = _safe_filename(title)
        epub_path = self.output_dir / f"{safe_title}.epub"

        # 写入文件
        epub.write_epub(str(epub_path), book, {})

        print(f"[Converter] EPUB 已生成: {epub_path}")
        return str(epub_path)

    def convert_to_txt(
        self,
        novel_content: str
    ) -> str:
        """
        转换为纯文本格式（去除 Markdown 标记）。

        Args:
            novel_content: 小说内容（支持 Markdown 格式）

        Returns:
            纯文本内容
        """
        lines = novel_content.split("\n")
        result_lines = []

        for line in lines:
            stripped = line.strip()

            # 跳过空行
            if not stripped:
                result_lines.append("")
                continue

            # 处理标题
            if stripped.startswith("# "):
                # 书籍标题
                result_lines.append(stripped[2:].strip())
                result_lines.append("")
                continue

            if stripped.startswith("## "):
                # 章节标题
                title_text = stripped[3:].strip()
                result_lines.append("")
                result_lines.append(self._normalize_chapter_title(title_text))
                result_lines.append("")
                continue

            # 处理其他 Markdown 标记
            # 去除加粗、斜体等
            text = stripped
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **加粗**
            text = re.sub(r'\*(.*?)\*', r'\1', text)  # *斜体*
            text = re.sub(r'~~(.*?)~~', r'\1', text)  # ~~删除线~~
            text = re.sub(r'`(.*?)`', r'\1', text)  # `代码`

            result_lines.append("　　" + text if text else "")

        return "\n".join(result_lines)

    def convert_to_all(
        self,
        novel_content: str,
        metadata: dict,
        output_dir: Optional[str] = None
    ) -> Dict[str, str]:
        """
        一键全格式导出。

        Args:
            novel_content: 小说内容
            metadata: 元数据
            output_dir: 输出目录（可选，默认使用初始化时的目录）

        Returns:
            {
                "fanqie": 文件路径,
                "qidian": 文件路径,
                "jjwxc": 文件路径,
                "epub": 文件路径,
                "txt": 文件路径
            }
        """
        title = metadata.get("title", "未命名作品")
        safe_title = _safe_filename(title)

        # 确定输出目录
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.output_dir / safe_title / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        # 平台格式
        for platform in SUPPORTED_PLATFORMS:
            try:
                content = self.convert_to_platform(novel_content, platform)
                file_path = out_dir / f"{safe_title}_{platform}.txt"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                results[platform] = str(file_path)
                print(f"[Converter] {PLATFORM_RULES[platform]['name']} 格式已导出: {file_path}")
            except Exception as e:
                print(f"[Converter] {PLATFORM_RULES[platform]['name']} 导出失败: {e}")

        # EPUB 格式
        try:
            epub_metadata = {**metadata, "title": title}
            epub_path = self.convert_to_epub(novel_content, epub_metadata)
            # 移动到导出目录
            import shutil
            dest = out_dir / f"{safe_title}.epub"
            shutil.move(epub_path, dest)
            results["epub"] = str(dest)
        except Exception as e:
            print(f"[Converter] EPUB 导出失败: {e}")

        # TXT 格式
        try:
            content = self.convert_to_txt(novel_content)
            file_path = out_dir / f"{safe_title}.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            results["txt"] = str(file_path)
            print(f"[Converter] TXT 格式已导出: {file_path}")
        except Exception as e:
            print(f"[Converter] TXT 导出失败: {e}")

        return results

    # ── 辅助方法 ────────────────────────────────────────────────

    def _normalize_chapter_title(self, title: str) -> str:
        """
        标准化章节标题格式。

        支持格式：
            - 第1章 标题
            - 第一章 标题
            - Chapter 1: 标题
        """
        # 第1章 标题 -> 第1章 标题
        match = re.match(r'第([一二三四五六七八九十百千\d]+)章\s*(.*)', title)
        if match:
            num = match.group(1)
            text = match.group(2).strip()
            return f"第{num}章 {text}"

        # Chapter 1: 标题 -> 第1章 标题
        match = re.match(r'Chapter\s+(\d+)\s*[:：]\s*(.*)', title, re.IGNORECASE)
        if match:
            num = match.group(1)
            text = match.group(2).strip()
            return f"第{num}章 {text}"

        return title

    def _parse_chapters(self, novel_content: str) -> List[tuple]:
        """
        解析小说内容为章节列表。

        Returns:
            [(标题, 内容), ...]
        """
        lines = novel_content.split("\n")
        chapters = []
        current_title = ""
        current_content = []

        for line in lines:
            stripped = line.strip()

            # 检测章节标题
            if stripped.startswith("## "):
                # 保存上一章
                if current_title:
                    chapters.append((current_title, "\n".join(current_content)))
                current_title = stripped[3:].strip()
                current_content = []
            elif stripped.startswith("# ") and not current_title:
                # 书籍标题，跳过
                continue
            else:
                if stripped:
                    current_content.append(line)

        # 保存最后一章
        if current_title:
            chapters.append((current_title, "\n".join(current_content)))

        # 如果没有检测到章节，作为单章处理
        if not chapters:
            chapters.append(("正文", novel_content))

        return chapters

    def _content_to_html(self, title: str, content: str) -> str:
        """将纯文本内容转换为 HTML。"""
        html_parts = [f"<h1>{title}</h1>"]

        for line in content.split("\n"):
            stripped = line.strip()
            if not stripped:
                html_parts.append("<br/>")
                continue
            # 添加段落缩进
            html_parts.append(f"<p>　　{stripped}</p>")

        return "\n".join(html_parts)


# ── 便捷函数 ──────────────────────────────────────────────────

def get_converter(config: Optional[dict] = None) -> Converter:
    """获取转换器实例。"""
    return Converter(config or {})


def convert_novel(
    novel_content: str,
    platform: str,
    output_path: Optional[str] = None
) -> str:
    """
    便捷函数：将小说转换为指定平台格式并保存。

    Args:
        novel_content: 小说内容
        platform: 目标平台
        output_path: 输出路径（可选）

    Returns:
        保存的文件路径
    """
    converter = Converter({"output_dir": Path(output_path).parent if output_path else EXPORT_DIR})
    content = converter.convert_to_platform(novel_content, platform)

    if output_path:
        save_path = Path(output_path)
    else:
        save_path = EXPORT_DIR / f"novel_{platform}.txt"

    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(save_path)
