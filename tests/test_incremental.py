"""
Story Wiki - 增量分析功能测试
测试增量分析的核心逻辑：检测、合并、写入。
"""
import json
import sys
from pathlib import Path

# 添加项目根目录到 Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import (
    detect_existing_analysis,
    build_initial_context_for_incremental,
    merge_characters,
    merge_settings,
    merge_events,
    _safe_filename
)
from src.generator import (
    _merge_character_data,
    _merge_setting_data,
    _merge_event_data
)


def test_merge_characters():
    """测试人物合并逻辑。"""
    print("测试人物合并...")

    existing = [
        {
            "name": "贾宝玉",
            "identity": "荣国府公子",
            "personality": "叛逆多情",
            "relationships": [{"target": "林黛玉", "nature": "恋人"}]
        }
    ]

    new_items = [
        {
            "name": "贾宝玉",
            "identity": "荣国府公子，衔玉而生",
            "relationships": [{"target": "薛宝钗", "nature": "妻子"}]
        }
    ]

    result = merge_characters(existing, new_items)

    assert len(result) == 1, "合并后应只有 1 个人物"
    assert result[0]["name"] == "贾宝玉"

    # 检查描述取更长的
    assert len(result[0]["identity"]) >= len(existing[0]["identity"]), "应取更长的描述"

    # 检查关系合并
    rel_targets = [r["target"] for r in result[0]["relationships"]]
    assert "林黛玉" in rel_targets, "应保留旧关系"
    assert "薛宝钗" in rel_targets, "应添加新关系"

    print("  [PASS] 人物合并测试通过")


def test_merge_settings():
    """测试设定合并逻辑。"""
    print("测试设定合并...")

    existing = [
        {
            "name": "大观园",
            "type": "地点",
            "description": "贾府花园"
        }
    ]

    new_items = [
        {
            "name": "大观园",
            "type": "地点",
            "description": "贾府花园，是贾宝玉和众姐妹的居住地"
        }
    ]

    result = merge_settings(existing, new_items)

    assert len(result) == 1, "合并后应只有 1 个设定"
    assert result[0]["name"] == "大观园"

    # 检查描述取更长的
    assert len(result[0]["description"]) >= len(existing[0]["description"]), "应取更长的描述"

    print("  [PASS] 设定合并测试通过")


def test_merge_events():
    """测试事件合并逻辑。"""
    print("测试事件合并...")

    existing = [
        {
            "name": "宝黛初见",
            "participants": ["贾宝玉", "林黛玉"],
            "cause": []
        }
    ]

    new_items = [
        {
            "name": "宝黛初见",
            "participants": ["贾宝玉", "林黛玉", "贾母"],
            "cause": ["黛玉进贾府"]
        }
    ]

    result = merge_events(existing, new_items)

    assert len(result) == 1, "合并后应只有 1 个事件"
    assert result[0]["name"] == "宝黛初见"

    # 检查参与者合并
    assert "贾母" in result[0]["participants"], "应添加新参与者"

    # 检查因果链合并
    assert "黛玉进贾府" in result[0]["cause"], "应添加新因果"

    print("  [PASS] 事件合并测试通过")


def test_merge_character_data():
    """测试人物数据合并（generator 模块）。"""
    print("测试人物数据合并（generator）...")

    old = {
        "name": "林黛玉",
        "identity": "林如海之女",
        "personality": "多愁善感",
        "aliases": ["颦儿"],
        "relationships": [{"target": "贾宝玉", "nature": "恋人"}]
    }

    new = {
        "name": "林黛玉",
        "identity": "林如海之女，贾母外孙女",
        "personality": "才情出众",
        "aliases": ["潇湘妃子"],
        "relationships": [{"target": "薛宝钗", "nature": "姐妹"}]
    }

    result = _merge_character_data(old, new)

    # 检查别名合并
    assert "颦儿" in result["aliases"], "应保留旧别名"
    assert "潇湘妃子" in result["aliases"], "应添加新别名"

    # 检查关系合并
    rel_targets = [r["target"] for r in result["relationships"]]
    assert "贾宝玉" in rel_targets, "应保留旧关系"
    assert "薛宝钗" in rel_targets, "应添加新关系"

    print("  [PASS] 人物数据合并测试通过")


def test_merge_setting_data():
    """测试设定数据合并（generator 模块）。"""
    print("测试设定数据合并（generator）...")

    old = {
        "name": "荣国府",
        "setting_type": "地点",
        "description": "贾府主宅",
        "related_characters": ["贾宝玉"]
    }

    new = {
        "name": "荣国府",
        "setting_type": "地点",
        "description": "贾府主宅，是贾政一家的居住地",
        "related_characters": ["贾政"]
    }

    result = _merge_setting_data(old, new)

    # 检查描述取更长的
    assert len(result["description"]) >= len(old["description"]), "应取更长的描述"

    # 检查关联人物合并
    assert "贾宝玉" in result["related_characters"], "应保留旧关联"
    assert "贾政" in result["related_characters"], "应添加新关联"

    print("  [PASS] 设定数据合并测试通过")


def test_merge_event_data():
    """测试事件数据合并（generator 模块）。"""
    print("测试事件数据合并（generator）...")

    old = {
        "name": "元妃省亲",
        "time": "元宵节",
        "participants": ["贾元春"],
        "cause": []
    }

    new = {
        "name": "元妃省亲",
        "time": None,
        "participants": ["贾元春", "贾宝玉"],
        "cause": ["建造大观园"]
    }

    result = _merge_event_data(old, new)

    # 检查时间保留旧的
    assert result["time"] == "元宵节", "应保留旧时间"

    # 检查参与者合并
    assert "贾宝玉" in result["participants"], "应添加新参与者"

    # 检查因果链合并
    assert "建造大观园" in result["cause"], "应添加新因果"

    print("  [PASS] 事件数据合并测试通过")


def test_build_initial_context():
    """测试初始上下文构建。"""
    print("测试初始上下文构建...")

    existing_data = {
        "exists": True,
        "chapters_analyzed": ["第1章", "第2章"],
        "characters": [
            {"name": "贾宝玉", "identity": "荣国府公子"}
        ],
        "settings": [
            {"name": "大观园", "type": "地点"}
        ],
        "events": [
            {"name": "宝黛初见", "time": "某日"}
        ]
    }

    chars, settings, events = build_initial_context_for_incremental(existing_data)

    assert len(chars) == 1, "应返回已有人物"
    assert len(settings) == 1, "应返回已有设定"
    assert len(events) == 1, "应返回已有事件"

    print("  [PASS] 初始上下文构建测试通过")


def test_safe_filename():
    """测试安全文件名生成。"""
    print("测试安全文件名生成...")

    assert _safe_filename("红楼梦") == "红楼梦"
    assert _safe_filename("第1章：甄士隐梦幻识通灵") == "第1章：甄士隐梦幻识通灵"
    assert _safe_filename('Test<>:"/\\|?*File') == "Test_________File"

    print("  [PASS] 安全文件名测试通过")


def run_all_tests():
    """运行所有测试。"""
    print("=" * 50)
    print("增量分析功能测试")
    print("=" * 50)

    tests = [
        test_merge_characters,
        test_merge_settings,
        test_merge_events,
        test_merge_character_data,
        test_merge_setting_data,
        test_merge_event_data,
        test_build_initial_context,
        test_safe_filename,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test.__name__} 失败: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {test.__name__} 异常: {e}")
            failed += 1

    print("=" * 50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
