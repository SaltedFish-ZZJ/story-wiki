"""项目管理命令：列出作品、查看详情、跨作品搜索。"""
import sys


def run_project(args):
    """执行项目管理命令。"""
    from src.project_manager import ProjectManager
    pm = ProjectManager()

    if args.list_books:
        _list_books(pm)
    elif args.book_info:
        _book_info(pm, args.book_info)
    elif args.cross_search:
        _cross_search(pm, args.cross_search)
    elif args.similar_characters:
        _similar_characters(pm)


def _list_books(pm):
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


def _book_info(pm, title):
    summary = pm.get_book_summary(title)
    if not summary:
        print(f"作品不存在或读取失败: {title}")
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


def _cross_search(pm, keyword):
    results = pm.search_cross_book(keyword)
    if not results:
        print(f"未找到包含「{keyword}」的卡片。")
    else:
        print(f"\n跨作品搜索「{keyword}」结果：")
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


def _similar_characters(pm):
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
