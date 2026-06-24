"""
Phase 3 模块独立测试脚本
单独测试 vault_manager、plot_generator、chapter_generator、novel_logger 四个模块。

用法：
    python test_phase3.py                  # 测试所有模块
    python test_phase3.py --module vault   # 只测试 vault_manager
    python test_phase3.py --module plot    # 只测试 plot_generator
    python test_phase3.py --module chapter # 只测试 chapter_generator
    python test_phase3.py --module logger  # 只测试 novel_logger
    python test_phase3.py --book 红楼梦    # 指定作品名
"""
import argparse
import json
import sys
from pathlib import Path

# 确保项目根目录在 Python path 中
sys.path.insert(0, str(Path(__file__).parent))

from src.config import VAULT_DIR, print_memory_status


def test_vault_manager(book_title: str):
    """测试知识库管理模块。"""
    print("=" * 60)
    print("[测试] vault_manager - 知识库管理模块")
    print("=" * 60)

    from src.vault_manager import VaultManager

    # 初始化
    manager = VaultManager({"vault_dir": VAULT_DIR, "book_title": book_title})
    print(f"[初始化] Vault 目录: {VAULT_DIR}")
    print(f"[初始化] 作品: {book_title}")

    # 1. 加载所有卡片
    print("\n[1] 加载所有卡片...")
    all_cards = manager.load_all_cards()
    print(f"    人物: {len(all_cards['characters'])} 个")
    print(f"    设定: {len(all_cards['settings'])} 个")
    print(f"    事件: {len(all_cards['events'])} 个")

    # 显示前 3 个人物
    if all_cards['characters']:
        print("\n    前 3 个人物:")
        for char in all_cards['characters'][:3]:
            name = char.get('name', '未知')
            identity = char.get('identity', '无身份')[:30]
            print(f"      - {name}: {identity}")

    # 2. 加载单个人物
    if all_cards['characters']:
        first_name = all_cards['characters'][0].get('name', '')
        print(f"\n[2] 加载单个人物: {first_name}")
        char = manager.load_character(first_name)
        if char:
            print(f"    身份: {char.identity}")
            print(f"    性格: {char.personality[:50] if char.personality else '无'}...")
            print(f"    关系数: {len(char.relationships)}")

    # 3. 搜索功能
    print(f"\n[3] 搜索关键词: '玉'")
    results = manager.search_cards("玉")
    print(f"    找到人物: {len(results.get('characters', []))} 个")
    print(f"    找到设定: {len(results.get('settings', []))} 个")
    print(f"    找到事件: {len(results.get('events', []))} 个")

    # 4. 获取时间线
    print(f"\n[4] 获取事件时间线...")
    timeline = manager.get_timeline()
    print(f"    时间线事件数: {len(timeline)}")
    if timeline:
        print("    前 3 个事件:")
        for evt in timeline[:3]:
            name = evt.get('name', '未知')
            time = evt.get('time', '未知时间')
            print(f"      - [{time}] {name}")

    print("\n[完成] vault_manager 测试通过 OK")
    return all_cards


def test_plot_generator(book_title: str, knowledge_base: dict = None):
    """测试情节生成模块。"""
    print("\n" + "=" * 60)
    print("[测试] plot_generator - 情节生成模块")
    print("=" * 60)

    from src.plot_generator import PlotGenerator

    # 初始化
    generator = PlotGenerator()
    print(f"[初始化] 作品: {book_title}")

    # 如果没有提供知识库，先加载
    if knowledge_base is None:
        from src.vault_manager import VaultManager
        manager = VaultManager({"vault_dir": VAULT_DIR, "book_title": book_title})
        knowledge_base = manager.load_all_cards()

    char_count = len(knowledge_base.get('characters', []))
    setting_count = len(knowledge_base.get('settings', []))
    event_count = len(knowledge_base.get('events', []))
    print(f"[知识库] 人物: {char_count} | 设定: {setting_count} | 事件: {event_count}")

    if char_count == 0:
        print("[跳过] 知识库为空，无法生成情节大纲")
        return None

    # 1. 生成情节大纲
    print("\n[1] 生成情节大纲（调用 DeepSeek API）...")
    print("    ... 等待 API 响应...")

    try:
        outline = generator.generate_outline(book_title, knowledge_base)
        print(f"\n    [OK] 大纲生成成功!")
        print(f"    标题: {outline.title}")
        print(f"    主题: {outline.theme}")
        print(f"    核心冲突: {outline.conflict[:60]}...")
        print(f"    结局走向: {outline.ending_direction[:60]}...")

        # 显示起承转合结构
        print("\n    起承转合结构:")
        for phase, data in outline.structure.items():
            title = data.get('title', '未命名')
            summary = data.get('summary', '无')[:40]
            print(f"      [{phase}] {title}: {summary}...")

        return outline

    except Exception as e:
        print(f"\n    FAIL 生成失败: {e}")
        return None


