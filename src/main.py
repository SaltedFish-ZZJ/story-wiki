"""
Story Wiki - 主入口
串联整个分析流程：读取文本 → AI 分析 → 生成 Obsidian 笔记。
支持自动分章处理长文本。
"""
import argparse
import sys
from pathlib import Path

# 确保项目根目录在 Python path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import CHAPTER_THRESHOLD, CHAPTER_CHUNK_SIZE, VAULT_DIR, print_memory_status, init_runtime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Story Wiki - AI 驱动的故事知识库生成器（分析 + 创作）"
    )
    # ── 分析模式参数 ──
    parser.add_argument("--input", "-i", default=None, help="输入文本文件路径")
    parser.add_argument("--title", "-t", default=None, help="作品名（可选，不指定则 AI 自动推断）")
    parser.add_argument("--output", "-o", default=None, help=f"输出目录（默认: {VAULT_DIR}）")
    parser.add_argument("--dry-run", action="store_true", help="只分析不生成文件，打印 JSON 结果")
    parser.add_argument("--no-split", action="store_true", help="禁用分章分析，强制单次处理")
    parser.add_argument("--chunk-size", type=int, default=CHAPTER_CHUNK_SIZE,
                        help=f"无章节标记时每块的目标字数（默认: {CHAPTER_CHUNK_SIZE}）")
    parser.add_argument("--incremental", action="store_true", help="启用增量分析模式（追加到已有笔记，不覆盖）")
    parser.add_argument("--start-chapter", type=int, default=None, help="起始章节编号（从 1 开始，需配合 --incremental 使用）")
    parser.add_argument("--end-chapter", type=int, default=None, help="结束章节编号（需配合 --incremental 使用）")
    parser.add_argument("--clear-cache", action="store_true", help="清除所有分析缓存")
    parser.add_argument("--no-cache", action="store_true", help="禁用分析结果缓存")
    parser.add_argument("--memory-status", action="store_true", help="只显示内存状态，不执行分析")

    # ── 创作模式参数 ──
    parser.add_argument("--create", action="store_true", help="启用创作模式（从知识库生成小说）")
    parser.add_argument("--chapters", type=int, default=5, help="创作模式：生成章节数（默认 5）")
    parser.add_argument("--resume", action="store_true", help="创作模式：断点续写")
    parser.add_argument("--outline-only", action="store_true", help="创作模式：只生成大纲")
    parser.add_argument("--strict-quality", action="store_true",
                        help="创作模式：严格质量检查（不通过则重写，额外消耗 API 调用）")
    parser.add_argument("--chapter-start", type=int, default=None, help="创作模式：起始章节号")
    parser.add_argument("--chapter-end", type=int, default=None, help="创作模式：结束章节号")

    # ── 项目管理参数 ──
    parser.add_argument("--list-books", action="store_true", help="列出所有已分析的作品")
    parser.add_argument("--book-info", type=str, default=None, help="查看指定作品的详细信息")
    parser.add_argument("--cross-search", type=str, default=None, help="跨作品搜索关键词")
    parser.add_argument("--similar-characters", action="store_true", help="查找跨作品相似人物")

    # ── 成长曲线参数 ──
    parser.add_argument("--growth-curve", type=str, default=None, help="查看指定人物的成长曲线")
    parser.add_argument("--growth-chart", type=str, default=None, help="生成指定人物的成长曲线图表数据")
    parser.add_argument("--extract-growth", action="store_true", help="从分析结果中提取成长事件并保存")
    parser.add_argument("--growth-analysis", type=str, nargs="?", const="", default=None,
                        help="分析角色成长曲线（可选指定人物名，不指定则分析全部主要人物）")

    # ── Agent 驱动模式（零 API 调用，LLM 由外部 Agent 提供）──
    parser.add_argument("--plan", type=str, default=None, metavar="FILE",
                        help="Agent 模式：纯本地切章，产出 manifest.json + 章节原文，交给 Agent 逐章分析")
    parser.add_argument("--ingest", type=str, default=None, metavar="CARDS_JSON",
                        help="Agent 模式：把 Agent 生成的卡片 JSON 增量写入知识库（零 API 调用）")
    parser.add_argument("--book-title", type=str, default=None, help="配合 --ingest：指定书名（卡片 JSON 未提供 title 时）")
    parser.add_argument("--chapter", type=str, default=None, help="配合 --ingest：为这批事件卡注入章节归属（如 \"第3章\"）")

    # ── 格式转换/导出参数 ──
    parser.add_argument("--export-markdown", action="store_true", help="将已生成的小说导出为Markdown格式")
    parser.add_argument("--export-epub", action="store_true", help="将已生成的小说导出为EPUB格式")
    parser.add_argument("--export-txt", action="store_true", help="将已生成的小说导出为纯文本格式")
    parser.add_argument("--batch-export", action="store_true", help="批量导出为所有支持的格式（EPUB/TXT/平台格式）")

    return parser


def main():
    init_runtime(verbose=False)
    parser = build_parser()
    args = parser.parse_args()

    # ── 快速命令：无依赖 ──
    if args.memory_status:
        print_memory_status()
        return

    if args.clear_cache:
        from src.pipeline import clear_cache
        clear_cache()
        return

    # ── 成长曲线命令 ──
    if args.growth_curve or args.growth_chart or args.extract_growth or args.growth_analysis is not None:
        from src.commands.growth import run_growth
        run_growth(args)
        return

    # ── 项目管理命令 ──
    if args.list_books or args.book_info or args.cross_search or args.similar_characters:
        from src.commands.project import run_project
        run_project(args)
        return

    # ── 格式转换/导出命令 ──
    if args.export_markdown or args.export_epub or args.export_txt or args.batch_export:
        from src.commands.export import run_export
        run_export(args)
        return

    # ── Agent 驱动模式 ──
    if args.plan or args.ingest:
        from src.commands.agent import run_ingest, run_plan
        if args.plan:
            run_plan(args)
        else:
            run_ingest(args)
        return

    # ── 创作模式 ──
    if args.create:
        from src.commands.create import run_create
        run_create(args)
        return

    # ── 默认：分析管线 ──
    if not args.input:
        parser.error("--input/-i 参数是必需的（除非使用 --clear-cache、--memory-status 或 --create）")

    from src.commands.analysis import run_analysis
    run_analysis(args)


if __name__ == "__main__":
    main()
