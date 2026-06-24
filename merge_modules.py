#!/usr/bin/env python3
"""
合并所有并行开发的模块
"""
import shutil
from pathlib import Path


def merge_modules():
    """合并所有模块到 src/ 目录"""
    src_dir = Path(__file__).parent / "src"
    test_dir = Path(__file__).parent / "tests"

    # 确保测试目录存在
    test_dir.mkdir(exist_ok=True)

    # 要合并的模块
    modules = [
        "vault_manager.py",
        "plot_generator.py",
        "chapter_generator.py",
        "novel_logger.py",
    ]

    print("合并模块...")
    print("=" * 60)

    for module in modules:
        src_file = src_dir / module
        if src_file.exists():
            print(f"[OK] {module} 已存在 ({src_file.stat().st_size} 字节)")
        else:
            print(f"[--] {module} 未找到")

    print("=" * 60)

    # 检查测试文件
    test_files = [
        "test_vault_manager.py",
        "test_plot_generator.py",
        "test_chapter_generator.py",
        "test_novel_logger.py",
    ]

    print("\n检查测试文件...")
    print("=" * 60)

    for test_file in test_files:
        test_path = test_dir / test_file
        if test_path.exists():
            print(f"[OK] {test_file} 已存在 ({test_path.stat().st_size} 字节)")
        else:
            print(f"[--] {test_file} 未找到")

    print("=" * 60)


if __name__ == "__main__":
    merge_modules()
