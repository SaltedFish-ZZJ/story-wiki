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

from src.config import CHAPTER_THRESHOLD, CHAPTER_CHUNK_SIZE, VAULT_DIR
from src.extractor import extract_text
from src.analyzer import analyze_text
from src.pipeline import analyze_chaptered, analyze_chaptered_incremental
from src.generator import generate_vault, generate_vault_incremental


def main():
    parser = argparse.ArgumentParser(
        description="Story Wiki - AI 驱动的故事知识库生成器"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
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

    args = parser.parse_args()

    # Step 1: 读取文本
    print(f"[1/3] 读取文本: {args.input}")
    try:
        text = extract_text(args.input)
    except (FileNotFoundError, ValueError) as e:
        print(f"[错误] {e}")
        sys.exit(1)

    print(f"      读取完成，共 {len(text)} 字")

    # Step 2: AI 分析（自动判断是否分章）
    use_split = not args.no_split and len(text) > CHAPTER_THRESHOLD

    if args.incremental:
        if use_split:
            print(f"[2/3] 启用增量分章分析...")
            try:
                analysis = analyze_chaptered_incremental(
                    text=text,
                    title=args.title,
                    chunk_size=args.chunk_size,
                    start_chapter=args.start_chapter,
                    end_chapter=args.end_chapter,
                )
            except (ValueError, RuntimeError) as e:
                print(f"[错误] {e}")
                sys.exit(1)
        else:
            print(f"[2/3] 启用增量分析...")
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
        print(f"[2/3] 文本较长（>{CHAPTER_THRESHOLD}字），启用分章分析...")
        try:
            analysis = analyze_chaptered(
                text=text,
                title=args.title,
                chunk_size=args.chunk_size,
            )
        except (ValueError, RuntimeError) as e:
            print(f"[错误] {e}")
            sys.exit(1)
    else:
        print(f"[2/3] 正在调用 AI 分析...")
        try:
            analysis = analyze_text(text, title=args.title)
        except (ValueError, RuntimeError) as e:
            print(f"[错误] {e}")
            sys.exit(1)

    title = analysis.get("title") or "未命名"
    chars = analysis.get("characters", [])
    settings = analysis.get("settings", [])
    events = analysis.get("events", [])
    print(f"      分析完成: 「{title}」")
    print(f"      人物: {len(chars)} 个 | 设定: {len(settings)} 个 | 事件: {len(events)} 个")

    # dry-run 模式：只打印 JSON
    if args.dry_run:
        import json
        print("\n--- AI 分析结果 (JSON) ---")
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
        return

    # Step 3: 生成 Obsidian 笔记
    output_dir = Path(args.output) if args.output else VAULT_DIR
    print(f"[3/3] 生成 Obsidian 笔记到: {output_dir}")
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


if __name__ == "__main__":
    main()
