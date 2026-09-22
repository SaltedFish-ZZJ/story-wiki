"""
Story Wiki - 创作管线入口模块
串联 VaultManager → PlotGenerator → ChapterGenerator → NovelLogger，
实现从知识库到完整小说的创作流程。
"""
import time
from typing import Dict, List, Optional, Tuple

from src.interfaces import (
    PlotOutline,
    ChapterContent,
    Character,
)
from src.vault_manager import VaultManager
from src.plot_generator import PlotGenerator
from src.chapter_generator import ChapterGenerator
from src.novel_logger import NovelLogger
from src.config import (
    DATA_DIR,
    CREATE_DEFAULT_CHAPTERS,
    CREATE_WORDS_PER_CHAPTER,
    CREATE_MAX_RETRIES,
    MIN_WORDS,
    MAX_WORDS,
)


def create_novel(
    book_title: str,
    num_chapters: int = CREATE_DEFAULT_CHAPTERS,
    incremental: bool = True,
    outline_only: bool = False,
    chapter_range: Tuple[int, int] = None,
    outline_only_output: bool = False,
    strict_quality: bool = False,
) -> dict:
    """
    核心创作管线：从知识库生成完整小说。

    流程：
    1. VaultManager.load_all_cards() → 知识库
    2. PlotGenerator.generate_outline() → 情节大纲
    3. 循环 ChapterGenerator.generate_chapter() → 逐章生成
    4. NovelLogger.save_chapter() → 保存每一章
    5. NovelLogger.merge_novel() → 合并为完整文本

    Args:
        book_title: 作品标题（对应 vault 目录名）
        num_chapters: 要生成的章节数（默认 5）
        incremental: 是否增量生成（跳过已有的章）
        outline_only: 只生成大纲不写章节
        chapter_range: 指定生成范围 (start, end)，覆盖 num_chapters
        outline_only_output: 仅输出大纲预览（不写文件）

    Returns:
        {
            "success": bool,
            "book_title": str,
            "outline": PlotOutline | None,
            "chapters_generated": int,
            "total_words": int,
            "output_dir": str,
            "error": str | None,
        }
    """
    print(f"\n{'═' * 50}")
    print(f"  Story Wiki — 创作管线")
    print(f"  作品：{book_title}")
    print(f"  目标：{num_chapters} 章")
    print(f"{'═' * 50}\n")

    # ── 步骤 1：加载知识库 ──
    print("[1/5] 加载知识库...")
    vault_config = {"book_title": book_title}
    vault = VaultManager(vault_config)

    try:
        knowledge_base = vault.load_all_cards()
    except (OSError, ValueError, RuntimeError) as e:
        return _error_result(book_title, f"加载知识库失败: {e}")

    char_count = len(knowledge_base.get("characters", []))
    setting_count = len(knowledge_base.get("settings", []))
    event_count = len(knowledge_base.get("events", []))
    print(f"  [OK] 知识库：{char_count} 人物，{setting_count} 设定，{event_count} 事件")

    if char_count == 0 and event_count == 0:
        return _error_result(book_title, "知识库为空，请先运行分析管线生成知识库")

    # ── 步骤 2：生成情节大纲 ──
    print("[2/5] 生成情节大纲...")
    plot_config = {}
    plot_gen = PlotGenerator(plot_config)

    try:
        outline = plot_gen.generate_outline(book_title, knowledge_base)
    except (RuntimeError, ValueError) as e:
        return _error_result(book_title, f"生成大纲失败: {e}")

    print(f"  [OK] 大纲：「{outline.title}」")
    print(f"    主题：{outline.theme}")
    print(f"    冲突：{outline.conflict}")

    # 只生成大纲模式
    if outline_only:
        _display_outline(outline, num_chapters)
        return {
            "success": True,
            "book_title": book_title,
            "outline": outline,
            "chapters_generated": 0,
            "total_words": 0,
            "output_dir": "",
            "error": None,
        }

    # 大纲预览模式（输出但不写文件）
    if outline_only_output:
        _display_outline(outline, num_chapters)
        return {
            "success": True,
            "book_title": book_title,
            "outline": outline,
            "chapters_generated": 0,
            "total_words": 0,
            "output_dir": "",
            "error": None,
        }

    # ── 步骤 3：准备章节生成 ──
    logger_config = {"book_title": book_title}
    logger = NovelLogger(logger_config)

    # 确定生成范围
    if chapter_range:
        start_chapter, end_chapter = chapter_range
    elif incremental:
        # 断点续写：从上次中断处继续
        next_chapter = logger.resume_writing(book_title)
        start_chapter = next_chapter
        end_chapter = start_chapter + num_chapters - 1
    else:
        start_chapter = 1
        end_chapter = num_chapters

    total_to_generate = end_chapter - start_chapter + 1
    print(f"[3/5] 准备生成章节（第 {start_chapter} 章 → 第 {end_chapter} 章，共 {total_to_generate} 章）")

    # ── 步骤 4：逐章生成 ──
    print("[4/5] 开始生成...\n")

    chapter_gen_config = {
        "min_words": MIN_WORDS,
        "max_words": MAX_WORDS,
    }
    chapter_gen = ChapterGenerator(chapter_gen_config)

    # 获取知识库人物对象（用于质量检查）
    characters = _load_character_objects(vault, knowledge_base)
    timeline = vault.get_timeline()

    chapters_generated = 0
    total_words = 0
    previous_content = ""

    for chapter_num in range(start_chapter, end_chapter + 1):
        progress_pct = (chapter_num - start_chapter) / total_to_generate * 100
        print(f"[创作] {progress_pct:.0f}% ({chapter_num - start_chapter}/{total_to_generate}) — 第 {chapter_num} 章")

        # 构建上下文
        context = {
            "previous_content": previous_content,
            "characters": knowledge_base.get("characters", []),
            "events": knowledge_base.get("events", []),
        }

        # 生成章节（带重试）
        content = None
        for attempt in range(CREATE_MAX_RETRIES):
            try:
                content = chapter_gen.generate_chapter(chapter_num, outline, context, num_chapters)
                break
            except (RuntimeError, ValueError) as e:
                if attempt < CREATE_MAX_RETRIES - 1:
                    delay = 2 ** attempt
                    print(f"  [WARN] 生成失败，{delay}s 后重试... ({e})")
                    time.sleep(delay)
                else:
                    print(f"  [ERROR] 第 {chapter_num} 章生成失败（已重试 {CREATE_MAX_RETRIES} 次）: {e}")
                    return _error_result(
                        book_title,
                        f"第 {chapter_num} 章生成失败: {e}",
                        chapters_generated,
                        total_words,
                    )

        if content is None:
            continue

        # 质量检查（strict 模式下不通过会尝试重写一次）
        if strict_quality:
            try:
                quality = chapter_gen.quality_check(content, characters)
                if not quality.get("passed", True):
                    issues = quality.get("issues", [])
                    print(f"  [WARN] 质量检查发现问题（{len(issues)} 个），尝试重写...")
                    # 重写一次
                    retry_context = {
                        **context,
                        "quality_feedback": issues,
                    }
                    try:
                        retry_content = chapter_gen.generate_chapter(
                            chapter_num, outline, retry_context, num_chapters
                        )
                        if retry_content and retry_content.word_count > 0:
                            content = retry_content
                            print(f"  [OK] 重写成功（{content.word_count} 字）")
                        else:
                            print(f"  [WARN] 重写失败，使用原始版本")
                    except (RuntimeError, ValueError) as e:
                        print(f"  [WARN] 重写异常: {e}")
            except (RuntimeError, ValueError) as e:
                print(f"  [WARN] 质量检查异常: {e}")

        # 保存章节
        try:
            logger.save_chapter(chapter_num, content)
        except (OSError, RuntimeError) as e:
            print(f"  [WARN] 保存章节失败: {e}")

        # 更新统计
        chapters_generated += 1
        total_words += content.word_count
        previous_content = content.content[:500]  # 取前 500 字作为下文上下文

        print(f"  [OK] 第 {chapter_num} 章「{content.title}」（{content.word_count} 字）\n")

    # ── 步骤 5：合并输出 ──
    print("[5/5] 合并输出...")
    try:
        merged_text = logger.merge_novel(book_title)
        output_file = logger._novel_dir(book_title) / "novel.txt"
        output_file.write_text(merged_text, encoding="utf-8")
        output_dir = str(logger._novel_dir(book_title))
        print(f"  [OK] 已保存到 {output_dir}/novel.txt")
    except (OSError, RuntimeError) as e:
        output_dir = str(logger._novel_dir(book_title))
        print(f"  [WARN] 合并输出失败: {e}")

    # 完成
    print(f"\n{'═' * 50}")
    print(f"  创作完成！")
    print(f"  生成：{chapters_generated} 章，{total_words} 字")
    print(f"  输出：{output_dir}")
    print(f"{'═' * 50}\n")

    return {
        "success": True,
        "book_title": book_title,
        "outline": outline,
        "chapters_generated": chapters_generated,
        "total_words": total_words,
        "output_dir": output_dir,
        "error": None,
    }


