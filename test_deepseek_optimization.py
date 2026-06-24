#!/usr/bin/env python3
"""
DeepSeek 建议实施效果测试脚本
验证重叠窗口、前文摘要、元数据携带等功能
"""
import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.extractor import extract_text
from src.splitter import split_chapters, _split_by_chunks_with_overlap, get_split_summary, Chapter
from src.analyzer import generate_context_summary
from src.config import print_memory_status


def test_overlap_chunking():
    """测试重叠窗口分块算法。"""
    print("=" * 60)
    print("测试 1: 重叠窗口分块算法")
    print("=" * 60)

    # 创建测试文本
    test_text = "这是一段测试文本。" * 500  # 约 2500 字
    print(f"测试文本长度: {len(test_text)} 字")

    # 使用重叠分块
    start_time = time.time()
    chunks = _split_by_chunks_with_overlap(test_text, chunk_size=1000, overlap=200)
    elapsed = time.time() - start_time

    print(f"分块结果:")
    print(f"  - 块数: {len(chunks)}")
    print(f"  - 耗时: {elapsed:.3f} 秒")

    # 验证重叠
    if len(chunks) > 1:
        overlap_count = 0
        for i in range(1, len(chunks)):
            prev_text = chunks[i-1].text
            curr_text = chunks[i].text
            # 检查是否有重叠
            for j in range(1, min(200, len(prev_text))):
                if prev_text[-j:] in curr_text[:200]:
                    overlap_count = j
                    break
        print(f"  - 实际重叠: {overlap_count} 字")

    # 显示元数据
    print(f"\n元数据示例:")
    for i, chunk in enumerate(chunks[:3]):
        print(f"  块 {i+1}:")
        print(f"    - chunk_index: {chunk.chunk_index}")
        print(f"    - total_chunks_in_chapter: {chunk.total_chunks_in_chapter}")
        print(f"    - text[:50]: {chunk.text[:50]}...")

    print()
    return chunks


def test_sentence_boundary():
    """测试句子边界断点。"""
    print("=" * 60)
    print("测试 2: 句子边界断点")
    print("=" * 60)

    from src.splitter import _find_sentence_boundary, SENTENCE_BOUNDARIES

    # 创建测试文本
    test_text = "这是第一句话。这是第二句话！这是第三句话？这是第四句话；这是第五句话"
    print(f"测试文本: {test_text}")

    # 测试向前查找
    position = 20
    boundary = _find_sentence_boundary(test_text, position, direction=-1)
    print(f"\n向前查找:")
    print(f"  - 位置 {position} → 边界 {boundary}")
    print(f"  - 边界前文本: {test_text[:boundary]}")
    print(f"  - 边界后文本: {test_text[boundary:]}")

    # 测试向后查找
    boundary = _find_sentence_boundary(test_text, position, direction=1)
    print(f"\n向后查找:")
    print(f"  - 位置 {position} → 边界 {boundary}")
    print(f"  - 边界前文本: {test_text[:boundary]}")
    print(f"  - 边界后文本: {test_text[boundary:]}")

    print()
    return True


def test_context_summary():
    """测试前文摘要生成。"""
    print("=" * 60)
    print("测试 3: 前文摘要生成")
    print("=" * 60)

    # 模拟分析结果
    mock_result = {
        "characters": [
            {"name": "孙悟空", "identity": "齐天大圣"},
            {"name": "唐僧", "identity": "取经人"},
            {"name": "猪八戒", "identity": "天蓬元帅"},
        ],
        "settings": [
            {"name": "花果山", "type": "地点"},
            {"name": "天宫", "type": "地点"},
        ],
        "events": [
            {"name": "大闹天宫", "description": "孙悟空大闹天宫"},
            {"name": "被压五行山", "description": "孙悟空被压五行山下"},
        ],
        "chapter_summary": "孙悟空大闹天宫后被如来佛祖压在五行山下。",
    }

    # 生成前文摘要
    start_time = time.time()
    summary = generate_context_summary(mock_result, max_length=200)
    elapsed = time.time() - start_time

    print(f"前文摘要:")
    print(f"  - 内容: {summary}")
    print(f"  - 长度: {len(summary)} 字")
    print(f"  - 耗时: {elapsed:.3f} 秒")

    print()
    return summary


