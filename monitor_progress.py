#!/usr/bin/env python3
"""
并行开发进度监控脚本
监控 4 个 Agent 的开发进度
"""
import json
import time
from pathlib import Path
from datetime import datetime


def load_sync_status():
    """加载同步状态"""
    status_file = Path(__file__).parent / "sync_status.json"
    if status_file.exists():
        with open(status_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def check_module_files():
    """检查模块文件是否存在"""
    src_dir = Path(__file__).parent / "src"
    test_dir = Path(__file__).parent / "tests"

    modules = {
        "vault_manager": {
            "src": src_dir / "vault_manager.py",
            "test": test_dir / "test_vault_manager.py"
        },
        "plot_generator": {
            "src": src_dir / "plot_generator.py",
            "test": test_dir / "test_plot_generator.py"
        },
        "chapter_generator": {
            "src": src_dir / "chapter_generator.py",
            "test": test_dir / "test_chapter_generator.py"
        },
        "novel_logger": {
            "src": src_dir / "novel_logger.py",
            "test": test_dir / "test_novel_logger.py"
        }
    }

    status = {}
    for module_name, files in modules.items():
        src_exists = files["src"].exists()
        test_exists = files["test"].exists()

        src_lines = 0
        if src_exists:
            with open(files["src"], 'r', encoding='utf-8') as f:
                src_lines = len(f.readlines())

        test_lines = 0
        if test_exists:
            with open(files["test"], 'r', encoding='utf-8') as f:
                test_lines = len(f.readlines())

        status[module_name] = {
            "src_exists": src_exists,
            "src_lines": src_lines,
            "test_exists": test_exists,
            "test_lines": test_lines,
            "progress": 100 if (src_exists and test_exists) else (50 if src_exists else 0)
        }

    return status


def print_progress():
    """打印进度"""
    print("=" * 60)
    print("Story Wiki 并行开发进度监控")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 检查文件状态
    module_status = check_module_files()

    print("模块开发进度:")
    print("-" * 60)
    print(f"{'模块名':<20} {'源代码':<15} {'测试':<15} {'进度':<10}")
    print("-" * 60)

    total_progress = 0
    for module_name, status in module_status.items():
        src_status = f"[OK] {status['src_lines']}行" if status['src_exists'] else "[--] 未创建"
        test_status = f"[OK] {status['test_lines']}行" if status['test_exists'] else "[--] 未创建"
        progress = f"{status['progress']}%"
        total_progress += status['progress']

        print(f"{module_name:<20} {src_status:<15} {test_status:<15} {progress:<10}")

    print("-" * 60)
    avg_progress = total_progress / len(module_status)
    print(f"{'平均进度':<20} {'':<15} {'':<15} {avg_progress:.1f}%")
    print()

    # 检查同步状态
    sync_status = load_sync_status()
    if sync_status:
        print("同步状态:")
        print("-" * 60)
        print(f"最后同步: {sync_status.get('last_sync', 'N/A')}")
        print(f"同步间隔: {sync_status.get('sync_interval_minutes', 30)} 分钟")
        print()

    # 显示详细信息
    print("详细信息:")
    print("-" * 60)
    for module_name, status in module_status.items():
        print(f"\n{module_name}:")
        print(f"  源代码: {'已创建' if status['src_exists'] else '未创建'}")
        if status['src_exists']:
            print(f"  代码行数: {status['src_lines']}")
        print(f"  测试: {'已创建' if status['test_exists'] else '未创建'}")
        if status['test_exists']:
            print(f"  测试行数: {status['test_lines']}")

    print()
    print("=" * 60)


if __name__ == "__main__":
    print_progress()
