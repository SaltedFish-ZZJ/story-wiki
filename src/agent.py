"""
Story Wiki - 交互式分析 Agent
启动后进入对话模式，丢文本或文件路径即可自动分析。
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import VAULT_DIR, INPUT_DIR
from src.extractor import extract_text
from src.analyzer import analyze_text
from src.generator import generate_vault


HELP_TEXT = """
╔══════════════════════════════════════════════════╗
║           Story Wiki 分析 Agent v0.1             ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  使用方式：                                       ║
║    1. 输入文件路径 → 自动读取并分析               ║
║    2. 直接粘贴文本 → 自动分析                     ║
║    3. 输入命令：                                  ║
║       /help    — 显示帮助                         ║
║       /list    — 列出已分析的作品                  ║
║       /vault   — 打开 vault 目录                  ║
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


def analyze_and_generate(text: str, title: str = None):
    """执行分析 + 生成的完整流程。"""
    print(f"\n{'='*50}")
    print(f"📝 文本长度: {len(text)} 字")
    print(f"{'='*50}")

    # Step 1: AI 分析
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
    except Exception as e:
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
            cmd = user_input.lower()
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
