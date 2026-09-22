"""导出命令：将已生成的小说导出为各种格式。"""
import sys

from src.utils import safe_filename


def run_export(args):
    """执行格式导出命令。"""
    from src.novel_logger import NovelLogger
    from src.converter import Converter

    if not args.title:
        print("[错误] 导出命令需要 --title 参数指定作品标题")
        sys.exit(1)

    # 初始化 NovelLogger 获取小说内容
    novel_logger = NovelLogger({"book_title": args.title})

    try:
        full_novel = novel_logger.merge_novel(args.title)
    except FileNotFoundError as e:
        print(f"[错误] 未找到小说内容: {e}")
        print("请先使用 --create 模式生成小说")
        sys.exit(1)

    # 初始化转换器
    converter = Converter({})
    metadata = {"title": args.title}

    print(f"\n{'=' * 50}")
    print(f"开始导出: {args.title}")
    print(f"{'=' * 50}")

    exported_files = []

    if args.export_markdown:
        txt_content = converter.convert_to_txt(full_novel)
        md_path = converter.output_dir / f"{safe_filename(args.title)}.txt"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(txt_content)
        exported_files.append(f"  Markdown/TXT: {md_path}")
        print(f"  Markdown 导出完成: {md_path}")

    if args.export_epub:
        try:
            epub_path = converter.convert_to_epub(full_novel, metadata)
            exported_files.append(f"  EPUB: {epub_path}")
            print(f"  EPUB 导出完成: {epub_path}")
        except ImportError:
            print("  EPUB 导出需要 ebooklib 库，请运行: pip install ebooklib")

    if args.export_txt:
        txt_content = converter.convert_to_txt(full_novel)
        txt_path = converter.output_dir / f"{safe_filename(args.title)}_plain.txt"
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt_content)
        exported_files.append(f"  TXT: {txt_path}")
        print(f"  TXT 导出完成: {txt_path}")

    if args.batch_export:
        print("\n  批量导出所有格式...")
        results = converter.convert_to_all(full_novel, metadata)
        for fmt, path in results.items():
            exported_files.append(f"  {fmt.upper()}: {path}")
            print(f"  {fmt.upper()} 导出完成: {path}")

    print(f"\n{'=' * 50}")
    print(f"导出完成！共 {len(exported_files)} 个文件")
    for f in exported_files:
        print(f"    {f}")
    print(f"{'=' * 50}")
