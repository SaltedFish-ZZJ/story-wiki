"""成长曲线命令。"""
import sys
import json

from src.config import VAULT_DIR


def run_growth(args):
    """执行成长曲线相关命令。"""
    from src.character_growth import CharacterGrowthTracker

    if not args.title:
        print("[错误] 成长曲线命令需要 --title 参数指定作品标题")
        sys.exit(1)

    tracker = CharacterGrowthTracker(VAULT_DIR, args.title)

    if args.growth_curve:
        _show_growth_curve(tracker, args.growth_curve)
    elif args.growth_chart:
        _show_growth_chart(tracker, args.growth_chart)
    elif args.extract_growth:
        _extract_growth(tracker, args.input)
    elif args.growth_analysis is not None:
        _show_growth_analysis(tracker, args.growth_analysis)


def _show_growth_curve(tracker, char_name):
    curve = tracker.get_character_growth_curve(char_name)
    if curve is None:
        print(f"人物不存在: {char_name}")
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


def _show_growth_chart(tracker, char_name):
    chart_data = tracker.generate_growth_chart_data(char_name)
    if "error" in chart_data:
        print(f"错误: {chart_data['error']}")
        sys.exit(1)
    print(json.dumps(chart_data, ensure_ascii=False, indent=2))


def _extract_growth(tracker, input_path):
    if not input_path:
        print("提取成长事件需要 --input 参数指定分析结果文件")
        sys.exit(1)

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)

        growth_events = tracker.extract_growth_events_from_analysis(analysis)
        if growth_events:
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
    except (RuntimeError, OSError, ValueError) as e:
        print(f"提取成长事件失败: {e}")
        sys.exit(1)


def _show_growth_analysis(tracker, target_char):
    if target_char:
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
        _show_all_growth_analysis(tracker)


def _show_all_growth_analysis(tracker):
    vault_manager = tracker.vault_manager
    cards = vault_manager.load_all_cards()
    characters = cards.get("characters", [])

    if not characters:
        print("知识库中没有人物信息")
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

        print(f"\n  {char_name}")
        print(f"    摘要: {curve.summary}")
        print(f"    趋势: {curve.overall_trend}")
        print(f"    成长事件数: {event_count}")

    print(f"\n{'═' * 60}")
