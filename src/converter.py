"""
Story Wiki - 格式转换器模块
将生成的小说转换为多平台格式（番茄/起点/晋江）、EPUB、Markdown 和纯文本。

实现 ConverterInterface 接口，新增 EPUB 优化、Markdown 导出、批量导出功能。
"""
import re
import os
import shutil
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
        "description": "番茄小说，流量大，适合新人",
    },
    "qidian": {
        "name": "起点中文网",
        "paragraph_indent": "　　",
        "title_format": "第{num}章 {title}",
        "prohibited_chars": [],
        "line_spacing": "\n",
        "description": "起点中文网，读者付费意愿强",
    },
    "jjwxc": {
        "name": "晋江文学城",
        "paragraph_indent": "　　",
        "title_format": "第{num}章 {title}",
        "prohibited_chars": [],
        "line_spacing": "\n",
        "description": "晋江文学城，女性读者为主",
    },
    "ciweimao": {
        "name": "刺猬猫",
        "paragraph_indent": "　　",
        "title_format": "第{num}章 {title}",
        "prohibited_chars": ["**", "```"],
        "line_spacing": "\n",
        "description": "刺猬猫，二次元轻小说平台",
    },
    "zongheng": {
        "name": "纵横中文网",
        "paragraph_indent": "　　",
        "title_format": "第{num}章 {title}",
        "prohibited_chars": [],
        "line_spacing": "\n",
        "description": "纵横中文网，老牌网文平台",
    },
}

SUPPORTED_PLATFORMS = list(PLATFORM_RULES.keys())


