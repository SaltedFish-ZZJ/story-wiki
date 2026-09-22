"""
Story Wiki - 交互式分析 Agent
启动后进入对话模式，丢文本或文件路径即可自动分析。
支持长文本自动分章。
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import CHAPTER_THRESHOLD, VAULT_DIR, INPUT_DIR, init_runtime
from src.extractor import extract_text
from src.analyzer import analyze_text
from src.pipeline import analyze_chaptered, clear_cache
from src.generator import generate_vault


# 启动时显式初始化（创建目录）
init_runtime(verbose=False)


HELP_TEXT = """
╔══════════════════════════════════════════════════╗
║         Story Wiki 分析 Agent v0.6               ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  使用方式：                                       ║
║    1. 输入文件路径 → 自动读取并分析               ║
║    2. 直接粘贴文本 → 自动分析                     ║
║    3. 长文本自动分章处理（逐章分析+合并去重）      ║
║    4. 输入命令：                                  ║
║       /help    — 显示帮助                         ║
║       /list    — 列出已分析的作品                  ║
║       /vault   — 打开 vault 目录                  ║
║       /cache   — 清除分析缓存                     ║
║       /growth  — 分析角色成长曲线                 ║
║       /export  — 导出小说为各种格式               ║
║       /quit    — 退出                             ║
║                                                  ║
╚══════════════════════════════════════════════════╝
"""


def is_file_path(text: str) -> bool:
    """判断输入是否像一个文件路径。"""
    text = text.strip().strip('"').strip("'")
    if len(text) > 200:
        return False
    path = Path(text)
    return path.exists() and path.is_file()


def list_analyzed_books():
    """列出 vault 中已分析的作品。"""
    if not VAULT_DIR.exists():
        print("[vault 目录不存在]")
        return
    books = [d for d in VAULT_DIR.iterdir() if d.is_dir() and d.name != ".obsidian"]
    if not books:
        print("[还没有分析过任何作品]")
        return
    print("\n已分析的作品：")
    for book in sorted(books):
        char_dir = book / "characters"
        char_count = len(list(char_dir.glob("*.md"))) if char_dir.exists() else 0
        print(f"  📖 {book.name} ({char_count} 个人物)")


def get_available_books():
    """获取可用的作品列表。"""
    if not VAULT_DIR.exists():
        return []
    return [d.name for d in VAULT_DIR.iterdir() if d.is_dir() and d.name != ".obsidian"]


def handle_growth_command(args_text: str):
    """处理 /growth 命令 - 分析角色成长曲线。"""
    from src.character_growth import CharacterGrowthTracker
    import re

    # 解析参数: /growth [作品名] [人物名]
    parts = args_text.strip().split()
    book_name = None
    char_name = None

    if len(parts) >= 2:
        book_name = parts[1]
    if len(parts) >= 3:
        char_name = parts[2]

    # 如果没有指定作品名，让用户选择
    if not book_name:
        books = get_available_books()
        if not books:
            print("❌ 没有可分析的作品，请先分析一个作品")
            return
        print("\n可分析的作品：")
        for i, book in enumerate(books, 1):
            print(f"  {i}. {book}")
        try:
            choice = input("\n选择作品编号 (或输入作品名): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(books):
                book_name = books[int(choice) - 1]
            else:
                book_name = choice
        except (EOFError, KeyboardInterrupt):
            print("\n取消操作")
            return

    tracker = CharacterGrowthTracker(VAULT_DIR, book_name)

    if char_name:
        # 分析指定角色
        curve = tracker.get_character_growth_curve(char_name)
        if curve is None:
            print(f"❌ 人物不存在: {char_name}")
            return

        print(f"\n{'═' * 60}")
        print(f"  {curve.character_name} 成长分析报告")
        print(f"{'═' * 60}")
        print(f"  摘要: {curve.summary}")
        print(f"  趋势: {curve.overall_trend}")
        print(f"  成长事件数: {len(curve.growth_events)}")
        print(f"  成长阶段数: {len(curve.growth_phases)}")

        if curve.growth_phases:
            print(f"\n  成长阶段:")
            print("-" * 60)
            for i, phase in enumerate(curve.growth_phases, 1):
                print(f"  阶段 {i}: {phase.get('type', '未知')}")
                print(f"    范围: {phase.get('start_chapter', '?')} - {phase.get('end_chapter', '?')}")
                print(f"    事件数: {phase.get('events_count', 0)}")
        print(f"{'═' * 60}")
    else:
        # 分析所有主要人物
        vault_manager = tracker.vault_manager
        cards = vault_manager.load_all_cards()
        characters = cards.get("characters", [])

        if not characters:
            print("❌ 知识库中没有人��信息")
            return

        print(f"\n{'═' * 60}")
        print(f"  {book_name} 全部角色成长分析")
        print(f"{'═' * 60}")

        analyzed_count = 0
        for char_data in characters:
            char_name = char_data.get("name", "")
            if not char_name:
                continue

            curve = tracker.get_character_growth_curve(char_name)
            if curve is None or len(curve.growth_events) == 0:
                continue

            analyzed_count += 1
            print(f"\n  👤 {char_name}")
            print(f"    摘要: {curve.summary}")
            print(f"    趋势: {curve.overall_trend}")
            print(f"    成长事件数: {len(curve.growth_events)}")

        if analyzed_count == 0:
            print("\n  暂无角色成长数据")
        print(f"\n{'═' * 60}")


def handle_export_command(args_text: str):
    """处理 /export 命令 - 导出小说为各种格式。"""
    from src.novel_logger import NovelLogger
    from src.converter import Converter

    # 解析参数: /export [作品名] [格式]
    parts = args_text.strip().split()
    book_name = None
    export_format = "all"  # 默认导出所有格式

    if len(parts) >= 2:
        book_name = parts[1]
    if len(parts) >= 3:
        export_format = parts[2].lower()

    # 如果没有指定作品名，让用户选择
    if not book_name:
        books = get_available_books()
        if not books:
            print("❌ 没有可导出的作品，请先分析并创作一个作品")
            return
        print("\n可导出的作品：")
        for i, book in enumerate(books, 1):
            print(f"  {i}. {book}")
        try:
            choice = input("\n选择作品编号 (或输入作品名): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(books):
                book_name = books[int(choice) - 1]
            else:
                book_name = choice
        except (EOFError, KeyboardInterrupt):
            print("\n取消操作")
            return

    # 选择导出格式
    if export_format not in ("epub", "txt", "md", "all"):
        print(f"❌ 不支持的格式: {export_format}")
        print("   支持的格式: epub, txt, md, all")
        return

    # 初始化 NovelLogger 获取小说内容
    novel_logger = NovelLogger({
        "book_title": book_name,
    })

    try:
        full_novel = novel_logger.merge_novel(book_name)
    except FileNotFoundError as e:
        print(f"❌ 未找到小说内容: {e}")
        print("请先使用 --create 模式生成小说")
        return

    # 初始化转换器
    converter = Converter({})
    metadata = {"title": book_name}

    print(f"\n{'='*50}")
    print(f"📦 开始导出: {book_name}")
    print(f"{'='*50}")

    exported_files = []

    if export_format in ("md", "all"):
        # Markdown/TXT 导出
        txt_content = converter.convert_to_txt(full_novel)
        from src.utils import safe_filename
        md_path = converter.output_dir / f"{safe_filename(book_name)}.txt"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(txt_content)
        exported_files.append(f"  ✅ TXT: {md_path}")
        print(f"  ✅ TXT 导出完成: {md_path}")

    if export_format in ("epub", "all"):
        try:
            epub_path = converter.convert_to_epub(full_novel, metadata)
            exported_files.append(f"  ✅ EPUB: {epub_path}")
            print(f"  ✅ EPUB 导出完成: {epub_path}")
        except ImportError:
            print("  ❌ EPUB 导出需要 ebooklib 库，请运行: pip install ebooklib")

    if export_format in ("txt", "all"):
        txt_content = converter.convert_to_txt(full_novel)
        from src.utils import safe_filename
        txt_path = converter.output_dir / f"{safe_filename(book_name)}_plain.txt"
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt_content)
        exported_files.append(f"  ✅ TXT: {txt_path}")
        print(f"  ✅ TXT 导出完成: {txt_path}")

    if export_format == "all":
        # 平台格式
        platform_content = converter.convert_to_platform(full_novel, platform="platform")
        from src.utils import safe_filename
        platform_path = converter.output_dir / f"{safe_filename(book_name)}_platform.txt"
        platform_path.parent.mkdir(parents=True, exist_ok=True)
        with open(platform_path, "w", encoding="utf-8") as f:
            f.write(platform_content)
        exported_files.append(f"  ✅ Platform: {platform_path}")
        print(f"  ✅ Platform 导出完成: {platform_path}")

    print(f"\n{'='*50}")
    print(f"📊 导出完成！共 {len(exported_files)} 个文件")
    for f in exported_files:
        print(f"    {f}")
    print(f"{'='*50}")


def analyze_and_generate(text: str, title: str = None):
    """执行分析 + 生成的完整流程。自动判断是否分章。"""
    print(f"\n{'='*50}")
    print(f"📝 文本长度: {len(text)} 字")
    print(f"{'='*50}")

    # 自动判断是否分章
    use_split = len(text) > CHAPTER_THRESHOLD

    if use_split:
        print(f"\n📖 文本较长（>{CHAPTER_THRESHOLD}字），启用分章分析...")
        try:
            analysis = analyze_chaptered(text=text, title=title)
        except (ValueError, RuntimeError) as e:
            print(f"❌ 分析失败: {e}")
            return
    else:
        # Step 1: AI 分析（单次）
        print("\n🤖 正在调用 DeepSeek 分析...")
        try:
            analysis = analyze_text(text, title=title)
        except (ValueError, RuntimeError) as e:
            print(f"❌ 分析失败: {e}")
            return

    title = analysis.get("title", "未命名")
    characters = analysis.get("characters", [])
    settings = analysis.get("settings", [])
    summary = analysis.get("summary", "")

    # 打印分析结果
    print(f"\n✅ 分析完成: 「{title}」")
    print(f"   人物: {len(characters)} 个")
    for c in characters:
        name = c.get("name", "?")
        identity = c.get("identity") or ""
        rels = c.get("relationships", [])
        rel_str = ", ".join([f"{r['target']}({r['nature']})" for r in rels[:3]])
        if len(rels) > 3:
            rel_str += f" +{len(rels)-3}"
        print(f"   👤 {name} — {identity}")
        if rel_str:
            print(f"      └─ 关系: {rel_str}")

    print(f"\n   设定: {len(settings)} 个")
    for s in settings:
        print(f"   🏛️ {s.get('name', '?')} ({s.get('type', '?')})")

    if summary:
        print(f"\n   📋 摘要: {summary}")

    # 询问是否生成 Obsidian 笔记
    print(f"\n{'='*50}")
    answer = input("💾 生成 Obsidian 笔记到 vault？(y/n/自定义标题): ").strip()

    if answer.lower() in ('n', 'no', '否'):
        print("跳过生成。")
        return

    custom_title = None
    if answer.lower() not in ('y', 'yes', '是', ''):
        custom_title = answer
        analysis["title"] = custom_title
        title = custom_title

    # 生成笔记
    print(f"\n📂 生成 Obsidian 笔记到: {VAULT_DIR}")
    try:
        files = generate_vault(analysis, VAULT_DIR)
    except (RuntimeError, OSError) as e:
        print(f"❌ 生成失败: {e}")
        return

    print(f"✅ 生成完成！共 {len(files)} 个文件:")
    for f in files:
        fname = Path(f).name
        print(f"   📄 {fname}")

    print(f"\n🔗 用 Obsidian 打开 {VAULT_DIR} 查看 Graph View")


def main():
    print(HELP_TEXT)

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见 👋")
            break

        if not user_input:
            continue

        # 命令处理
        if user_input.startswith('/'):
            cmd = user_input.lower().split()[0] if user_input.strip() else ''
            if cmd in ('/quit', '/exit', '/q'):
                print("再见 👋")
                break
            elif cmd in ('/help', '/h'):
                print(HELP_TEXT)
            elif cmd == '/list':
                list_analyzed_books()
            elif cmd == '/vault':
                print(f"Vault 路径: {VAULT_DIR}")
                print(f"用 Obsidian 打开此目录即可查看")
            elif cmd == '/cache':
                clear_cache()
            elif cmd == '/growth':
                handle_growth_command(user_input)
            elif cmd == '/export':
                handle_export_command(user_input)
            else:
                print(f"未知命令: {user_input}，输入 /help 查看帮助")
            continue

        # 文件路径模式
        if is_file_path(user_input):
            file_path = user_input.strip().strip('"').strip("'")
            print(f"📁 检测到文件: {file_path}")
            try:
                text = extract_text(file_path)
            except (FileNotFoundError, ValueError) as e:
                print(f"❌ {e}")
                continue

            # 用文件名作为默认标题
            default_title = Path(file_path).stem
            analyze_and_generate(text, title=default_title)
            continue

        # 直接文本模式（输入较长时认为是待分析文本）
        if len(user_input) > 100:
            analyze_and_generate(user_input)
        else:
            print("输入太短，无法分析。请输入文件路径或粘贴较长的文本。")
            print("提示: 输入 /help 查看帮助")


if __name__ == "__main__":
    main()