def test_metadata_in_chapters():
    """测试章节中的元数据携带。"""
    print("=" * 60)
    print("测试 4: 章节元数据携带")
    print("=" * 60)

    # 读取红楼梦
    file_path = Path(__file__).parent / "story/红楼梦.txt"
    if not file_path.exists():
        print(f"[跳过] {file_path} 不存在")
        return None

    print(f"读取文件: {file_path}")
    text = extract_text(str(file_path))
    print(f"文件长度: {len(text)} 字")

    # 切分章节
    chapters = split_chapters(text)
    print(f"章节数: {len(chapters)}")

    # 显示前 3 个章节的元数据
    print(f"\n前 3 个章节的元数据:")
    for i, ch in enumerate(chapters[:3]):
        print(f"\n章节 {i+1}:")
        print(f"  - index: {ch.index}")
        print(f"  - title: {ch.title}")
        print(f"  - chapter_title: {ch.chapter_title}")
        print(f"  - char_count: {ch.char_count}")
        print(f"  - chunk_index: {ch.chunk_index}")
        print(f"  - total_chunks_in_chapter: {ch.total_chunks_in_chapter}")
        print(f"  - context_before_summary: {ch.context_before_summary}")

    print()
    return chapters


def test_html_cleaning():
    """测试 HTML 标签清理。"""
    print("=" * 60)
    print("测试 5: HTML 标签清理")
    print("=" * 60)

    from src.extractor import _clean_text

    # 测试文本（包含 HTML 标签）
    test_text = """
    <p>这是第一段。</p>
    <p>这是第二段。</p>
    &nbsp;&nbsp;&nbsp;&nbsp;这是第三段。
    <br>
    这是第四段。
    """

    print(f"原始文本:")
    print(test_text)

    # 清理 HTML
    cleaned = _clean_text(test_text, remove_html=True, remove_non_content=False)
    print(f"\n清理后文本:")
    print(cleaned)

    print()
    return cleaned


def test_non_content_removal():
    """测试非正文内容移除。"""
    print("=" * 60)
    print("测试 6: 非正文内容移除")
    print("=" * 60)

    from src.extractor import _remove_non_content

    # 测试文本（包含非正文内容）
    test_text = """
    版权所有 2024
    翻印必究

    序言
    这是一本伟大的书...

    第一回 甄士隐梦幻识通灵 贾雨村风尘怀闺秀
    此开卷第一回也。作者自云...

    第二回 贾夫人仙逝扬州城 冷子兴演说荣国府
    话说贾雨村...

    后记
    感谢读者...

    THE END
    """

    print(f"原始文本:")
    print(test_text)

    # 移除非正文
    cleaned = _remove_non_content(test_text)
    print(f"\n清理后文本:")
    print(cleaned)

    print()
    return cleaned


def run_all_tests():
    """运行所有测试。"""
    print("DeepSeek 建议实施效果测试")
    print("=" * 60)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 显示内存状态
    print_memory_status()
    print()

    # 运行所有测试
    tests = [
        ("重叠窗口分块算法", test_overlap_chunking),
        ("句子边界断点", test_sentence_boundary),
        ("前文摘要生成", test_context_summary),
        ("章节元数据携带", test_metadata_in_chapters),
        ("HTML 标签清理", test_html_cleaning),
        ("非正文内容移除", test_non_content_removal),
    ]

    results = []
    for name, test_func in tests:
        try:
            start_time = time.time()
            result = test_func()
            elapsed = time.time() - start_time
            results.append((name, "SUCCESS", elapsed))
        except Exception as e:
            print(f"[ERROR] {name} 测试失败: {e}")
            results.append((name, "FAILED", 0))

    # 打印测试结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    print(f"{'测试项':<20} {'状态':<10} {'耗时':<10}")
    print("-" * 40)

    for name, status, elapsed in results:
        print(f"{name:<20} {status:<10} {elapsed:.3f}s")

    print("=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
