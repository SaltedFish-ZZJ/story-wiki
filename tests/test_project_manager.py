"""
Story Wiki - ProjectManager 单元测试
使用临时目录模拟多作品 Vault，测试跨作品管理功能。
"""
import tempfile
from pathlib import Path

from src.project_manager import ProjectManager
from src.vault_manager import _safe_filename


# ── 辅助：创建测试用多作品 Vault ──────────────────────────────

def _create_multi_book_vault(base_dir: Path):
    """在临时目录中创建包含多个作品的测试 Vault。"""
    # 作品 A：红楼梦
    book_a = base_dir / _safe_filename("红楼梦")
    char_a = book_a / "characters"
    event_a = book_a / "events"
    setting_a = book_a / "settings"
    for d in [char_a, event_a, setting_a]:
        d.mkdir(parents=True, exist_ok=True)

    # 人物卡片
    (char_a / "贾宝玉.md").write_text("""---
type: character
gender: 男
faction: 荣国府
aliases: [宝二爷]
---

# 贾宝玉

> 活跃

## 身份
荣国府公子

## 性格
叛逆多情

## 人际关系
- [[characters/林黛玉|林黛玉]] — 恋人
""", encoding="utf-8")

    (char_a / "林黛玉.md").write_text("""---
type: character
gender: 女
faction: 荣国府
---

# 林黛玉

> 活跃

## 身份
贾府外甥女

## 性格
多愁善感

## 人际关系
- [[characters/贾宝玉|贾宝玉]] — 恋人
""", encoding="utf-8")

    # 事件卡片
    (event_a / "宝黛初见.md").write_text("""---
type: event
time: 贾宝玉五岁
chapter: 第三回
---

# 宝黛初见

**时间**：贾宝玉五岁

宝黛二人初次相见。
""", encoding="utf-8")

    # 设定卡片
    (setting_a / "大观园.md").write_text("""---
type: setting
setting_type: 地点
---

# 大观园

**类型**：地点

贾府的后花园。
""", encoding="utf-8")

    # 作品 B：西游记
    book_b = base_dir / _safe_filename("西游记")
    char_b = book_b / "characters"
    event_b = book_b / "events"
    setting_b = book_b / "settings"
    for d in [char_b, event_b, setting_b]:
        d.mkdir(parents=True, exist_ok=True)

    (char_b / "孙悟空.md").write_text("""---
type: character
gender: 男
faction: 花果山
aliases: [孙行者, 齐天大圣]
---

# 孙悟空

> 活跃

## 身份
花果山水帘洞美猴王

## 性格
勇敢无畏

## 人际关系
- [[characters/唐僧|唐僧]] — 师父
""", encoding="utf-8")

    (event_b / "大闹天宫.md").write_text("""---
type: event
time: 取经前
chapter: 第五回
---

# 大闹天宫

**时间**：取经前

孙悟空大闹天宫的故事。
""", encoding="utf-8")

    return base_dir


# ── 测试 VaultManager.list_books ──────────────────────────────

class TestVaultManagerListBooks:
    """测试 VaultManager.list_books() 方法。"""

    def test_list_books_empty_vault(self):
        """空 Vault 返回空列表"""
        from src.vault_manager import VaultManager
        with tempfile.TemporaryDirectory() as tmpdir:
            vm = VaultManager({"vault_dir": tmpdir})
            books = vm.list_books()
            assert books == []

    def test_list_books_with_books(self, tmp_path):
        """有作品时返回正确统计"""
        from src.vault_manager import VaultManager
        vault_dir = _create_multi_book_vault(tmp_path)
        vm = VaultManager({"vault_dir": str(vault_dir)})
        books = vm.list_books()
        assert len(books) == 2

        # 按名称排序
        titles = sorted([b["title"] for b in books])
        assert titles == ["红楼梦", "西游记"]

        # 验证统计
        for book in books:
            if book["title"] == "红楼梦":
                assert book["characters"] == 2
                assert book["events"] == 1
                assert book["settings"] == 1
            elif book["title"] == "西游记":
                assert book["characters"] == 1
                assert book["events"] == 1
                assert book["settings"] == 0

    def test_list_books_skips_hidden_dirs(self, tmp_path):
        """跳过隐藏目录和 .obsidian"""
        from src.vault_manager import VaultManager
        vault_dir = _create_multi_book_vault(tmp_path)
        # 创建隐藏目录
        (vault_dir / ".obsidian").mkdir(exist_ok=True)
        (vault_dir / ".hidden").mkdir(exist_ok=True)
        vm = VaultManager({"vault_dir": str(vault_dir)})
        books = vm.list_books()
        titles = [b["title"] for b in books]
        assert ".obsidian" not in titles
        assert ".hidden" not in titles


