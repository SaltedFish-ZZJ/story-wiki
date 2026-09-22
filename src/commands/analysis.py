"""分析命令：读取文本 → AI 分析 → 生成 Obsidian 笔记。"""
import sys
from pathlib import Path

from src.config import CHAPTER_THRESHOLD, VAULT_DIR, print_memory_status
from src.extractor import extract_text
from src.analyzer import analyze_text
from src.pipeline import analyze_chaptered, analyze_chaptered_incremental
from src.generator import generate_vault, generate_vault_incremental


def run_analysis(args):
    """执行分析管线（原有默认流程）。"""
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

    # Step 2: AI 分析
    use_split = not args.no_split and len(text) > CHAPTER_THRESHOLD

    if args.incremental:
        if use_split:
            print("\n[2/3] 启用增量分章分析...")
            try:
                result = analyze_chaptered_incremental(text=text, title=args.title, chunk_size=args.chunk_size)
                analysis = {"characters": [], "settings": [], "events": [], "incremental": True}
                analysis.update(result)
            except (ValueError, RuntimeError) as e:
                print(f"[错误] {e}")
                sys.exit(1)
        else:
            print("\n[2/3] 启用增量分析...")
            try:
                existing = _load_existing(args.title)
                analysis = analyze_text(text, title=args.title)
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
            analysis = analyze_chaptered(text=text, title=args.title, chunk_size=args.chunk_size, use_cache=not args.no_cache)
        except (ValueError, RuntimeError) as e:
            print(f"[错误] {e}")
            sys.exit(1)
    else:
        print("\n[2/3] 正在调用 AI 分析...")
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

    # dry-run 模式
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
    except (RuntimeError, OSError, ValueError) as e:
        print(f"[错误] 生成笔记失败: {e}")
        sys.exit(1)

    print(f"      生成完成！共 {len(files)} 个文件:")
    for f in files:
        print(f"        - {f}")

    print(f"\n[完成] 用 Obsidian 打开 {output_dir} 查看结果")
    print("=" * 60)
    print_memory_status()


def _load_existing(title):
    """加载已有分析结果（用于增量模式）。"""
    from src.pipeline import detect_existing_analysis
    return detect_existing_analysis(title)
