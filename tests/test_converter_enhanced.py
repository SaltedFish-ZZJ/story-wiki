"""
Story Wiki - 格式转换器增强功能测试
测试 EPUB 优化、Markdown 导出、批量导出、平台格式转换。
"""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from src.converter import (
    Converter,
    get_converter,
    convert_novel,
    batch_export_novel,
    SUPPORTED_PLATFORMS,
    PLATFORM_RULES,
)


# ── 测试数据 ──────────────────────────────────────────────────

SAMPLE_NOVEL = """# 测试小说

## 第一章 初遇

在一个阳光明媚的早晨，小明走在上学的路上。

突然，他看到了一个奇怪的老人。

"小伙子，你想改变命运吗？"老人神秘地问道。

小明犹豫了一下，点了点头。

## 第二章 奇遇

从那天起，小明的生活发生了翻天覆地的变化。

他发现自己获得了一种特殊的能力。

这种能力让他可以看见别人看不见的东西。

## 第三章 冒险

小明决定利用这种能力去帮助别人。

他踏上了冒险的旅程。

一路上遇到了各种各样的挑战。

但他始终没有放弃。
"""

SAMPLE_METADATA = {
    "title": "测试小说",
    "author": "测试作者",
    "language": "zh",
    "description": "这是一本测试小说",
    "date": "2026-06-24",
}


def _make_converter():
    """创建使用临时目录的 Converter 实例。"""
    tmpdir = tempfile.mkdtemp(prefix="converter_enhanced_test_")
    return Converter({"output_dir": tmpdir}), Path(tmpdir)


# ── EPUB 优化测试 ─────────────────────────────────────────────

