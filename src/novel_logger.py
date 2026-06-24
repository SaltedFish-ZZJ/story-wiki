"""
Story Wiki - 小说日志模块
记录小说生成过程：章节保存、知识库日志、合并输出、进度追踪、断点续写。
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.interfaces import (
    NovelLoggerInterface,
    ChapterContent,
)
from src.config import CREATE_OUTPUT_DIR as NOVELS_DIR
from src.utils import safe_filename as _safe_filename


class NovelLogger(NovelLoggerInterface):
    """
    小说日志记录器。

    文件结构：
        data/novels/{safe_title}/
            progress.json          — 写作进度
            knowledge_log.json     — 知识库变更日志
            chapter_1.json         — 第 1 章
            chapter_2.json         — 第 2 章
            ...
    """

    def __init__(self, config: dict):
        """
        初始化日志记录器。

        Args:
            config: 配置字典，可选键：
                - book_title (str): 作品标题，用于目录组织
                - output_dir (str|Path): 输出目录，默认 DATA_DIR/novels
        """
        self.config = config
        self.book_title = config.get("book_title", "未命名作品")
        raw_dir = config.get("output_dir", NOVELS_DIR)
        self.output_dir = Path(raw_dir) if raw_dir else NOVELS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── BaseModule 接口实现 ──────────────────────────────────────

    def run(self, input_data: dict) -> dict:
        """
        运行日志记录。

        支持的 action：
            - save_chapter: 保存章节
            - update_knowledge_log: 更新知识库日志
            - merge_novel: 合并为完整小说
            - get_progress: 获取写作进度
            - resume_writing: 断点续写

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
            if action == "save_chapter":
                chapter_num = input_data["chapter_num"]
                content = input_data["content"]
                self.save_chapter(chapter_num, content)
                return {"success": True, "message": f"第 {chapter_num} 章已保存"}

            elif action == "update_knowledge_log":
                changes = input_data["changes"]
                self.update_knowledge_log(changes)
                return {"success": True, "message": "知识库日志已更新"}

            elif action == "merge_novel":
                book_title = input_data.get("book_title", self.book_title)
                result = self.merge_novel(book_title)
                return {"success": True, "content": result}

            elif action == "get_progress":
                book_title = input_data.get("book_title", self.book_title)
                result = self.get_progress(book_title)
                return {"success": True, "progress": result}

            elif action == "resume_writing":
                book_title = input_data.get("book_title", self.book_title)
                next_chapter = self.resume_writing(book_title)
                return {"success": True, "next_chapter": next_chapter}

            else:
                return {"success": False, "error": f"未知 action: {action}"}

        except (KeyError, TypeError) as e:
            return {"success": False, "error": f"参数错误: {e}"}
        except Exception as e:
            return {"success": False, "error": f"执行失败: {e}"}

    def validate(self, output_data: dict) -> bool:
        """验证输出数据是否合法。"""
        if not isinstance(output_data, dict):
            return False
        if "success" not in output_data:
            return False
        if output_data["success"] and "message" in output_data:
            return True
        if output_data["success"] and "content" in output_data:
            return True
        if output_data["success"] and "progress" in output_data:
            return True
        if output_data["success"] and "next_chapter" in output_data:
            return True
        if not output_data["success"] and "error" in output_data:
            return True
        return False

    # ── 目录辅助 ────────────────────────────────────────────────

    def _novel_dir(self, book_title: str) -> Path:
        """获取小说目录路径。"""
        return self.output_dir / _safe_filename(book_title)

    def _chapter_file(self, book_title: str, chapter_num: int) -> Path:
        """获取章节文件路径。"""
        return self._novel_dir(book_title) / f"chapter_{chapter_num}.json"

    def _progress_file(self, book_title: str) -> Path:
        """获取进度文件路径。"""
        return self._novel_dir(book_title) / "progress.json"

    def _knowledge_log_file(self, book_title: str) -> Path:
        """获取知识库日志文件路径。"""
        return self._novel_dir(book_title) / "knowledge_log.json"

    def _ensure_novel_dir(self, book_title: str) -> Path:
        """确保小说目录存在并返回。"""
        d = self._novel_dir(book_title)
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── 内部读写辅助 ────────────────────────────────────────────

    def _read_json(self, path: Path, default=None):
        """安全读取 JSON 文件。"""
        if not path.exists():
            return default if default is not None else {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[NovelLogger] 读取文件失败 {path}: {e}")
            return default if default is not None else {}

    def _write_json(self, path: Path, data):
        """安全写入 JSON 文件。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"[NovelLogger] 写入文件失败 {path}: {e}")
            raise

    def _chapter_to_dict(self, content: ChapterContent) -> dict:
        """将 ChapterContent 转为可序列化字典。"""
        return {
            "chapter_num": content.chapter_num,
            "title": content.title,
            "content": content.content,
            "word_count": content.word_count,
            "characters_involved": content.characters_involved,
            "events_happened": content.events_happened,
        }

    def _dict_to_chapter(self, data: dict) -> ChapterContent:
        """将字典转为 ChapterContent。"""
        return ChapterContent(
            chapter_num=data["chapter_num"],
            title=data["title"],
            content=data["content"],
            word_count=data.get("word_count", 0),
            characters_involved=data.get("characters_involved", []),
            events_happened=data.get("events_happened", []),
        )

    # ── 核心接口实现 ────────────────────────────────────────────

    def save_chapter(self, chapter_num: int, content: ChapterContent):
        """
        保存章节内容。

        同时更新进度文件。使用初始化时配置的 book_title 作为目录名。

        Args:
            chapter_num: 章节号
            content: 章节内容对象
        """
        if chapter_num < 1:
            raise ValueError(f"章节号必须 >= 1，当前: {chapter_num}")
        if not isinstance(content, ChapterContent):
            raise TypeError("content 必须是 ChapterContent 类型")
        if not content.content and content.content != "":
            raise ValueError("章节内容不能为空（允许空字符串）")

        book_title = self.book_title
        self._ensure_novel_dir(book_title)

        chapter_data = self._chapter_to_dict(content)
        chapter_data["saved_at"] = datetime.now().isoformat()

        # 写入章节文件
        chapter_file = self._chapter_file(book_title, chapter_num)
        self._write_json(chapter_file, chapter_data)

        # 更新进度
        self._update_progress(book_title, chapter_num, content.word_count)

        print(f"[NovelLogger] 已保存第 {chapter_num} 章「{content.title}」"
              f"（{content.word_count} 字）")

    def _update_progress(self, book_title: str, chapter_num: int, word_count: int):
        """更新进度文件。"""
        progress = self._read_json(self._progress_file(book_title), {
            "book_title": book_title,
            "total_chapters": 0,
            "completed_chapters": 0,
            "total_words": 0,
            "chapter_word_counts": {},
            "last_updated": "",
        })

        # 更新字数
        old_count = progress.get("chapter_word_counts", {}).get(str(chapter_num), 0)
        progress["total_words"] = progress.get("total_words", 0) - old_count + word_count

        if "chapter_word_counts" not in progress:
            progress["chapter_word_counts"] = {}
        progress["chapter_word_counts"][str(chapter_num)] = word_count

        # 更新完成章节数
        all_chapter_files = list(self._novel_dir(book_title).glob("chapter_*.json"))
        progress["completed_chapters"] = len(all_chapter_files)

        # 更新总章节数（取已完成章节号的最大值）
        if chapter_num > progress.get("total_chapters", 0):
            progress["total_chapters"] = chapter_num

        progress["last_updated"] = datetime.now().isoformat()

        self._write_json(self._progress_file(book_title), progress)

    def update_knowledge_log(self, changes: dict):
        """
        更新知识库变更日志。

        Args:
            changes: 变更内容，格式：
                {
                    "book_title": "作品名",
                    "chapter_num": 1,          # 可选
                    "new_characters": [...],    # 新人物列表
                    "updated_characters": [...], # 更新的人物列表
                    "new_events": [...],        # 新事件列表
                    "new_settings": [...]       # 新设定列表
                }
        """
        if not isinstance(changes, dict):
            raise TypeError("changes 必须是 dict 类型")

        book_title = changes.get("book_title", "未命名作品")
        self._ensure_novel_dir(book_title)

        log_file = self._knowledge_log_file(book_title)
        existing_log = self._read_json(log_file, {"entries": []})

        if "entries" not in existing_log:
            existing_log["entries"] = []

        entry = {
            "timestamp": datetime.now().isoformat(),
            "chapter_num": changes.get("chapter_num"),
            "new_characters": changes.get("new_characters", []),
            "updated_characters": changes.get("updated_characters", []),
            "new_events": changes.get("new_events", []),
            "new_settings": changes.get("new_settings", []),
        }

        existing_log["entries"].append(entry)
        existing_log["book_title"] = book_title
        existing_log["last_updated"] = datetime.now().isoformat()

        self._write_json(log_file, existing_log)

        total_new = (
            len(entry["new_characters"])
            + len(entry["new_events"])
            + len(entry["new_settings"])
        )
        print(f"[NovelLogger] 知识库日志已更新：{total_new} 项新增变更")

    def merge_novel(self, book_title: str) -> str:
        """
        合并所有已保存章节为完整小说文本。

        Args:
            book_title: 作品标题

        Returns:
            完整小说内容（markdown 格式）
        """
        novel_dir = self._novel_dir(book_title)
        if not novel_dir.exists():
            raise FileNotFoundError(f"小说目录不存在: {novel_dir}")

        # 收集所有章节文件
        chapter_files = sorted(
            novel_dir.glob("chapter_*.json"),
            key=lambda p: self._extract_chapter_num(p.name)
        )

        if not chapter_files:
            raise FileNotFoundError(f"未找到任何章节文件: {novel_dir}")

        parts = [f"# {book_title}\n"]

        for cf in chapter_files:
            chapter_data = self._read_json(cf)
            if not chapter_data:
                continue

            title = chapter_data.get("title", "")
            content = chapter_data.get("content", "")
            chapter_num = chapter_data.get("chapter_num", "")

            parts.append(f"\n## 第 {chapter_num} 章 {title}\n")
            parts.append(content)
            parts.append("")  # 章节间空行

        return "\n".join(parts)

    def get_progress(self, book_title: str) -> dict:
        """
        获取写作进度。

        Args:
            book_title: 作品标题

        Returns:
            {
                "book_title": "作品标题",
                "total_chapters": 总章节数,
                "completed_chapters": 已完成章节数,
                "total_words": 总字数,
                "last_updated": 最后更新时间
            }
        """
        progress_file = self._progress_file(book_title)
        progress = self._read_json(progress_file)

        if not progress:
            # 尝试从目录中扫描
            return self._scan_progress(book_title)

        return {
            "book_title": book_title,
            "total_chapters": progress.get("total_chapters", 0),
            "completed_chapters": progress.get("completed_chapters", 0),
            "total_words": progress.get("total_words", 0),
            "last_updated": progress.get("last_updated", ""),
        }

    def _scan_progress(self, book_title: str) -> dict:
        """从目录扫描实际进度（作为备份方案）。"""
        novel_dir = self._novel_dir(book_title)
        if not novel_dir.exists():
            return {
                "book_title": book_title,
                "total_chapters": 0,
                "completed_chapters": 0,
                "total_words": 0,
                "last_updated": "",
            }

        chapter_files = list(novel_dir.glob("chapter_*.json"))
        total_words = 0
        max_chapter = 0

        for cf in chapter_files:
            data = self._read_json(cf)
            if data:
                total_words += data.get("word_count", 0)
                ch_num = data.get("chapter_num", 0)
                if ch_num > max_chapter:
                    max_chapter = ch_num

        return {
            "book_title": book_title,
            "total_chapters": max_chapter,
            "completed_chapters": len(chapter_files),
            "total_words": total_words,
            "last_updated": "",
        }

    def resume_writing(self, book_title: str) -> int:
        """
        恢复写作（断点续写）。

        返回下一个要写的章节号。如果没有任何章节已保存，返回 1。

        Args:
            book_title: 作品标题

        Returns:
            下一个要写的章节号
        """
        novel_dir = self._novel_dir(book_title)
        if not novel_dir.exists():
            return 1

        chapter_files = list(novel_dir.glob("chapter_*.json"))
        if not chapter_files:
            return 1

        # 找到最大章节号
        max_chapter = 0
        for cf in chapter_files:
            ch_num = self._extract_chapter_num(cf.name)
            if ch_num > max_chapter:
                max_chapter = ch_num

        return max_chapter + 1

    @staticmethod
    def _extract_chapter_num(filename: str) -> int:
        """从文件名提取章节号。"""
        match = re.search(r"chapter_(\d+)\.json", filename)
        if match:
            return int(match.group(1))
        return 0

    # ── 辅助方法 ────────────────────────────────────────────────

    def list_novels(self) -> List[str]:
        """列出所有已记录的小说标题。"""
        if not self.output_dir.exists():
            return []

        novels = []
        for d in sorted(self.output_dir.iterdir()):
            if d.is_dir() and list(d.glob("chapter_*.json")):
                novels.append(d.name)
        return novels

    def delete_novel(self, book_title: str) -> bool:
        """删除小说的所有日志文件。"""
        import shutil
        novel_dir = self._novel_dir(book_title)
        if not novel_dir.exists():
            return False
        try:
            shutil.rmtree(novel_dir)
            print(f"[NovelLogger] 已删除小说日志: {book_title}")
            return True
        except OSError as e:
            print(f"[NovelLogger] 删除失败: {e}")
            return False

    def get_chapter(self, book_title: str, chapter_num: int) -> Optional[ChapterContent]:
        """获取指定章节内容。"""
        chapter_file = self._chapter_file(book_title, chapter_num)
        data = self._read_json(chapter_file)
        if not data:
            return None
        return self._dict_to_chapter(data)

    def get_knowledge_log(self, book_title: str) -> List[dict]:
        """获取知识库变更日志条目列表。"""
        log_file = self._knowledge_log_file(book_title)
        log_data = self._read_json(log_file, {"entries": []})
        return log_data.get("entries", [])