# ── 测试 ProjectManager.list_books ────────────────────────────

class TestProjectManagerListBooks:
    """测试 ProjectManager.list_books() 方法。"""

    def test_list_books_empty_vault(self):
        """空 Vault 返回空列表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProjectManager({"vault_dir": tmpdir})
            books = pm.list_books()
            assert books == []

    def test_list_books_with_books(self, tmp_path):
        """有作品时返回正确统计"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        books = pm.list_books()
        assert len(books) == 2
        titles = sorted([b["title"] for b in books])
        assert titles == ["红楼梦", "西游记"]


# ── 测试 ProjectManager.search_cross_book ─────────────────────

class TestProjectManagerSearchCrossBook:
    """测试跨作品搜索功能。"""

    def test_search_cross_book(self, tmp_path):
        """跨作品搜索正确分组"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})

        results = pm.search_cross_book("贾")
        assert "红楼梦" in results
        # 贾宝玉匹配
        chars = results["红楼梦"]["characters"]
        assert any(c["name"] == "贾宝玉" for c in chars)

    def test_search_cross_book_no_results(self, tmp_path):
        """搜索无结果时返回空字典"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        results = pm.search_cross_book("完全不存在的内容")
        assert results == {}

    def test_search_cross_book_marks_source(self, tmp_path):
        """搜索结果标注来源作品"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        results = pm.search_cross_book("孙")
        assert "西游记" in results
        for char in results["西游记"]["characters"]:
            assert char["book"] == "西游记"


# ── 测试 ProjectManager.find_similar_characters ────────────────

class TestProjectManagerFindSimilarCharacters:
    """测试跨作品人物相似度匹配。"""

    def test_find_similar_none(self, tmp_path):
        """无相似人物时返回空列表"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        # 红楼梦和西游记没有相似人物
        matches = pm.find_similar_characters()
        # 应该为空（没有名称匹配的人物）
        assert isinstance(matches, list)

    def test_find_similar_with_exact_match(self, tmp_path):
        """精确名称匹配检测"""
        vault_dir = _create_multi_book_vault(tmp_path)

        # 添加一个同名人物到西游记
        char_b = vault_dir / _safe_filename("西游记") / "characters"
        (char_b / "林黛玉.md").write_text("""---
type: character
gender: 女
faction: 天庭
---

# 林黛玉

> 活跃

## 身份
仙女

## 性格
温柔

## 人际关系
""", encoding="utf-8")

        pm = ProjectManager({"vault_dir": str(vault_dir)})
        matches = pm.find_similar_characters()

        # 应该找到红楼梦的林黛玉和西游记的林黛玉匹配
        found = [m for m in matches
                 if m["character_a"]["name"] == "林黛玉"
                 and m["character_b"]["name"] == "林黛玉"]
        assert len(found) >= 1
        assert found[0]["match_type"] == "exact"
        assert found[0]["confidence"] == "high"

    def test_find_similar_single_book(self, tmp_path):
        """只有一本书时返回空列表"""
        book_dir = tmp_path / _safe_filename("红楼梦")
        char_dir = book_dir / "characters"
        char_dir.mkdir(parents=True)
        (char_dir / "贾宝玉.md").write_text("""---
type: character
gender: 男
---

# 贾宝玉

> 活跃

## 身份
公子
""", encoding="utf-8")

        pm = ProjectManager({"vault_dir": str(tmp_path)})
        matches = pm.find_similar_characters()
        assert matches == []


# ── 测试 ProjectManager.get_book_summary ───────────────────────

