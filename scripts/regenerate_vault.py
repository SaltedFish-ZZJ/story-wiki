"""从现有 Vault 读取卡片数据，用新的子文件夹结构重新生成笔记。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.vault_manager import VaultManager
from src.generator import generate_vault
from src.logging_setup import get_logger

logger = get_logger("regenerate")

VAULT_DIR = Path(r"D:\Obsidian_Work\story_wiki")
BOOK_TITLE = "富爸爸穷爸爸"


def main():
    # 1. 加载现有卡片
    vm = VaultManager({"vault_dir": str(VAULT_DIR), "book_title": BOOK_TITLE})
    cards = vm.load_all_cards()
    
    characters = cards["characters"]
    settings = cards["settings"]
    events = cards["events"]
    
    logger.info(f"加载完成: {len(characters)} 人物, {len(settings)} 设定, {len(events)} 事件")
    
    # 2. 构建 analysis dict
    analysis = {
        "title": BOOK_TITLE,
        "characters": characters,
        "settings": settings,
        "events": events,
        "summary": "《富爸爸穷爸爸》通过作者罗伯特·清崎的成长经历，对比了其亲生父亲（穷爸爸）与朋友之父（富爸爸）截然不同的金钱观与人生哲学。",
    }
    
    # 3. 删除旧的 .md 文件（保留 .incremental_state.json）
    book_dir = VAULT_DIR / BOOK_TITLE
    deleted = 0
    for md_file in book_dir.rglob("*.md"):
        md_file.unlink()
        deleted += 1
    logger.info(f"已删除 {deleted} 个旧 .md 文件")
    
    # 4. 重新生成
    files = generate_vault(analysis, VAULT_DIR)
    logger.info(f"已生成 {len(files)} 个文件")
    
    # 5. 验证子文件夹结构
    for f in files:
        rel = Path(f).relative_to(VAULT_DIR)
        logger.info(f"  {rel}")


if __name__ == "__main__":
    main()