class Converter(ConverterInterface):
    """
    格式转换器：将小说内容转换为多平台格式、EPUB、Markdown 和纯文本。

    新增功能：
        - EPUB 优化（带封面生成、目录增强、样式美化）
        - Markdown 导出（完整导出、带目录）
        - 批量导出（选择格式、一键全平台）

    文件结构：
        data/novels/{safe_title}/exports/
            {title}_fanqie.txt
            {title}_qidian.txt
            {title}_jjwxc.txt
            {title}_ciweimao.txt
            {title}_zongheng.txt
            {title}.epub
            {title}.md
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
            - to_epub_with_cover: 带封面的 EPUB 生成
            - to_txt: 转换为纯文本
            - to_markdown: 转换为 Markdown
            - to_markdown_with_toc: 带目录的 Markdown
            - to_all: 全格式导出
            - batch_export: 批量导出指定格式
            - to_all_platforms: 导出到所有平台格式

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

            elif action == "to_epub_with_cover":
                content = input_data["content"]
                metadata = input_data.get("metadata", {})
                cover_image = input_data.get("cover_image")
                result = self.create_epub_with_cover(content, metadata, cover_image)
                return {"success": True, "path": result}

            elif action == "to_txt":
                content = input_data["content"]
                result = self.convert_to_txt(content)
                return {"success": True, "content": result}

            elif action == "to_markdown":
                content = input_data["content"]
                metadata = input_data.get("metadata", {})
                result = self.export_to_markdown(content, metadata)
                return {"success": True, "path": result}

            elif action == "to_markdown_with_toc":
                content = input_data["content"]
                metadata = input_data.get("metadata", {})
                chapters = self._parse_chapters(content)
                result = self.create_markdown_with_toc(chapters, metadata)
                return {"success": True, "path": result}

            elif action == "to_all":
                content = input_data["content"]
                metadata = input_data.get("metadata", {})
                output_dir = input_data.get("output_dir")
                result = self.convert_to_all(content, metadata, output_dir)
                return {"success": True, "files": result}

            elif action == "batch_export":
                content = input_data["content"]
                metadata = input_data.get("metadata", {})
                formats = input_data.get("formats", [])
                result = self.batch_export(content, metadata, formats)
                return {"success": True, "files": result}

            elif action == "to_all_platforms":
                content = input_data["content"]
                metadata = input_data.get("metadata", {})
                result = self.export_to_all_platforms(content, metadata)
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

        根据目标平台的规则进行格式化处理：
        - 段落缩进
        - 章节标题标准化
        - 禁用字符过滤
        - 平台特定格式化规则

        Args:
            novel_content: 小说内容（支持 Markdown 格式）
            platform: 目标平台（fanqie/qidian/jjwxc/ciweimao/zongheng）

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
                - cover_image (str): 封面图片路径（支持 PNG/JPG）
                - publisher (str): 出版社
                - date (str): 出版日期（ISO 格式）
                - isbn (str): ISBN 号
                - rights (str): 版权信息

        Returns:
            EPUB 文件路径
        """
        return self.create_epub_with_cover(novel_content, metadata, metadata.get("cover_image"))

    def create_epub_with_cover(
        self,
        novel_content: str,
        metadata: dict,
        cover_image: Optional[str] = None
    ) -> str:
        """
        生成带封面的 EPUB 文件。

        增强的 EPUB 生成，支持：
        - 封面图片嵌入（自动检测 MIME 类型）
        - 增强的目录结构
        - 美化后的 HTML 内容

        Args:
            novel_content: 小说内容（支持 Markdown 格式）
            metadata: 元数据字典
            cover_image: 封面图片路径（可选，如果为 None 则从 metadata 中获取）

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
        cover_image_path = cover_image or metadata.get("cover_image")
        publisher = metadata.get("publisher", "")
        pub_date = metadata.get("date", "")
        isbn = metadata.get("isbn", "")
        rights = metadata.get("rights", "")

        # 创建 EPUB 书籍
        book = epub.EpubBook()
        book.set_identifier(f"story-wiki-{_safe_filename(title)}")
        book.set_title(title)
        book.set_language(language)
        book.add_author(author)

        if description:
            book.add_metadata("DC", "description", description)
        if publisher:
            book.add_metadata("DC", "publisher", publisher)
        if pub_date:
            book.add_metadata("DC", "date", pub_date)
        if isbn:
            book.add_metadata("DC", "identifier", isbn, {"id": "isbn"})
        if rights:
            book.add_metadata("DC", "rights", rights)

        # 添加封面图片
        if cover_image_path and os.path.exists(cover_image_path):
            try:
                with open(cover_image_path, "rb") as f:
                    cover_data = f.read()

                # 检测 MIME 类型
                ext = Path(cover_image_path).suffix.lower()
                mime_map = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                }
                mime_type = mime_map.get(ext, "image/jpeg")

                book.set_cover(f"cover{ext}", cover_data)
                print(f"[Converter] 封面图片已嵌入: {cover_image_path}")
            except Exception as e:
                print(f"[Converter] 封面图片加载失败: {e}")

        # 添加 CSS 样式
        style = self._get_epub_css()
        css_item = epub.EpubItem(
            uid="style",
            file_name="style/default.css",
            media_type="text/css",
            content=style.encode("utf-8")
        )
        book.add_item(css_item)

        # 解析章节内容
        chapters = self._parse_chapters(novel_content)

        # 添加章节（使用增强的目录）
        epub_chapters = self.add_epub_toc(book, chapters, language, css_item)

        # 设置目录
        book.toc = epub_chapters

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

    def add_epub_toc(
        self,
        book: Any,
        chapters: List[tuple],
        language: str = "zh",
        css_item: Any = None
    ) -> List[Any]:
        """
        为 EPUB 添加增强目录。

        创建格式化的章节页面，每个章节包含：
        - 美化后的标题
        - 段落内容（支持 Markdown 转 HTML）
        - 统一的 CSS 样式

        Args:
            book: ebooklib.EpubBook 实例
            chapters: 章节列表 [(标题, 内容), ...]
            language: 语言代码
            css_item: CSS 样式项

        Returns:
            epub_chapters: EPUB 章节对象列表
        """
        try:
            from ebooklib import epub
        except ImportError:
            raise ImportError("EPUB 生成需要 ebooklib 库")

        epub_chapters = []

        for i, (ch_title, ch_content) in enumerate(chapters):
            chapter = epub.EpubHtml(
                title=ch_title,
                file_name=f"chapter_{i+1}.xhtml",
                lang=language,
            )
            # 使用增强的样式化内容
            html_content = self.style_epub_content(ch_title, ch_content, css_item)
            chapter.content = html_content.encode("utf-8")
            book.add_item(chapter)
            epub_chapters.append(chapter)

        return epub_chapters

    def style_epub_content(
        self,
        title: str,
        content: str,
        css_item: Any = None
    ) -> str:
        """
        美化 EPUB 内容样式。

        将 Markdown 内容转换为带有增强样式的 HTML：
        - 章节标题居中并添加装饰
        - 段落首行缩进
        - 引用块左侧边框
        - 列表样式美化
        - 水平线样式

        Args:
            title: 章节标题
            content: Markdown 格式内容
            css_item: CSS 样式项（可选）

        Returns:
            美化后的 HTML 内容
        """
        # 构建 HTML 头部
        style_link = ""
        if css_item:
            style_link = '<link rel="stylesheet" type="text/css" href="style/default.css"/>'

        html_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE html>',
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">',
            '<head>',
            f'<title>{title}</title>',
            style_link,
            '</head>',
            '<body>',
            f'<h1 class="chapter-title">{title}</h1>'
        ]

        # 处理内容
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 跳过空行
            if not stripped:
                html_parts.append('<p class="empty-line">&nbsp;</p>')
                i += 1
                continue

            # 处理标题（# 标题）
            if stripped.startswith("# "):
                text = stripped[2:].strip()
                html_parts.append(f'<h2>{text}</h2>')
                i += 1
                continue

            if stripped.startswith("## "):
                text = stripped[3:].strip()
                html_parts.append(f'<h3>{text}</h3>')
                i += 1
                continue

            if stripped.startswith("### "):
                text = stripped[4:].strip()
                html_parts.append(f'<h4>{text}</h4>')
                i += 1
                continue

            # 处理引用块（> 引用）
            if stripped.startswith("> "):
                quote_lines = []
                while i < len(lines) and lines[i].strip().startswith("> "):
                    quote_lines.append(lines[i].strip()[2:])
                    i += 1
                quote_text = "<br/>".join(quote_lines)
                html_parts.append(f'<blockquote class="quote">{quote_text}</blockquote>')
                continue

            # 处理无序列表（- 列表项）
            if stripped.startswith("- ") or stripped.startswith("* "):
                list_items = []
                while i < len(lines) and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                    item_text = lines[i].strip()[2:]
                    list_items.append(f'<li>{self._markdown_inline_to_html(item_text)}</li>')
                    i += 1
                html_parts.append('<ul class="list">')
                html_parts.extend(list_items)
                html_parts.append('</ul>')
                continue

            # 处理有序列表（1. 列表项）
            if re.match(r'^\d+\.\s', stripped):
                list_items = []
                while i < len(lines) and re.match(r'^\d+\.\s', lines[i].strip()):
                    item_text = re.sub(r'^\d+\.\s', '', lines[i].strip())
                    list_items.append(f'<li>{self._markdown_inline_to_html(item_text)}</li>')
                    i += 1
                html_parts.append('<ol class="list">')
                html_parts.extend(list_items)
                html_parts.append('</ol>')
                continue

            # 处理水平线（--- 或 ***）
            if stripped in ("---", "***", "___"):
                html_parts.append('<hr class="separator"/>')
                i += 1
                continue

            # 处理普通段落（支持行内 Markdown）
            processed_text = self._markdown_inline_to_html(stripped)
            html_parts.append(f'<p class="paragraph">{processed_text}</p>')
            i += 1

        # 关闭 HTML
        html_parts.extend([
            '</body>',
            '</html>'
        ])

        return "\n".join(html_parts)

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

        导出所有支持的格式：
        - 平台格式（fanqie/qidian/jjwxc/ciweimao/zongheng）
        - EPUB 格式
        - TXT 格式

        Args:
            novel_content: 小说内容
            metadata: 元数据
            output_dir: 输出目录（可选，默认使用初始化时的目录）

        Returns:
            {
                "fanqie": 文件路径,
                "qidian": 文件路径,
                "jjwxc": 文件路径,
                "ciweimao": 文件路径,
                "zongheng": 文件路径,
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

    # ── Markdown 导出 ──────────────────────────────────────────

    def export_to_markdown(
        self,
        novel_content: str,
        metadata: dict
    ) -> str:
        """
        导出为完整的 Markdown 文件。

        生成包含元数据头部、完整章节内容的 Markdown 文件。
        保留原始的 Markdown 格式，但添加标准化的结构。

        Args:
            novel_content: 小说内容（Markdown 格式）
            metadata: 元数据，可选键：
                - title (str): 书名
                - author (str): 作者
                - description (str): 简介
                - language (str): 语言
                - date (str): 日期

        Returns:
            Markdown 文件路径
        """
        title = metadata.get("title", "未命名作品")
        author = metadata.get("author", "")
        description = metadata.get("description", "")
        language = metadata.get("language", "zh")
        date = metadata.get("date", "")

        # 构建 Markdown 内容
        md_parts = []

        # 添加 YAML frontmatter
        md_parts.append("---")
        md_parts.append(f"title: \"{title}\"")
        if author:
            md_parts.append(f"author: \"{author}\"")
        if description:
            md_parts.append(f"description: \"{description}\"")
        md_parts.append(f"language: {language}")
        if date:
            md_parts.append(f"date: {date}")
        md_parts.append("generator: Story Wiki")
        md_parts.append("---")
        md_parts.append("")

        # 添加目录（如果有多章）
        chapters = self._parse_chapters(novel_content)
        if len(chapters) > 1:
            md_parts.append("## 目录")
            md_parts.append("")
            for i, (ch_title, _) in enumerate(chapters, 1):
                md_parts.append(f"- [{ch_title}](#{_safe_filename(ch_title)})")
            md_parts.append("")
            md_parts.append("---")
            md_parts.append("")

        # 添加章节内容
        for ch_title, ch_content in chapters:
            md_parts.append(f"## {ch_title}")
            md_parts.append("")
            md_parts.append(ch_content)
            md_parts.append("")

        md_content = "\n".join(md_parts)

        # 生成文件路径
        safe_title = _safe_filename(title)
        md_path = self.output_dir / f"{safe_title}.md"

        # 写入文件
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"[Converter] Markdown 已导出: {md_path}")
        return str(md_path)

    def create_markdown_with_toc(
        self,
        chapters: List[tuple],
        metadata: dict
    ) -> str:
        """
        生成带增强目录的 Markdown 文件。

        目录特点：
        - 可点击的章节链接
        - 章节编号
        - 字数统计（如果可用）

        Args:
            chapters: 章节列表 [(标题, 内容), ...]
            metadata: 元数据字典

        Returns:
            Markdown 文件路径
        """
        title = metadata.get("title", "未命名作品")
        author = metadata.get("author", "")
        description = metadata.get("description", "")

        md_parts = []

        # YAML frontmatter
        md_parts.append("---")
        md_parts.append(f"title: \"{title}\"")
        if author:
            md_parts.append(f"author: \"{author}\"")
        if description:
            md_parts.append(f"description: \"{description}\"")
        md_parts.append("generator: Story Wiki")
        md_parts.append("---")
        md_parts.append("")

        # 标题
        md_parts.append(f"# {title}")
        md_parts.append("")
        if author:
            md_parts.append(f"**作者**: {author}")
            md_parts.append("")
        if description:
            md_parts.append(f"> {description}")
            md_parts.append("")
        md_parts.append("---")
        md_parts.append("")

        # 增强的目录
        md_parts.append("## 📖 目录")
        md_parts.append("")
        for i, (ch_title, ch_content) in enumerate(chapters, 1):
            # 计算字数（粗略）
            word_count = len(ch_content)
            anchor = _safe_filename(ch_title)
            md_parts.append(f"{i}. [{ch_title}](#{anchor}) — {word_count} 字")
        md_parts.append("")
        md_parts.append("---")
        md_parts.append("")

        # 章节内容
        for ch_title, ch_content in chapters:
            md_parts.append(f"## {ch_title}")
            md_parts.append("")
            md_parts.append(ch_content)
            md_parts.append("")
            md_parts.append("---")
            md_parts.append("")

        md_content = "\n".join(md_parts)

        # 生成文件路径
        safe_title = _safe_filename(title)
        md_path = self.output_dir / f"{safe_title}_toc.md"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"[Converter] 带目录的 Markdown 已导出: {md_path}")
        return str(md_path)

    # ── 批量导出 ──────────────────────────────────────────────

    def batch_export(
        self,
        novel_content: str,
        metadata: dict,
        formats: List[str],
        output_dir: Optional[str] = None
    ) -> Dict[str, str]:
        """
        批量导出指定格式。

        支持的格式：
        - fanqie: 番茄小说
        - qidian: 起点中文网
        - jjwxc: 晋江文学城
        - ciweimao: 刺猬猫
        - zongheng: 纵横中文网
        - epub: EPUB 电子书
        - txt: 纯文本
        - markdown/md: Markdown 文件
        - all: 所有格式

        Args:
            novel_content: 小说内容
            metadata: 元数据
            formats: 要导出的格式列表
            output_dir: 输出目录（可选）

        Returns:
            {
                "format_name": 文件路径
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

        # 规范化格式名称
        normalized_formats = []
        for fmt in formats:
            fmt_lower = fmt.lower().strip()
            if fmt_lower in ("markdown", "md"):
                normalized_formats.append("markdown")
            elif fmt_lower == "all":
                # 添加所有格式
                normalized_formats = list(SUPPORTED_PLATFORMS) + ["epub", "txt", "markdown"]
                break
            else:
                normalized_formats.append(fmt_lower)

        # 去重
        normalized_formats = list(dict.fromkeys(normalized_formats))

        # 执行导出
        for fmt in normalized_formats:
            try:
                if fmt in SUPPORTED_PLATFORMS:
                    content = self.convert_to_platform(novel_content, fmt)
                    file_path = out_dir / f"{safe_title}_{fmt}.txt"
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    results[fmt] = str(file_path)
                    print(f"[Converter] {PLATFORM_RULES[fmt]['name']} 格式已导出: {file_path}")

                elif fmt == "epub":
                    epub_metadata = {**metadata, "title": title}
                    epub_path = self.convert_to_epub(novel_content, epub_metadata)
                    dest = out_dir / f"{safe_title}.epub"
                    shutil.move(epub_path, dest)
                    results["epub"] = str(dest)
                    print(f"[Converter] EPUB 已导出: {dest}")

                elif fmt == "txt":
                    content = self.convert_to_txt(novel_content)
                    file_path = out_dir / f"{safe_title}.txt"
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    results["txt"] = str(file_path)
                    print(f"[Converter] TXT 已导出: {file_path}")

                elif fmt == "markdown":
                    md_path = self.export_to_markdown(novel_content, metadata)
                    results["markdown"] = md_path
                    print(f"[Converter] Markdown 已导出: {md_path}")

                else:
                    print(f"[Converter] 跳过未知格式: {fmt}")

            except Exception as e:
                print(f"[Converter] {fmt} 导出失败: {e}")

        return results

    def export_to_all_platforms(
        self,
        novel_content: str,
        metadata: dict,
        output_dir: Optional[str] = None
    ) -> Dict[str, str]:
        """
        导出到所有支持的平台格式。

        与 convert_to_all 的区别：
        - 只导出平台格式（不包含 EPUB/TXT/Markdown）
        - 包含所有平台（包括新增的 ciweimao、zongheng）
        - 返回值包含平台的中文名称

        Args:
            novel_content: 小说内容
            metadata: 元数据
            output_dir: 输出目录（可选）

        Returns:
            {
                "fanqie": {"name": "番茄小说", "path": 文件路径},
                "qidian": {"name": "起点中文网", "path": 文件路径},
                ...
            }
        """
        title = metadata.get("title", "未命名作品")
        safe_title = _safe_filename(title)

        # 确定输出目录
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.output_dir / safe_title / "platforms"
        out_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        for platform in SUPPORTED_PLATFORMS:
            try:
                content = self.convert_to_platform(novel_content, platform)
                file_path = out_dir / f"{safe_title}_{platform}.txt"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                results[platform] = {
                    "name": PLATFORM_RULES[platform]["name"],
                    "path": str(file_path),
                    "description": PLATFORM_RULES[platform].get("description", ""),
                }
                print(f"[Converter] {PLATFORM_RULES[platform]['name']} 格式已导出: {file_path}")
            except Exception as e:
                print(f"[Converter] {PLATFORM_RULES[platform]['name']} 导出失败: {e}")

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

    def _content_to_html(self, title: str, content: str, css_item=None) -> str:
        """
        将 Markdown 内容转换为 HTML。

        支持的 Markdown 语法：
        - **加粗** → <strong>加粗</strong>
        - *斜体* → <em>斜体</em>
        - ~~删除线~~ → <del>删除线</del>
        - `代码` → <code>代码</code>
        - > 引用 → <blockquote>引用</blockquote>
        - - 列表项 → <ul><li>列表项</li></ul>
        - 1. 有序列表 → <ol><li>列表项</li></ol>

        Args:
            title: 章节标题
            content: Markdown 格式内容
            css_item: CSS 样式项（可选）

        Returns:
            HTML 格式内容
        """
        return self.style_epub_content(title, content, css_item)

    def _markdown_inline_to_html(self, text: str) -> str:
        """
        将行内 Markdown 标记转换为 HTML。

        支持：
        - **加粗** → <strong>加粗</strong>
        - *斜体* → <em>斜体</em>
        - ~~删除线~~ → <del>删除线</del>
        - `代码` → <code>代码</code>
        """
        # 处理加粗（**text**）
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        # 处理斜体（*text*）
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        # 处理删除线（~~text~~）
        text = re.sub(r'~~(.*?)~~', r'<del>\1</del>', text)
        # 处理行内代码（`text`）
        text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
        return text

    def _get_epub_css(self) -> str:
        """
        返回 EPUB 内嵌 CSS 样式。

        提供中文电子书排版样式：
        - 字体族设置
        - 段落首行缩进
        - 行高和段间距
        - 章节标题样式
        - 引用块样式
        - 列表样式
        """
        return """
/* Story Wiki EPUB 样式表 */

/* 全局样式 */
body {
    font-family: "Source Han Serif SC", "Noto Serif CJK SC", "SimSun", "宋体", serif;
    font-size: 1em;
    line-height: 1.8;
    margin: 1em;
    color: #333;
}

/* 章节标题 */
h1.chapter-title {
    font-size: 1.8em;
    text-align: center;
    margin: 2em 0 1.5em;
    font-weight: bold;
    color: #222;
    page-break-before: always;
}

h2 {
    font-size: 1.4em;
    margin: 1.5em 0 1em;
    font-weight: bold;
    color: #333;
}

h3 {
    font-size: 1.2em;
    margin: 1.2em 0 0.8em;
    font-weight: bold;
    color: #444;
}

h4 {
    font-size: 1.1em;
    margin: 1em 0 0.6em;
    font-weight: bold;
    color: #555;
}

/* 段落 */
p.paragraph {
    text-indent: 2em;
    margin: 0.5em 0;
    text-align: justify;
}

/* 空行 */
p.empty-line {
    margin: 0;
    line-height: 0.5;
}

/* 引用块 */
blockquote.quote {
    margin: 1em 2em;
    padding: 0.5em 1em;
    border-left: 3px solid #ccc;
    background-color: #f9f9f9;
    font-style: italic;
    color: #555;
}

/* 列表 */
ul.list, ol.list {
    margin: 1em 2em;
    padding-left: 1.5em;
}

ul.list li, ol.list li {
    margin: 0.3em 0;
}

/* 分隔线 */
hr.separator {
    border: none;
    border-top: 1px solid #ccc;
    margin: 2em 0;
}

/* 行内代码 */
code {
    font-family: "Source Code Pro", "Consolas", monospace;
    background-color: #f5f5f5;
    padding: 0.1em 0.3em;
    border-radius: 3px;
    font-size: 0.9em;
}

/* 加粗 */
strong {
    font-weight: bold;
}

/* 斜体 */
em {
    font-style: italic;
}

/* 删除线 */
del {
    text-decoration: line-through;
    color: #888;
}
"""


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


def batch_export_novel(
    novel_content: str,
    metadata: dict,
    formats: List[str],
    output_dir: Optional[str] = None
) -> Dict[str, str]:
    """
    便捷函数：批量导出小说为多种格式。

    Args:
        novel_content: 小说内容
        metadata: 元数据
        formats: 格式列表
        output_dir: 输出目录（可选）

    Returns:
        {格式: 文件路径} 字典
    """
    converter = Converter({"output_dir": output_dir or EXPORT_DIR})
    return converter.batch_export(novel_content, metadata, formats, output_dir)