class TestEpubOptimization:
    """EPUB 优化功能测试。"""

    def test_create_epub_with_cover_no_cover(self):
        """测试不带封面的 EPUB 生成。"""
        print("测试不带封面的 EPUB 生成...")
        converter, tmpdir = _make_converter()
        try:
            try:
                path = converter.create_epub_with_cover(
                    SAMPLE_NOVEL, SAMPLE_METADATA, cover_image=None
                )
            except ImportError:
                print("  [SKIP] ebooklib 未安装，跳过 EPUB 测试")
                return
            assert Path(path).exists()
            assert Path(path).stat().st_size > 0
            print(f"  [PASS] EPUB 已生成: {path}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_create_epub_with_cover_with_cover(self):
        """测试带封面的 EPUB 生成。"""
        print("测试带封面的 EPUB 生成...")
        converter, tmpdir = _make_converter()
        try:
            # 创建一个假封面图片
            cover_path = tmpdir / "cover.png"
            # 创建一个最小的有效 PNG 文件
            # PNG 文件头 + IHDR 块 (1x1 像素)
            import struct
            png_header = b'\x89PNG\r\n\x1a\n'
            # IHDR 数据
            ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
            ihdr_crc = b'\x00\x00\x00\x00'  # 简化的 CRC
            ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + ihdr_crc
            # 写入文件
            with open(cover_path, 'wb') as f:
                f.write(png_header)
                f.write(ihdr_chunk)

            metadata = {**SAMPLE_METADATA, "cover_image": str(cover_path)}
            try:
                path = converter.create_epub_with_cover(
                    SAMPLE_NOVEL, metadata, cover_image=str(cover_path)
                )
            except ImportError:
                print("  [SKIP] ebooklib 未安装，跳过带封面 EPUB 测试")
                return
            assert Path(path).exists()
            assert Path(path).stat().st_size > 0
            print(f"  [PASS] 带封面的 EPUB 已生成: {path}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_add_epub_toc(self):
        """测试 EPUB 目录生成。"""
        print("测试 EPUB 目录生成...")
        converter, tmpdir = _make_converter()
        try:
            chapters = converter._parse_chapters(SAMPLE_NOVEL)
            assert len(chapters) == 3

            # 验证章节标题
            assert chapters[0][0] == "第一章 初遇"
            assert chapters[1][0] == "第二章 奇遇"
            assert chapters[2][0] == "第三章 冒险"

            print("  [PASS] EPUB 目录生成测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_style_epub_content(self):
        """测试 EPUB 内容样式化。"""
        print("测试 EPUB 内容样式化...")
        converter, tmpdir = _make_converter()
        try:
            content = "这是测试内容。\n\n**加粗**和*斜体*。"
            html = converter.style_epub_content("测试章节", content)

            # 验证 HTML 结构
            assert '<?xml version="1.0"' in html
            assert '<h1 class="chapter-title">测试章节</h1>' in html
            assert '<p class="paragraph">' in html
            assert '<strong>加粗</strong>' in html
            assert '<em>斜体</em>' in html

            print("  [PASS] EPUB 内容样式化测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── Markdown 导出测试 ─────────────────────────────────────────

class TestMarkdownExport:
    """Markdown 导出功能测试。"""

    def test_export_to_markdown_basic(self):
        """测试基本 Markdown 导出。"""
        print("测试基本 Markdown 导出...")
        converter, tmpdir = _make_converter()
        try:
            path = converter.export_to_markdown(SAMPLE_NOVEL, SAMPLE_METADATA)
            assert Path(path).exists()

            # 读取并验证内容
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # 验证 YAML frontmatter
            assert '---' in content
            assert 'title: "测试小说"' in content
            assert 'author: "测试作者"' in content

            # 验证章节内容
            assert "## 第一章 初遇" in content
            assert "小明" in content

            print("  [PASS] 基本 Markdown 导出测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_export_to_markdown_with_toc(self):
        """测试带目录的 Markdown 导出。"""
        print("测试带目录的 Markdown 导出...")
        converter, tmpdir = _make_converter()
        try:
            path = converter.export_to_markdown(SAMPLE_NOVEL, SAMPLE_METADATA)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # 验证目录存在
            assert "## 目录" in content
            assert "- [第一章 初遇]" in content
            assert "- [第二章 奇遇]" in content
            assert "- [第三章 冒险]" in content

            print("  [PASS] 带目录的 Markdown 导出测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_create_markdown_with_toc(self):
        """测试创建带增强目录的 Markdown。"""
        print("测试创建带增强目录的 Markdown...")
        converter, tmpdir = _make_converter()
        try:
            chapters = converter._parse_chapters(SAMPLE_NOVEL)
            path = converter.create_markdown_with_toc(chapters, SAMPLE_METADATA)
            assert Path(path).exists()

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # 验证增强的目录格式
            assert "## 📖 目录" in content
            assert "1." in content  # 编号
            assert "字" in content  # 字数统计

            # 验证章节内容
            assert "## 第一章 初遇" in content

            print("  [PASS] 带增强目录的 Markdown 测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_export_to_markdown_no_chapters(self):
        """测试无章节内容的 Markdown 导出。"""
        print("测试无章节内容的 Markdown 导出...")
        converter, tmpdir = _make_converter()
        try:
            content_no_chapters = "这是一段没有章节标记的内容。"
            metadata = {"title": "无章节测试"}
            path = converter.export_to_markdown(content_no_chapters, metadata)
            assert Path(path).exists()

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # 应该没有目录
            assert "## 目录" not in content

            print("  [PASS] 无章节 Markdown 导出测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── 批量导出测试 ─────────────────────────────────────────────

class TestBatchExport:
    """批量导出功能测试。"""

    def test_batch_export_select_formats(self):
        """测试选择格式批量导出。"""
        print("测试选择格式批量导出...")
        converter, tmpdir = _make_converter()
        try:
            formats = ["fanqie", "qidian"]
            results = converter.batch_export(SAMPLE_NOVEL, SAMPLE_METADATA, formats)

            # 验证指定格式已导出
            assert "fanqie" in results
            assert "qidian" in results

            # 验证文件存在
            for key, path in results.items():
                assert Path(path).exists(), f"{key} 格式文件应存在"

            print("  [PASS] 选择格式批量导出测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_batch_export_all(self):
        """测试导出所有格式。"""
        pytest.importorskip("ebooklib")
        print("测试导出所有格式...")
        converter, tmpdir = _make_converter()
        try:
            results = converter.batch_export(
                SAMPLE_NOVEL, SAMPLE_METADATA, ["all"]
            )

            # 验证非 EPUB 的所有格式都导出（EPUB 需要 ebooklib）
            expected_formats = SUPPORTED_PLATFORMS + ["txt", "markdown"]
            for fmt in expected_formats:
                assert fmt in results, f"格式 {fmt} 应被导出"

            # EPUB 可能因 ebooklib 缺失而失败
            has_epub = "epub" in results
            print(f"  [INFO] EPUB 是否生成: {has_epub}")

            # 验证文件存在
            for key, path in results.items():
                assert Path(path).exists(), f"{key} 格式文件应存在"

            print("  [PASS] 导出所有格式测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_batch_export_markdown(self):
        """测试导出 Markdown 格式。"""
        print("测试导出 Markdown 格式...")
        converter, tmpdir = _make_converter()
        try:
            results = converter.batch_export(
                SAMPLE_NOVEL, SAMPLE_METADATA, ["markdown"]
            )

            assert "markdown" in results
            assert Path(results["markdown"]).exists()

            print("  [PASS] 导出 Markdown 格式测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_batch_export_custom_dir(self):
        """测试自定义目录批量导出。"""
        print("测试自定义目录批量导出...")
        converter, tmpdir = _make_converter()
        try:
            custom_dir = tmpdir / "custom_exports"
            results = converter.batch_export(
                SAMPLE_NOVEL, SAMPLE_METADATA,
                ["fanqie", "txt"],
                output_dir=str(custom_dir)
            )

            for key, path in results.items():
                assert str(custom_dir) in path, f"{key} 文件应在自定义目录中"

            print("  [PASS] 自定义目录批量导出测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_export_to_all_platforms(self):
        """测试导出到所有平台。"""
        print("测试导出到所有平台...")
        converter, tmpdir = _make_converter()
        try:
            results = converter.export_to_all_platforms(SAMPLE_NOVEL, SAMPLE_METADATA)

            # 验证所有平台都导出
            for platform in SUPPORTED_PLATFORMS:
                assert platform in results, f"平台 {platform} 应被导出"
                assert "name" in results[platform]
                assert "path" in results[platform]
                assert Path(results[platform]["path"]).exists()

            print("  [PASS] 导出到所有平台测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_export_to_all_platforms_custom_dir(self):
        """测试自定义目录导出到所有平台。"""
        print("测试自定义目录导出到所有平台...")
        converter, tmpdir = _make_converter()
        try:
            custom_dir = tmpdir / "platforms"
            results = converter.export_to_all_platforms(
                SAMPLE_NOVEL, SAMPLE_METADATA,
                output_dir=str(custom_dir)
            )

            for key, data in results.items():
                assert str(custom_dir) in data["path"]

            print("  [PASS] 自定义目录导出到所有平台测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── 平台格式转换测试 ─────────────────────────────────────────

class TestPlatformFormats:
    """平台格式转换测试。"""

    def test_new_platforms_supported(self):
        """测试新增平台的支持。"""
        print("测试新增平台的支持...")
        converter, tmpdir = _make_converter()
        try:
            # 测试新增的平台
            for platform in ["ciweimao", "zongheng"]:
                result = converter.convert_to_platform(SAMPLE_NOVEL, platform)
                assert "第一章 初遇" in result
                assert platform in SUPPORTED_PLATFORMS

            print("  [PASS] 新增平台支持测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_platform_rules_complete(self):
        """测试平台规则完整性。"""
        print("测试平台规则完整性...")
        for platform, rules in PLATFORM_RULES.items():
            assert "name" in rules
            assert "paragraph_indent" in rules
            assert "title_format" in rules
            assert "prohibited_chars" in rules
            assert "description" in rules

        print("  [PASS] 平台规则完整性测试通过")

    def test_convert_to_platform_all(self):
        """测试所有平台的格式转换。"""
        print("测试所有平台的格式转换...")
        converter, tmpdir = _make_converter()
        try:
            for platform in SUPPORTED_PLATFORMS:
                result = converter.convert_to_platform(SAMPLE_NOVEL, platform)
                assert isinstance(result, str)
                assert len(result) > 0

            print("  [PASS] 所有平台格式转换测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── run 接口增强测试 ─────────────────────────────────────────

class TestRunInterface:
    """run 接口增强功能测试。"""

    def test_run_to_epub_with_cover(self):
        """测试 run 方法带封面 EPUB 转换。"""
        pytest.importorskip("ebooklib")
        print("测试 run 带封面 EPUB 转换...")
        converter, tmpdir = _make_converter()
        try:
            result = converter.run({
                "action": "to_epub_with_cover",
                "content": SAMPLE_NOVEL,
                "metadata": SAMPLE_METADATA,
                "cover_image": None,
            })
            # 如果 ebooklib 未安装，run 会返回失败结果
            if not result["success"] and "ebooklib" in result.get("error", "").lower():
                print("  [SKIP] ebooklib 未安装，跳过 run EPUB 测试")
                return
            assert result["success"] is True
            assert "path" in result

            print("  [PASS] run 带封面 EPUB 转换测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_run_to_markdown(self):
        """测试 run 方法 Markdown 转换。"""
        print("测试 run Markdown 转换...")
        converter, tmpdir = _make_converter()
        try:
            result = converter.run({
                "action": "to_markdown",
                "content": SAMPLE_NOVEL,
                "metadata": SAMPLE_METADATA,
            })
            assert result["success"] is True
            assert "path" in result

            print("  [PASS] run Markdown 转换测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_run_to_markdown_with_toc(self):
        """测试 run 方法带目录 Markdown 转换。"""
        print("测试 run 带目录 Markdown 转换...")
        converter, tmpdir = _make_converter()
        try:
            result = converter.run({
                "action": "to_markdown_with_toc",
                "content": SAMPLE_NOVEL,
                "metadata": SAMPLE_METADATA,
            })
            assert result["success"] is True
            assert "path" in result

            print("  [PASS] run 带目录 Markdown 转换测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_run_batch_export(self):
        """测试 run 方法批量导出。"""
        pytest.importorskip("ebooklib")
        print("测试 run 批量导出...")
        converter, tmpdir = _make_converter()
        try:
            result = converter.run({
                "action": "batch_export",
                "content": SAMPLE_NOVEL,
                "metadata": SAMPLE_METADATA,
                "formats": ["fanqie", "epub"],
            })
            assert result["success"] is True
            assert "files" in result

            print("  [PASS] run 批量导出测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_run_to_all_platforms(self):
        """测试 run 方法全平台导出。"""
        print("测试 run 全平台导出...")
        converter, tmpdir = _make_converter()
        try:
            result = converter.run({
                "action": "to_all_platforms",
                "content": SAMPLE_NOVEL,
                "metadata": SAMPLE_METADATA,
            })
            assert result["success"] is True
            assert "files" in result

            print("  [PASS] run 全平台导出测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── 便捷函数测试 ─────────────────────────────────────────────

class TestConvenienceFunctions:
    """便捷函数测试。"""

    def test_batch_export_novel(self):
        """测试 batch_export_novel 便捷函数。"""
        print("测试 batch_export_novel 便捷函数...")
        tmpdir = tempfile.mkdtemp(prefix="batch_export_test_")
        try:
            results = batch_export_novel(
                SAMPLE_NOVEL,
                SAMPLE_METADATA,
                ["fanqie", "txt"],
                output_dir=tmpdir
            )
            assert "fanqie" in results
            assert "txt" in results

            for path in results.values():
                assert Path(path).exists()

            print("  [PASS] batch_export_novel 测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_converter_default(self):
        """测试默认配置的 get_converter。"""
        print("测试默认配置的 get_converter...")
        converter = get_converter()
        assert isinstance(converter, Converter)
        print("  [PASS] get_converter 默认配置测试通过")

    def test_get_converter_custom(self):
        """测试自定义配置的 get_converter。"""
        print("测试自定义配置的 get_converter...")
        tmpdir = tempfile.mkdtemp(prefix="converter_custom_test_")
        try:
            converter = get_converter({"output_dir": tmpdir})
            assert isinstance(converter, Converter)
            print("  [PASS] get_converter 自定义配置测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── validate 增强测试 ─────────────────────────────────────────

class TestValidate:
    """validate 方法增强测试。"""

    def test_validate_with_files(self):
        """测试包含 files 的结果验证。"""
        print("测试包含 files 的结果验证...")
        converter, tmpdir = _make_converter()
        try:
            # 测试成功结果
            assert converter.validate({
                "success": True,
                "files": {"fanqie": "/path/to/file.txt"}
            }) is True

            # 测试带新增格式的成功结果
            assert converter.validate({
                "success": True,
                "files": {"markdown": "/path/to/file.md"}
            }) is True

            print("  [PASS] 包含 files 的结果验证测试通过")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── 运行所有测试 ──────────────────────────────────────────────

def run_all_tests():
    """运行所有增强功能测试。"""
    print("=" * 60)
    print("格式转换器增强功能测试")
    print("=" * 60)

    test_classes = [
        TestEpubOptimization,
        TestMarkdownExport,
        TestBatchExport,
        TestPlatformFormats,
        TestRunInterface,
        TestConvenienceFunctions,
        TestValidate,
    ]

    passed = 0
    failed = 0
    errors = []

    for test_class in test_classes:
        print(f"\n--- {test_class.__name__} ---")
        instance = test_class()

        for method_name in dir(instance):
            if method_name.startswith("test_"):
                test_method = getattr(instance, method_name)
                try:
                    test_method()
                    passed += 1
                except AssertionError as e:
                    print(f"  [FAIL] {method_name} 失败: {e}")
                    errors.append((method_name, str(e)))
                    failed += 1
                except Exception as e:
                    print(f"  [ERROR] {method_name} 异常: {e}")
                    errors.append((method_name, str(e)))
                    failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    if errors:
        print("\n失败详情:")
        for name, error in errors:
            print(f"  - {name}: {error}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    import sys
    sys.exit(0 if success else 1)