def _load_character_objects(vault: VaultManager, knowledge_base: dict) -> List[Character]:
    """从知识库加载 Character 对象列表。"""
    characters = []
    for char_dict in knowledge_base.get("characters", []):
        name = char_dict.get("name", "")
        if name:
            char_obj = vault.load_character(name)
            if char_obj:
                characters.append(char_obj)
    return characters


def _display_outline(outline: PlotOutline, num_chapters: int):
    """美化显示情节大纲。"""
    print(f"\n{'═' * 50}")
    print(f"  情节大纲")
    print(f"{'═' * 50}")
    print(f"  作品：{outline.title}")
    print(f"  主题：{outline.theme}")
    print(f"  冲突：{outline.conflict}")
    print()

    structure = outline.structure or {}
    for key, value in structure.items():
        if isinstance(value, dict):
            title = value.get("title", "")
            summary = value.get("summary", "")
            events = value.get("key_events", [])
            print(f"  {key}：{title}")
            if summary:
                print(f"    {summary}")
            if events:
                for event in events[:3]:
                    print(f"    · {event}")
        else:
            print(f"  {key}：{value}")
        print()

    if outline.key_points:
        print(f"  关键情节点：{'、'.join(outline.key_points[:5])}")

    if outline.ending_direction:
        print(f"  结局走向：{outline.ending_direction}")

    print(f"\n  总计：{num_chapters} 章，预计 {num_chapters * CREATE_WORDS_PER_CHAPTER} 字")
    print(f"{'═' * 50}\n")


