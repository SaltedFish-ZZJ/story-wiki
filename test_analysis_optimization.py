#!/usr/bin/env python3
"""
测试分析管线优化
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.analyzer import (
    _rank_characters,
    _dedupe_relationships,
    _is_name_pair,
    generate_context_summary,
    _build_chapter_context
)


def test_rank_characters():
    """测试人物排序函数。"""
    print("=" * 60)
    print("测试 1: 人物排序函数")
    print("=" * 60)
    
    # 测试数据
    characters = [
        {
            "name": "贾宝玉",
            "role_tags": ["主角"],
            "relationships": [{"target": "林黛玉", "nature": "恋人"}],
            "status": "活跃"
        },
        {
            "name": "林黛玉",
            "role_tags": ["女主"],
            "relationships": [{"target": "贾宝玉", "nature": "恋人"}],
            "status": "活跃"
        },
        {
            "name": "薛宝钗",
            "role_tags": ["女主"],
            "relationships": [{"target": "贾宝玉", "nature": "夫妻"}],
            "status": "活跃"
        },
        {
            "name": "王熙凤",
            "role_tags": ["配角"],
            "relationships": [{"target": "贾琏", "nature": "夫妻"}, {"target": "贾母", "nature": "祖孙"}],
            "status": "活跃"
        },
        {
            "name": "贾母",
            "role_tags": ["配角"],
            "relationships": [{"target": "贾宝玉", "nature": "祖孙"}, {"target": "贾政", "nature": "母子"}],
            "status": "活跃"
        }
    ]
    
    # 测试排序
    main, minor = _rank_characters(characters)
    
    print(f"总人物数: {len(characters)}")
    print(f"主要人物: {len(main)}")
    print(f"次要人物: {len(minor)}")
    
    print("\n主要人物（按重要性排序）:")
    for i, c in enumerate(main, 1):
        role = c.get("role_tags", [])
        rel_count = len(c.get("relationships", []))
        print(f"  {i}. {c['name']} - 角色: {role}, 关系数: {rel_count}")
    
    print("\n次要人物:")
    for c in minor:
        print(f"  - {c['name']}")
    
    print()


def test_dedupe_relationships():
    """测试关系去重函数。"""
    print("=" * 60)
    print("测试 2: 关系去重函数")
    print("=" * 60)
    
    # 测试数据
    characters = [
        {
            "name": "贾宝玉",
            "role_tags": ["主角"],
            "relationships": [
                {"target": "林黛玉", "nature": "恋人"},
                {"target": "薛宝钗", "nature": "夫妻"},
                {"target": "袭人", "nature": "主仆"}
            ]
        },
        {
            "name": "林黛玉",
            "role_tags": ["女主"],
            "relationships": [
                {"target": "贾宝玉", "nature": "恋人"},
                {"target": "紫鹃", "nature": "主仆"}
            ]
        }
    ]
    
    # 测试去重
    relationships = _dedupe_relationships(characters)
    
    print(f"总关系数: {len(relationships)}")
    print("\n关系列表:")
    for i, rel in enumerate(relationships, 1):
        print(f"  {i}. {rel}")
    
    print()


def test_is_name_pair():
    """测试名字匹配函数。"""
    print("=" * 60)
    print("测试 3: 名字匹配函数")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        ("宝玉", "贾宝玉", True),    # 应该匹配
        ("林", "林黛玉", False),      # 不应该匹配（长度限制）
        ("黛玉", "林黛玉", True),     # 应该匹配
        ("宝钗", "薛宝钗", True),     # 应该匹配
        ("贾", "贾宝玉", False),      # 不应该匹配（长度限制）
        ("宝玉", "宝钗", False),      # 不应该匹配（子串不匹配）
        ("林黛玉", "林黛玉", True),   # 应该匹配（相同）
        ("a", "ab", False),           # 不应该匹配（长度限制）
    ]
    
    print("测试用例:")
    for a, b, expected in test_cases:
        result = _is_name_pair(a, b)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status} '{a}' vs '{b}': {result} (期望: {expected})")
    
    print()


def test_generate_context_summary():
    """测试前文摘要生成函数。"""
    print("=" * 60)
    print("测试 4: 前文摘要生成函数")
    print("=" * 60)
    
    # 测试数据
    analysis_result = {
        "characters": [
            {
                "name": "贾宝玉",
                "role_tags": ["主角"],
                "identity": "荣国府公子",
                "relationships": [{"target": "林黛玉", "nature": "恋人"}],
                "status": "活跃"
            },
            {
                "name": "林黛玉",
                "role_tags": ["女主"],
                "identity": "林如海之女",
                "relationships": [{"target": "贾宝玉", "nature": "恋人"}],
                "status": "活跃"
            }
        ],
        "settings": [
            {
                "name": "大观园",
                "type": "地点",
                "related_characters": ["贾宝玉", "林黛玉"]
            }
        ],
        "events": [
            {
                "name": "宝黛初见",
                "importance": "高"
            }
        ],
        "chapter_summary": "贾宝玉和林黛玉初次见面，互生情愫。"
    }
    
    # 测试生成摘要
    summary = generate_context_summary(analysis_result, max_length=300)
    
    print(f"摘要长度: {len(summary)}")
    print(f"摘要内容:\n{summary}")
    
    print()


def test_build_chapter_context():
    """测试章节上下文构建函数。"""
    print("=" * 60)
    print("测试 5: 章节上下文构建函数")
    print("=" * 60)
    
    # 测试数据
    known_characters = [
        {
            "name": "贾宝玉",
            "role_tags": ["主角"],
            "identity": "荣国府公子",
            "relationships": [{"target": "林黛玉", "nature": "恋人"}],
            "status": "活跃"
        },
        {
            "name": "林黛玉",
            "role_tags": ["女主"],
            "identity": "林如海之女",
            "relationships": [{"target": "贾宝玉", "nature": "恋人"}],
            "status": "活跃"
        }
    ]
    
    known_settings = [
        {
            "name": "大观园",
            "type": "地点",
            "description": "贾府的园林"
        }
    ]
    
    known_events = [
        {
            "name": "宝黛初见",
            "importance": "高"
        }
    ]
    
    # 测试构建上下文
    context = _build_chapter_context(known_characters, known_settings, known_events)
    
    print("上下文内容:")
    print(context)
    
    print()


def run_all_tests():
    """运行所有测试。"""
    print("Story Wiki 分析管线优化测试")
    print("=" * 60)
    
    # 测试 1: 人物排序
    test_rank_characters()
    
    # 测试 2: 关系去重
    test_dedupe_relationships()
    
    # 测试 3: 名字匹配
    test_is_name_pair()
    
    # 测试 4: 前文摘要生成
    test_generate_context_summary()
    
    # 测试 5: 章节上下文构建
    test_build_chapter_context()
    
    print("=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()