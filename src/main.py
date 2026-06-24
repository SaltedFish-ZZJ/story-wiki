"""
Story Wiki - 主入口
串联整个分析流程：读取文本 → AI 分析 → 生成 Obsidian 笔记。
支持自动分章处理长文本。

优化：添加内存监控，改进大文件处理。
"""
import argparse
import sys
from pathlib import Path

# 确保项目根目录在 Python path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import CHAPTER_THRESHOLD, CHAPTER_CHUNK_SIZE, VAULT_DIR, print_memory_status
from src.extractor import extract_text
from src.analyzer import analyze_text
from src.pipeline import analyze_chaptered, analyze_chaptered_incremental, clear_cache
from src.generator import generate_vault, generate_vault_incremental


def main():
    parser = argparse.ArgumentParser(
        description="Story Wiki - AI 驱动的故事知识库生成器（分析 + 创作）"
    )
    parser.add_argument(
        "--input", "-i",
        default=None,
        help="输入文本文件路径",
    )
    parser.add_argument(
        "--title", "-t",
        default=None,
        help="作品名（可选，不指定则 AI 自动推断）",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help=f"输出目录（默认: {VAULT_DIR}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只分析不生成文件，打印 JSON 结果",
    )
    parser.add_argument(
        "--no-split",
        action="store_true",
        help="禁用分章分析，强制单次处理",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHAPTER_CHUNK_SIZE,
        help=f"无章节标记时每块的目标字数（默认: {CHAPTER_CHUNK_SIZE}）",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="启用增量分析模式（追加到已有笔记，不覆盖）",
    )
    parser.add_argument(
        "--start-chapter",
        type=int,
        default=None,
        help="起始章节编号（从 1 开始，需配合 --incremental 使用）",
    )
    parser.add_argument(
        "--end-chapter",
        type=int,
        default=None,
        help="结束章节编号（需配合 --incremental 使用）",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="清除所有分析缓存",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="禁用分析结果缓存",
    )
    parser.add_argument(
        "--memory-status",
        action="store_true",
        help="只显示内存状态，不执行分析",
    )

    # ── 创作模式参数 ──
    parser.add_argument(
        "--create",
        action="store_true",
        help="启用创作模式（从知识库生成小说）",
    )
    parser.add_argument(
        "--chapters",
        type=int,
        default=5,
        help="创作模式：生成章节数（默认 5）",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="创作模式：断点续写",
    )
    parser.add_argument(
        "--outline-only",
        action="store_true",
        help="创作模式：只生成大纲",
    )
    parser.add_argument(
        "--chapter-start",
        type=int,
        default=None,
        help="创作模式：起始章节号",
    )
    parser.add_argument(
        "--chapter-end",
        type=int,
        default=None,
        help="创作模式：结束章节号",
    )

    # ── 项目管理参数 ──
    parser.add_argument(
        "--list-books",
        action="store_true",
        help="列出所有已分析的作品",
    )
    parser.add_argument(
        "--book-info",
        type=str,
        default=None,
        help="查看指定作品的详细信息",
    )
    parser.add_argument(
        "--cross-search",
        type=str,
        default=None,
        help="跨作品搜索关键词",
    )
    parser.add_argument(
        "--similar-characters",
        action="store_true",
        help="查找跨作品相似人物",
    )

    # ── 成长曲线参数 ──
    parser.add_argument(
        "--growth-curve",
        type=str,
        default=None,
        help="查看指定人物的成长曲线",
    )
    parser.add_argument(
        "--growth-chart",
        type=str,
        default=None,
        help="生成指定人物的成长曲线图表数据",
    )
    parser.add_argument(
        "--extract-growth",
        action="store_true",
        help="从分析结果中提取成长事件并保存",
    )
    parser.add_argument(
        "--growth-analysis",
        type=str,
        nargs="?",
        const="",
        default=None,
        help="分析角色成长曲线（可选指定人物名，不指定则分析全部主要人物）",
    )

    # ── 格式转换/导出参数 ──
    parser.add_argument(
        "--export-markdown",
        action="store_true",
        help="将已生成的小说导出为Markdown格式",
    )
    parser.add_argument(
        "--export-epub",
        action="store_true",
        help="将已生成的小说导出为EPUB格式",
    )
    parser.add_argument(
        "--export-txt",
        action="store_true",
        help="将已生成的小说导出为纯文本格式",
    )
    parser.add_argument(
        "--batch-export",
        action="store_true",
        help="批量导出为所有支持的格式（EPUB/TXT/平台格式）",
    )

    args = parser.parse_args()

    # 处理内存状态命令
    if args.memory_status:
        print_memory_status()
        return

    # 处理缓存清除命令
    if args.clear_cache:
        clear_cache()
        return

    # ── 成长曲线命令 ──
    if args.growth_curve or args.growth_chart or args.extract_growth or args.growth_analysis is not None:
        from src.character_growth import CharacterGrowthTracker

        if not args.title:
            parser.error("成长曲线命令需要 --title 参数指定作品标题")

        tracker = CharacterGrowthTracker(VAULT_DIR, args.title)

        if args.growth_curve:
            curve = tracker.get_character_growth_curve(args.growth_curve)
            if curve is None:
                print(f"人物不存在: {args.growth_curve}")
                sys.exit(1)

            print(f"\n{'═' * 60}")
            print(f"  {curve.character_name} 成长曲线")
            print(f"{'═' * 60}")
            print(f"  摘要: {curve.summary}")
            print(f"  趋势: {curve.overall_trend}")
            print(f"  成长事件数: {len(curve.growth_events)}")

            if curve.growth_events:
                print(f"\n  成长事件:")
                print("-" * 60)
                for event in curve.growth_events:
                    sig_mark = "★" if event.significance == "高" else "☆"
                    print(f"  {sig_mark} [{event.chapter}] {event.event_name}")
                    print(f"    类型: {event.growth_type} | 时间: {event.time or '未知'}")
                    if event.description:
                        print(f"    描述: {event.description}")
                    if event.state_after:
                        print(f"    状态: {event.state_after}")
                    print()
            print(f"{'═' * 60}")
            return

        if args.growth_chart:
            chart_data = tracker.generate_growth_chart_data(args.growth_chart)
            if "error" in chart_data:
                print(f"错误: {chart_data['error']}")
                sys.exit(1)

            import json
            print(json.dumps(chart_data, ensure_ascii=False, indent=2))
            return

        if args.extract_growth:
            if not args.input:
                print("提取成长事件需要 --input 参数指定分析结果文件")
                sys.exit(1)

            try:
                import json
                with open(args.input, "r", encoding="utf-8") as f:
                    analysis = json.load(f)

                growth_events = tracker.extract_growth_events_from_analysis(analysis)
                if growth_events:
                    # 按人物分组
                    char_events = {}
                    for event in growth_events:
                        char_name = event.event_name.split("状态更新")[0].split("与")[0]
                        if char_name not in char_events:
                            char_events[char_name] = []
                        char_events[char_name].append(event)

                    for char_name, events in char_events.items():
                        tracker.save_growth_events(char_name, events)
                        print(f"已保存 {char_name} 的 {len(events)} 个成长事件")
                else:
                    print("未检测到成长事件")
            except Exception as e:
                print(f"提取成长事件失败: {e}")
                sys.exit(1)
            return

        if args.growth_analysis is not None:
            # 分析角色成长曲线
            target_char = args.growth_analysis if args.growth_analysis else None

            if target_char:
                # 分析指定角色
                curve = tracker.get_character_growth_curve(target_char)
                if curve is None:
                    print(f"人物不存在: {target_char}")
                    sys.exit(1)

                print(f"\n{'═' * 60}")
                print(f"  {curve.character_name} 成长分析报告")
                print(f"{'═' * 60}")
                print(f"  摘要: {curve.summary}")
                print(f"  趋势: {curve.overall_trend}")
                print(f"  成长阶段数: {len(curve.growth_phases)}")

                if curve.growth_phases:
                    print(f"\n  成长阶段:")
                    print("-" * 60)
                    for i, phase in enumerate(curve.growth_phases, 1):
                        print(f"  阶段 {i}: {phase.get('type', '未知')}")
                        print(f"    范围: {phase.get('start_chapter', '?')} - {phase.get('end_chapter', '?')}")
                        print(f"    事件数: {phase.get('events_count', 0)} (高重要性: {phase.get('high_significance_count', 0)})")
                        if phase.get('description'):
                            print(f"    描述: {phase['description']}")
                print(f"{'═' * 60}")
            else:
                # 分析所有主要人物
                vault_manager = tracker.vault_manager
                cards = vault_manager.load_all_cards()
                characters = cards.get("characters", [])

                if not characters:
                    print("知识库中没有人��信息")
                    sys.exit(1)

                print(f"\n{'═' * 60}")
                print(f"  全部角色成长分析")
                print(f"{'═' * 60}")

                for char_data in characters:
                    char_name = char_data.get("name", "")
                    if not char_name:
                        continue

                    curve = tracker.get_character_growth_curve(char_name)
                    if curve is None:
                        continue

                    event_count = len(curve.growth_events)
                    if event_count == 0:
                        continue

                    print(f"\n  👤 {char_name}")
                    print(f"    摘要: {curve.summary}")
                    print(f"    趋势: {curve.overall_trend}")
                    print(f"    成长事件数: {event_count}")

                print(f"\n{'═' * 60}")
            return

    # ── 项目管理命令 ──
    if args.list_books or args.book_info or args.cross_search or args.similar_characters:
        from src.project_manager import ProjectManager

        pm = ProjectManager()

        if args.list_books:
            books = pm.list_books()
            if not books:
                print("未找到任何已分析的作品。")
            else:
                print(f"\n已分析的作品（共 {len(books)} 本）：")
                print("-" * 60)
                for book in books:
                    print(f"  {book['title']}")
                    print(f"    人物: {book['characters']}  设定: {book['settings']}  事件: {book['events']}")
                print("-" * 60)
            return

        if args.book_info:
            summary = pm.get_book_summary(args.book_info)
            if not summary:
                print(f"作品不存在或读取失败: {args.book_info}")
                sys.exit(1)
            print(f"\n{'═' * 50}")
            print(f"  {summary['title']}")
            print(f"{'═' * 50}")
            print(f"  人物: {summary['characters_count']} 个")
            print(f"  设定: {summary['settings_count']} 个")
            print(f"  事件: {summary['events_count']} 个")
            if summary["timeline_span"]:
                print(f"  时间跨度: {summary['timeline_span']}")
            if summary["characters"]:
                print(f"\n  人物列表：")
                for c in summary["characters"]:
                    faction_info = f"（{c['faction']}）" if c["faction"] else ""
                    rel_info = f"，{c['relationships_count']} 个关系" if c["relationships_count"] else ""
                    print(f"    - {c['name']}{faction_info} — {c['identity'] or '未知'}{rel_info}")
            print(f"{'═' * 50}")
            return

        if args.cross_search:
            results = pm.search_cross_book(args.cross_search)
            if not results:
                print(f"未找到包含「{args.cross_search}」的卡片。")
            else:
                print(f"\n跨作品搜索「{args.cross_search}」结果：")
                print("-" * 60)
                for book_name, cards in results.items():
                    char_count = len(cards.get("characters", []))
                    setting_count = len(cards.get("settings", []))
                    event_count = len(cards.get("events", []))
                    print(f"  [{book_name}] 人物: {char_count}  设定: {setting_count}  事件: {event_count}")
                    for char in cards.get("characters", []):
                        print(f"    · 人物: {char['name']} — {char.get('identity', '')}")
                    for setting in cards.get("settings", []):
                        print(f"    · 设定: {setting['name']}")
                    for event in cards.get("events", []):
                        print(f"    · 事件: {event['name']}")
                print("-" * 60)
            return

        if args.similar_characters:
            matches = pm.find_similar_characters()
            if not matches:
                print("未找到跨作品相似人物。")
            else:
                print(f"\n跨作品相似人物（共 {len(matches)} 对）：")
                print("-" * 60)
                for m in matches:
                    a = m["character_a"]
                    b = m["character_b"]
                    print(f"  {a['name']}（{a['book']}） <-> {b['name']}（{b['book']}）")
                    print(f"    匹配方式: {m['match_type']}  置信度: {m['confidence']}")
                print("-" * 60)
            return

    # ── 格式转换/导出命令 ──
    if args.export_markdown or args.export_epub or args.export_txt or args.batch_export:
        from src.novel_logger import NovelLogger
        from src.converter import Converter

        if not args.title:
            parser.error("导出命令需要 --title 参数指定作品标题")

        # 初始化 NovelLogger 获取小说内容
        novel_logger = NovelLogger({
            "book_title": args.title,
        })

        try:
            full_novel = novel_logger.merge_novel(args.title)
        except FileNotFoundError as e:
            print(f"[错误] 未找到小说内容: {e}")
            print("请先使用 --create 模式生成小说")
            sys.exit(1)

        # 初始化转换器
        converter = Converter({})
        metadata = {"title": args.title}

        print(f"\n{'='*50}")
        print(f"📦 开始导出: {args.title}")
        print(f"{'='*50}")

        exported_files = []

        if args.export_markdown:
            # Markdown 导出（即纯文本，去除 Markdown 标记）
            txt_content = converter.convert_to_txt(full_novel)
            from src.utils import safe_filename
            md_path = converter.output_dir / f"{safe_filename(args.title)}.txt"
            md_path.parent.mkdir(parents=True, exist_ok=True)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(txt_content)
            exported_files.append(f"  ✅ Markdown/TXT: {md_path}")
            print(f"  ✅ Markdown 导出完成: {md_path}")

        if args.export_epub:
            try:
                epub_path = converter.convert_to_epub(full_novel, metadata)
                exported_files.append(f"  ✅ EPUB: {epub_path}")
                print(f"  ✅ EPUB 导出完成: {epub_path}")
            except ImportError:
                print("  ❌ EPUB 导出需要 ebooklib 库，请运行: pip install ebooklib")

        if args.export_txt:
            txt_content = converter.convert_to_txt(full_novel)
            from src.utils import safe_filename
            txt_path = converter.output_dir / f"{safe_filename(args.title)}_plain.txt"
            txt_path.parent.mkdir(parents=True, exist_ok=True)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(txt_content)
            exported_files.append(f"  ✅ TXT: {txt_path}")
            print(f"  ✅ TXT 导出完成: {txt_path}")

        if args.batch_export:
            print("\n  📦 批量导出所有格式...")
            results = converter.convert_to_all(full_novel, metadata)
            for fmt, path in results.items():
                exported_files.append(f"  ✅ {fmt.upper()}: {path}")
                print(f"  ✅ {fmt.upper()} 导出完成: {path}")

        print(f"\n{'='*50}")
        print(f"📊 导出完成！共 {len(exported_files)} 个文件")
        for f in exported_files:
            print(f"    {f}")
        print(f"{'='*50}")
        return

    # ── 创作模式 ──
    if args.create:
        from src.create import create_novel, resume_create, preview_outline

        if not args.title:
            parser.error("创作模式需要 --title 参数指定作品标题")

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
            sys.exit(1)
        return

    # 检查必需参数
    if not args.input and not args.create:
        parser.error("--input/-i 参数是必需的（除非使用 --clear-cache、--memory-status 或 --create）")

    # 显示初始内存状态
    print("=" * 60)
    print("[启动] Story Wiki - AI 驱动的故事知识库生成器")
    print("=" * 60)
    print_memory_status()

    # Step 1: 读取文本
    print(f"\n[1/3] 读取文本: {args.input}")
    try:
        text = extract_text(args.input)
    except (FileNotFoundError, ValueError) as e:
        print(f"[错误] {e}")
        sys.exit(1)

    print(f"      读取完成，共 {len(text)} 字")
    print_memory_status()

    # Step 2: AI 分析（自动判断是否分章）
    use_split = not args.no_split and len(text) > CHAPTER_THRESHOLD

    if args.incremental:
        if use_split:
            print(f"\n[2/3] 启用增量分章分析...")
            try:
                analysis = analyze_chaptered_incremental(
                    text=text,
                    title=args.title,
                    chunk_size=args.chunk_size,
                    start_chapter=args.start_chapter,
                    end_chapter=args.end_chapter,
                    use_cache=not args.no_cache,
                )
            except (ValueError, RuntimeError) as e:
                print(f"[错误] {e}")
                sys.exit(1)
        else:
            print(f"\n[2/3] 启用增量分析...")
            try:
                from src.pipeline import detect_existing_analysis, build_initial_context_for_incremental
                existing = detect_existing_analysis(args.title)
                if existing["exists"]:
                    print(f"       检测到已有分析结果：{len(existing['characters'])} 人物, {len(existing['settings'])} 设定")
                analysis = analyze_text(text, title=args.title)
                # 合并新旧结果
                from src.pipeline import merge_characters, merge_settings, merge_events
                analysis["characters"] = merge_characters(existing["characters"], analysis.get("characters", []))
                analysis["settings"] = merge_settings(existing["settings"], analysis.get("settings", []))
                analysis["events"] = merge_events(existing["events"], analysis.get("events", []))
                analysis["incremental"] = True
            except (ValueError, RuntimeError) as e:
                print(f"[错误] {e}")
                sys.exit(1)
    elif use_split:
        print(f"\n[2/3] 文本较长（>{CHAPTER_THRESHOLD}字），启用分章分析...")
        try:
            analysis = analyze_chaptered(
                text=text,
                title=args.title,
                chunk_size=args.chunk_size,
                use_cache=not args.no_cache,
            )
        except (ValueError, RuntimeError) as e:
            print(f"[错误] {e}")
            sys.exit(1)
    else:
        print(f"\n[2/3] 正在调用 AI 分析...")
        try:
            analysis = analyze_text(text, title=args.title)
        except (ValueError, RuntimeError) as e:
            print(f"[错误] {e}")
            sys.exit(1)

    title = analysis.get("title") or "未命名"
    chars = analysis.get("characters", [])
    settings = analysis.get("settings", [])
    events = analysis.get("events", [])
    print(f"\n      分析完成: 「{title}」")
    print(f"      人物: {len(chars)} 个 | 设定: {len(settings)} 个 | 事件: {len(events)} 个")
    print_memory_status()

    # dry-run 模式：只打印 JSON
    if args.dry_run:
        import json
        print("\n--- AI 分析结果 (JSON) ---")
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
        return

    # Step 3: 生成 Obsidian 笔记
    output_dir = Path(args.output) if args.output else VAULT_DIR
    print(f"\n[3/3] 生成 Obsidian 笔记到: {output_dir}")
    try:
        if args.incremental or analysis.get("incremental"):
            files = generate_vault_incremental(analysis, output_dir)
        else:
            files = generate_vault(analysis, output_dir)
    except Exception as e:
        print(f"[错误] 生成笔记失败: {e}")
        sys.exit(1)

    print(f"      生成完成！共 {len(files)} 个文件:")
    for f in files:
        print(f"        - {f}")

    print(f"\n[完成] 用 Obsidian 打开 {output_dir} 查看结果")
    print("=" * 60)
    print_memory_status()


if __name__ == "__main__":
    main()