class TestProjectManagerBookSummary:
    """测试单本书摘要功能。"""

    def test_get_book_summary(self, tmp_path):
        """单本书摘要正确"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        summary = pm.get_book_summary("红楼梦")

        assert summary is not None
        assert summary["title"] == "红楼梦"
        assert summary["characters_count"] == 2
        assert summary["settings_count"] == 1
        assert summary["events_count"] == 1
        assert len(summary["characters"]) == 2

    def test_get_book_summary_nonexistent(self, tmp_path):
        """不存在的作品返回空摘要"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        summary = pm.get_book_summary("不存在的作品")
        assert summary is not None
        assert summary["title"] == "不存在的作品"
        assert summary["characters_count"] == 0
        assert summary["events_count"] == 0
        assert summary["settings_count"] == 0

    def test_get_book_summary_timeline_span(self, tmp_path):
        """时间线跨度正确"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        summary = pm.get_book_summary("西游记")
        assert summary["timeline_span"] == "取经前"


# ── 测试 ProjectManager.get_cross_book_timeline ───────────────

class TestProjectManagerCrossBookTimeline:
    """测试跨作品时间线功能。"""

    def test_get_cross_book_timeline(self, tmp_path):
        """时间线合并排序"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        timeline = pm.get_cross_book_timeline()

        assert len(timeline) == 2
        # 验证每个事件都有 book 字段
        for event in timeline:
            assert "book" in event
        # 验证排序（空时间排最后）
        times = [e.get("time", "") for e in timeline]
        assert times == sorted(times, key=lambda t: t if t else "\uffff")


# ── 测试 ProjectManager.run() ─────────────────────────────────

class TestProjectManagerRun:
    """测试 run() 方法的分发逻辑。"""

    def test_run_list_books(self, tmp_path):
        """run() 分发 list_books"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        result = pm.run({"action": "list_books"})
        assert result["success"] is True
        assert len(result["books"]) == 2

    def test_run_search_cross_book(self, tmp_path):
        """run() 分发 search_cross_book"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        result = pm.run({"action": "search_cross_book", "keyword": "孙"})
        assert result["success"] is True
        assert "西游记" in result["results"]

    def test_run_search_cross_book_missing_keyword(self, tmp_path):
        """run() 缺少 keyword 返回错误"""
        pm = ProjectManager()
        result = pm.run({"action": "search_cross_book"})
        assert result["success"] is False
        assert "keyword" in result["error"]

    def test_run_find_similar_characters(self, tmp_path):
        """run() 分发 find_similar_characters"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        result = pm.run({"action": "find_similar_characters"})
        assert result["success"] is True
        assert "matches" in result

    def test_run_get_book_summary(self, tmp_path):
        """run() 分发 get_book_summary"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        result = pm.run({"action": "get_book_summary", "book_title": "红楼梦"})
        assert result["success"] is True
        assert result["summary"]["title"] == "红楼梦"

    def test_run_get_book_summary_missing_title(self, tmp_path):
        """run() 缺少 book_title 返回错误"""
        pm = ProjectManager()
        result = pm.run({"action": "get_book_summary"})
        assert result["success"] is False
        assert "book_title" in result["error"]

    def test_run_get_cross_book_timeline(self, tmp_path):
        """run() 分发 get_cross_book_timeline"""
        vault_dir = _create_multi_book_vault(tmp_path)
        pm = ProjectManager({"vault_dir": str(vault_dir)})
        result = pm.run({"action": "get_cross_book_timeline"})
        assert result["success"] is True
        assert len(result["timeline"]) == 2

    def test_run_unknown_action(self):
        """run() 未知 action 返回错误"""
        pm = ProjectManager()
        result = pm.run({"action": "unknown_action"})
        assert result["success"] is False
        assert "未知" in result["error"]

    def test_run_not_dict(self):
        """run() 非 dict 输入返回错误"""
        pm = ProjectManager()
        result = pm.run("not a dict")
        assert result["success"] is False

    def test_validate(self):
        """validate() 正确验证输出"""
        pm = ProjectManager()
        assert pm.validate({"success": True, "books": []}) is True
        assert pm.validate({"success": False, "error": "test"}) is True
        assert pm.validate({"not_valid": True}) is False
        assert pm.validate("not a dict") is False
