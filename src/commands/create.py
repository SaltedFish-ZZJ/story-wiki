"""创作命令：从知识库生成小说。"""
import sys


def run_create(args):
    """执行创作模式命令。"""
    from src.create import create_novel, resume_create, preview_outline

    if not args.title:
        print("[错误] 创作模式需要 --title 参数指定作品标题")
        sys.exit(1)

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
            strict_quality=args.strict_quality,
        )

    if not result["success"]:
        sys.exit(1)
