#!/usr/bin/env python3
"""
Story Wiki 优化测试脚本
用于验证长文本处理优化效果
"""
import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.extractor import extract_text
from src.splitter import split_chapters, get_split_summary
from src.config import print_memory_status, get_system_memory, get_process_memory


def test_memory_status():
    """测试内存状态显示。"""
    print("=" * 60)
    print("测试 1: 内存状态显示")
    print("=" * 60)
    print_memory_status()
    print()


def test_file_reading(file_path: str):
    """测试文件读取性能。"""
    print("=" * 60)
    print(f"测试 2: 文件读取 - {file_path}")
    print("=" * 60)

    if not Path(file_path).exists():
        print(f"[错误] 文件不存在: {file_path}")
        return None

    # 显示文件信息
    file_size = Path(file_path).stat().st_size
    print(f"文件大小: {file_size / 1024 / 1024:.2f} MB")

    # 读取文件
    start_time = time.time()
    text = extract_text(file_path)
    read_time = time.time() - start_time

    print(f"读取完成:")
    print(f"  - 字数: {len(text)}")
    print(f"  - 耗时: {read_time:.2f} 秒")
    print(f"  - 速度: {len(text) / read_time / 1024:.2f} KB/秒")
    print()

    print_memory_status()
    print()

    return text


def test_chapter_splitting(text: str, title: str = "测试"):
    """测试章节切分性能。"""
    print("=" * 60)
    print(f"测试 3: 章节切分 - {title}")
    print("=" * 60)

    # 切分章节
    start_time = time.time()
    chapters = split_chapters(text)
    split_time = time.time() - start_time

    print(f"切分完成:")
    print(f"  - 章节数: {len(chapters)}")
    print(f"  - 耗时: {split_time:.2f} 秒")
    if chapters:
        avg_chars = sum(ch.char_count for ch in chapters) / len(chapters)
        print(f"  - 平均每章字数: {avg_chars:.0f}")
    print()

    # 显示前 5 个章节信息
    if chapters:
        print("前 5 个章节:")
        print(get_split_summary(chapters[:5]))
    print()

    print_memory_status()
    print()

    return chapters


def test_multiple_files():
    """测试多个大文件。"""
    print("=" * 60)
    print("测试 4: 多文件批量测试")
    print("=" * 60)

    test_files = [
        ("红楼梦", "story/红楼梦.txt"),
        ("水浒传", "story/水浒传.txt"),
        ("西游记", "story/西游记.txt"),
        ("三国演义", "story/三国演义.txt"),
    ]

    results = []

    for title, file_path in test_files:
        full_path = Path(__file__).parent / file_path
        if not full_path.exists():
            print(f"[跳过] {file_path} 不存在")
            continue

        print(f"\n测试 {title}...")

        # 读取
        start_time = time.time()
        text = extract_text(str(full_path))
        read_time = time.time() - start_time

        # 切分
        start_time = time.time()
        chapters = split_chapters(text)
        split_time = time.time() - start_time

        results.append({
            "title": title,
            "chars": len(text),
            "chapters": len(chapters),
            "read_time": read_time,
            "split_time": split_time,
        })

    # 打印结果
    print("\n" + "=" * 60)
    print("批量测试结果")
    print("=" * 60)

    print(f"{'文件名':<10} {'字数':<12} {'章节数':<8} {'读取耗时':<12} {'切分耗时':<12}")
    print("-" * 60)

    for r in results:
        print(f"{r['title']:<10} {r['chars']:<12} {r['chapters']:<8} {r['read_time']:.2f}s{'':<8} {r['split_time']:.2f}s")


def run_all_tests():
    """运行所有测试。"""
    print("Story Wiki 优化测试")
    print("=" * 60)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 测试 1: 内存状态
    test_memory_status()

    # 测试 2: 读取红楼梦
    text = test_file_reading("story/红楼梦.txt")

    # 测试 3: 切分红楼梦
    if text:
        test_chapter_splitting(text, "红楼梦")

    # 测试 4: 批量测试
    test_multiple_files()

    print("=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