def test_chapter_generator(book_title: str, outline=None, knowledge_base: dict = None):
    """测试章节生成模块。"""
    print("\n" + "=" * 60)
    print("[测试] chapter_generator - 章节生成模块")
    print("=" * 60)

    from src.chapter_generator import ChapterGenerator

    # 初始化
    generator = ChapterGenerator()
    print(f"[初始化] 作品: {book_title}")

    # 如果没有提供知识库，先加载
    if knowledge_base is None:
        from src.vault_manager import VaultManager
        manager = VaultManager({"vault_dir": VAULT_DIR, "book_title": book_title})
        knowledge_base = manager.load_all_cards()

    # 如果没有大纲，先生成
    if outline is None:
        print("[跳过] 需要先生成情节大纲")
        return None

    # 1. 生成第 1 章
    print("\n[1] 生成第 1 章（调用 DeepSeek API）...")
    print("    ... 等待 API 响应...")

    context = {
        "characters": knowledge_base.get('characters', [])[:10],  # 只传前 10 个人物
        "settings": knowledge_base.get('settings', [])[:5],
        "events": [],
        "previous_chapters": [],
    }

    try:
        chapter = generator.generate_chapter(1, outline, context)
        print(f"\n    [OK] 第 1 章生成成功!")
        print(f"    标题: {chapter.title}")
        print(f"    字数: {chapter.word_count}")
        print(f"    出场人物: {', '.join(chapter.characters_involved[:5])}")
        print(f"    关键事件: {', '.join(chapter.events_happened[:3])}")

        # 显示前 200 字
        preview = chapter.content[:200].replace('\n', '\n    ')
        print(f"\n    内容预览:\n    {preview}...")

        # 2. 质量检查
        print("\n[2] 质量检查...")
        chars = []
        from src.interfaces import Character
        for c in knowledge_base.get('characters', [])[:5]:
            chars.append(Character(
                name=c.get('name', ''),
                identity=c.get('identity', ''),
                personality=c.get('personality', ''),
            ))

        check_result = generator.quality_check(chapter, chars)
        print(f"    检查结果: {'OK 通过' if check_result.get('passed') else '[FAIL] 未通过'}")
        if check_result.get('issues'):
            print(f"    问题数: {len(check_result['issues'])}")
            for issue in check_result['issues'][:3]:
                print(f"      - {issue.get('type', '未知')}: {issue.get('detail', '')[:50]}")

        return chapter

    except Exception as e:
        print(f"\n    FAIL 生成失败: {e}")
        return None


def test_novel_logger(book_title: str, chapter=None):
    """测试日志记录模块。"""
    print("\n" + "=" * 60)
    print("[测试] novel_logger - 日志记录模块")
    print("=" * 60)

    from src.novel_logger import NovelLogger

    # 初始化
    logger = NovelLogger({"book_title": book_title})
    print(f"[初始化] 作品: {book_title}")
    print(f"[初始化] 输出目录: {logger.output_dir}")

    # 1. 获取当前进度
    print("\n[1] 获取写作进度...")
    progress = logger.get_progress(book_title)
    print(f"    总章节数: {progress.get('total_chapters', 0)}")
    print(f"    已完成章节: {progress.get('completed_chapters', 0)}")
    print(f"    总字数: {progress.get('total_words', 0)}")
    print(f"    最后更新: {progress.get('last_updated', '无')}")

    # 2. 保存章节（如果有）
    if chapter:
        print(f"\n[2] 保存第 1 章...")
        logger.save_chapter(1, chapter)
        print(f"    OK 已保存: {chapter.title}")

        # 重新获取进度
        progress = logger.get_progress(book_title)
        print(f"    更新后进度: {progress.get('completed_chapters', 0)} 章")

    # 3. 断点续写
    print(f"\n[3] 断点续写检查...")
    next_chapter = logger.resume_writing(book_title)
    print(f"    下一章编号: {next_chapter}")

    # 4. 知识库日志
    print(f"\n[4] 更新知识库日志...")
    logger.update_knowledge_log({
        "new_characters": ["测试人物A", "测试人物B"],
        "updated_characters": ["贾宝玉"],
        "new_events": ["测试事件1"],
        "new_settings": [],
    })
    print(f"    OK 知识库日志已更新")

    print("\n[完成] novel_logger 测试通过 OK")


def main():
    parser = argparse.ArgumentParser(description="Phase 3 模块独立测试")
    parser.add_argument("--module", "-m",
                        choices=["vault", "plot", "chapter", "logger", "all"],
                        default="all",
                        help="要测试的模块（默认: all）")
    parser.add_argument("--book", "-b",
                        default="红楼梦",
                        help="作品名（默认: 红楼梦）")
    parser.add_argument("--skip-api",
                        action="store_true",
                        help="跳过需要 API 调用的测试")

    args = parser.parse_args()

    print("=" * 60)
    print("Story Wiki - Phase 3 模块独立测试")
    print("=" * 60)
    print(f"作品: {args.book}")
    print(f"模块: {args.module}")
    print(f"跳过 API: {args.skip_api}")
    print_memory_status()

    # 测试结果
    results = {}

    # 测试 vault_manager
    if args.module in ["vault", "all"]:
        knowledge_base = test_vault_manager(args.book)
        results["vault_manager"] = "OK 通过"
    else:
        knowledge_base = None

    # 测试 plot_generator
    if args.module in ["plot", "all"] and not args.skip_api:
        outline = test_plot_generator(args.book, knowledge_base)
        results["plot_generator"] = "OK 通过" if outline else "[FAIL] 失败"
    else:
        outline = None
        if args.module in ["plot", "all"]:
            results["plot_generator"] = "SKIP 跳过（--skip-api）"

    # 测试 chapter_generator
    if args.module in ["chapter", "all"] and not args.skip_api:
        chapter = test_chapter_generator(args.book, outline, knowledge_base)
        results["chapter_generator"] = "OK 通过" if chapter else "[FAIL] 失败"
    else:
        chapter = None
        if args.module in ["chapter", "all"]:
            results["chapter_generator"] = "SKIP 跳过（--skip-api）"

    # 测试 novel_logger
    if args.module in ["logger", "all"]:
        test_novel_logger(args.book, chapter)
        results["novel_logger"] = "OK 通过"

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for module, result in results.items():
        print(f"  {module}: {result}")

    print_memory_status()
    print("\n测试完成！")


if __name__ == "__main__":
    main()