def _error_result(
    book_title: str,
    error: str,
    chapters_generated: int = 0,
    total_words: int = 0,
) -> dict:
    """构建错误结果。"""
    print(f"\n[ERROR] 创作失败：{error}\n")
    return {
        "success": False,
        "book_title": book_title,
        "outline": None,
        "chapters_generated": chapters_generated,
        "total_words": total_words,
        "output_dir": "",
        "error": error,
    }


# ── 便捷函数 ──────────────────────────────────────────────

def quick_create(book_title: str, chapters: int = 3) -> dict:
    """
    快速创作：从知识库生成指定章节数的小说。

    Args:
        book_title: 作品标题
        chapters: 章节数（默认 3）

    Returns:
        创作结果
    """
    return create_novel(book_title, num_chapters=chapters, incremental=False)


def resume_create(book_title: str, chapters: int = 5) -> dict:
    """
    断点续写：从中断处继续生成。

    Args:
        book_title: 作品标题
        chapters: 要续写的章节数（默认 5）

    Returns:
        创作结果
    """
    return create_novel(book_title, num_chapters=chapters, incremental=True)


def preview_outline(book_title: str) -> dict:
    """
    只生成大纲，不写章节。

    Args:
        book_title: 作品标题

    Returns:
        大纲预览结果
    """
    return create_novel(book_title, outline_only=True)


# ── CLI 入口 ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Story Wiki 创作管线")
    parser.add_argument("--title", required=True, help="作品标题")
    parser.add_argument("--chapters", type=int, default=5, help="生成章节数（默认 5）")
    parser.add_argument("--resume", action="store_true", help="断点续写模式")
    parser.add_argument("--outline-only", action="store_true", help="只生成大纲")
    # 移除未使用的 seed 参数
    parser.add_argument("--chapter-start", type=int, help="起始章节号")
    parser.add_argument("--chapter-end", type=int, help="结束章节号")

    args = parser.parse_args()

    # 确定模式
    if args.outline_only:
        result = preview_outline(args.title)
    elif args.resume:
        result = resume_create(args.title, args.chapters)
    else:
        chapter_range = None
        if args.chapter_start and args.chapter_end:
            chapter_range = (args.chapter_start, args.chapter_end)

        result = create_novel(
            args.title,
            num_chapters=args.chapters,
            chapter_range=chapter_range,
        )

    if not result["success"]:
        exit(1)
