"""
Story Wiki - 笔记生成模块测试

覆盖 generator.py 中的核心函数：
- wikilink 构建、状态栏构建
- 人物/设定/事件卡片生成
- 作品索引生成、时间线页面
- Mermaid 图谱生成
- 增量更新与数据合并
- MD 文件解析
"""
import pytest
from pathlib import Path

from src.generator import (
    _wikilink_section,
    _build_status_bar,
    _build_setting_status_bar,
    _build_event_status_bar,
    _build_achievements,
    _build_quotes_section,
    _build_character_mermaid,
    _build_mermaid_graph,
    _build_mermaid_timeline,
    _build_importance_groups,
    _sort_events_by_time,
    _extract_chapter_number,
    _write_character_card,
    _write_setting_card,
    _write_event_card,
    _write_book_index,
    generate_vault,
    generate_vault_incremental,
    generate_timeline_page,
    _merge_character_data,
    _merge_setting_data,
    _merge_event_data,
    _parse_character_md,
    _parse_setting_md,
    _parse_event_md,
)


# ═══════════════════════════════════════════════════════════════
# 1. 辅助函数
# ═══════════════════════════════════════════════════════════════

class TestWikilinkSection:
    """测试 _wikilink_section 函数。"""

    def test_basic(self):
        result = _wikilink_section("关联人物", ["[[A|A]]", "[[B|B]]"])
        assert result[0] == "## 关联人物"
        assert "- [[A|A]]" in result
        assert "- [[B|B]]" in result

    def test_empty_links(self):
        assert _wikilink_section("标题", []) == []

    def test_single_link(self):
        result = _wikilink_section("设定", ["[[大观园]]"])
        assert len(result) == 3  # title, link, empty line


class TestStatusBar:
    """测试状态栏构建函数。"""

    def test_character_status_bar(self):
        char = {"status": "活跃", "faction": "荣国府", "role_tags": ["主角", "男主"]}
        lines = _build_status_bar(char)
        assert "🟢 活跃" in lines[0]
        assert "阵营：荣国府" in lines[0]
        assert "定位：主角 · 男主" in lines[0]

    def test_character_status_unknown(self):
        char = {}
        lines = _build_status_bar(char)
        assert "⚪ 未知" in lines[0]

    def test_setting_status_bar(self):
        setting = {"type": "地点"}
        lines = _build_setting_status_bar(setting, ["A", "B", "C"])
        assert "类型：地点" in lines[0]
        assert "关联人物：3" in lines[0]

    def test_setting_status_no_chars(self):
        setting = {"type": "组织"}
        lines = _build_setting_status_bar(setting, [])
        assert "类型：组织" in lines[0]
        assert "关联人物" not in lines[0]

    def test_event_status_bar(self):
        event = {
            "importance": "高",
            "location": "大观园",
            "participants": ["A", "B"],
            "cause": ["C"],
        }
        lines = _build_event_status_bar(event)
        assert "🔴 高" in lines[0]
        assert "📍 大观园" in lines[0]
        assert "👥 2人参与" in lines[0]
        assert "🔗 前置：1个事件" in lines[0]

    def test_event_status_empty(self):
        assert _build_event_status_bar({}) == []


class TestBuildAchievements:
    """测试 _build_achievements 函数。"""

    def test_with_participating_events(self):
        events = [
            {"name": "事件A", "participants": ["主角"], "importance": "高", "description": "重要事件"},
            {"name": "事件B", "participants": ["配角"], "importance": "低"},
        ]
        lines = _build_achievements("主角", events)
        assert "事件A" in "\n".join(lines)
        assert "事件B" not in "\n".join(lines)

    def test_no_events(self):
        assert _build_achievements("主角", []) == []

    def test_no_participation(self):
        events = [{"name": "事件A", "participants": ["其他人"]}]
        assert _build_achievements("主角", events) == []


class TestBuildQuotesSection:
    """测试 _build_quotes_section 函数。"""

    def test_with_quotes(self):
        char = {"quotes": ["引言1", "引言2"]}
        lines = _build_quotes_section(char)
        assert "💬 经典语录" in lines[0]
        assert '"引言1"' in "\n".join(lines)

    def test_no_quotes(self):
        assert _build_quotes_section({}) == []

    def test_limit_5(self):
        char = {"quotes": [f"q{i}" for i in range(10)]}
        lines = _build_quotes_section(char)
        quote_count = sum(1 for l in lines if l.startswith('> "'))
        assert quote_count == 5


class TestBuildCharacterMermaid:
    """测试 _build_character_mermaid 函数。"""

    def test_with_relationships(self):
        char = {
            "name": "宝玉",
            "relationships": [{"target": "黛玉", "nature": "恋人"}],
        }
        lines = _build_character_mermaid(char)
        assert "```mermaid" in "\n".join(lines)
        assert "宝玉" in "\n".join(lines)
        assert "黛玉" in "\n".join(lines)

    def test_no_relationships(self):
        assert _build_character_mermaid({"name": "路人"}) == []

    def test_max_8_relationships(self):
        rels = [{"target": f"人物{i}", "nature": "朋友"} for i in range(12)]
        char = {"name": "主角", "relationships": rels}
        lines = _build_character_mermaid(char)
        # 应该不超过 8 条关系线
        edge_count = sum(1 for l in lines if "-->" in l)
        assert edge_count <= 8


# ═══════════════════════════════════════════════════════════════
# 2. Mermaid 图谱
# ═══════════════════════════════════════════════════════════════

class TestBuildMermaidGraph:
    """测试 _build_mermaid_graph 函数。"""

    def test_basic_graph(self):
        chars = [
            {"name": "A", "relationships": [{"target": "B", "nature": "朋友"}]},
            {"name": "B", "relationships": [{"target": "A", "nature": "朋友"}]},
        ]
        lines = _build_mermaid_graph(chars)
        assert len(lines) > 1  # 至少有 graph LR 声明
        assert "graph LR" in lines[0]

    def test_no_relationships(self):
        chars = [{"name": "A", "relationships": []}]
        assert _build_mermaid_graph(chars) == []

    def test_dedupes_edges(self):
        chars = [
            {"name": "A", "relationships": [{"target": "B", "nature": "朋友"}]},
            {"name": "B", "relationships": [{"target": "A", "nature": "朋友"}]},
        ]
        lines = _build_mermaid_graph(chars)
        edge_lines = [l for l in lines if "-->" in l]
        assert len(edge_lines) == 1  # 去重后只有1条边

    def test_limits_to_15_chars(self):
        chars = [
            {"name": f"C{i}", "relationships": [{"target": f"C{j}", "nature": "x"} for j in range(3)]}
            for i in range(20)
        ]
        lines = _build_mermaid_graph(chars)
        assert "graph LR" in lines[0]


class TestBuildMermaidTimeline:
    """测试 _build_mermaid_timeline 函数。"""

    def test_basic_timeline(self):
        events = [
            {"name": "事件1", "chapter": "第一章", "participants": ["A"]},
            {"name": "事件2", "chapter": "第二章", "participants": ["B"]},
        ]
        lines = _build_mermaid_timeline("测试作品", events)
        assert "timeline" in lines[0]
        assert "section 第一章" in "\n".join(lines)

    def test_events_without_chapter(self):
        events = [{"name": "事件1"}]
        lines = _build_mermaid_timeline("作品", events)
        assert "section 其他" in "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 3. 事件分组与排序
# ═══════════════════════════════════════════════════════════════

class TestBuildImportanceGroups:
    """测试 _build_importance_groups 函数。"""

    def test_basic_grouping(self):
        events = [
            {"name": "A", "importance": "高"},
            {"name": "B", "importance": "中"},
            {"name": "C", "importance": "低"},
            {"name": "D"},  # 未分类
        ]
        groups = _build_importance_groups(events)
        assert len(groups["高"]) == 1
        assert len(groups["中"]) == 1
        assert len(groups["低"]) == 1
        assert len(groups["未分类"]) == 1

    def test_unknown_importance(self):
        events = [{"name": "A", "importance": "神秘"}]
        groups = _build_importance_groups(events)
        assert len(groups["未分类"]) == 1


class TestSortEventsByTime:
    """测试 _sort_events_by_time 函数。"""

    def test_sorts_by_chapter(self):
        events = [
            {"name": "B", "chapter": "第二回"},
            {"name": "A", "chapter": "第一回"},
        ]
        result = _sort_events_by_time(events)
        assert result[0]["name"] == "A"
        assert result[1]["name"] == "B"

    def test_events_without_chapter_last(self):
        events = [
            {"name": "无章节"},
            {"name": "有章节", "chapter": "第一回"},
        ]
        result = _sort_events_by_time(events)
        assert result[0]["name"] == "有章节"


class TestExtractChapterNumber:
    """测试 generator._extract_chapter_number 函数。"""

    def test_arabic_number(self):
        assert _extract_chapter_number("第12章") == 12

    def test_chinese_number(self):
        assert _extract_chapter_number("第三回") == 3

    def test_empty_returns_9999(self):
        assert _extract_chapter_number("") == 9999

    def test_no_number_returns_9999(self):
        assert _extract_chapter_number("序章") == 9999


# ═══════════════════════════════════════════════════════════════
# 4. 文件写入（使用 tmp_path）
# ═══════════════════════════════════════════════════════════════

class TestWriteCharacterCard:
    """测试 _write_character_card 函数。"""

    def test_creates_file(self, tmp_path):
        char = {"name": "贾宝玉", "identity": "公子", "personality": "多情"}
        path = _write_character_card(char, tmp_path, "红楼梦")
        assert path.exists()
        assert path.name == "贾宝玉.md"

    def test_content_contains_name(self, tmp_path):
        char = {"name": "贾宝玉", "identity": "公子", "personality": "多情",
                "role_tags": ["主角"], "status": "活跃"}
        path = _write_character_card(char, tmp_path, "红楼梦")
        content = path.read_text(encoding="utf-8")
        assert "# 贾宝玉" in content
        assert "公子" in content

    def test_with_relationships(self, tmp_path):
        char = {
            "name": "宝玉",
            "relationships": [{"target": "黛玉", "nature": "恋人"}],
        }
        path = _write_character_card(char, tmp_path, "红楼梦")
        content = path.read_text(encoding="utf-8")
        assert "黛玉" in content

    def test_with_quotes(self, tmp_path):
        char = {"name": "宝玉", "quotes": ["弱水三千只取一瓢饮"]}
        path = _write_character_card(char, tmp_path, "红楼梦")
        content = path.read_text(encoding="utf-8")
        assert "弱水三千只取一瓢饮" in content


class TestWriteSettingCard:
    """测试 _write_setting_card 函数。"""

    def test_creates_file(self, tmp_path):
        setting = {"name": "大观园", "type": "地点", "description": "美丽园林"}
        path = _write_setting_card(setting, tmp_path, "红楼梦")
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "# 大观园" in content


class TestWriteEventCard:
    """测试 _write_event_card 函数。"""

    def test_creates_file(self, tmp_path):
        event = {"name": "宝黛初见", "importance": "高", "time": "某日"}
        path = _write_event_card(event, tmp_path, "红楼梦")
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "# 宝黛初见" in content


class TestWriteBookIndex:
    """测试 _write_book_index 函数。"""

    def test_creates_index(self, tmp_path):
        path = _write_book_index(
            "红楼梦", "一部巨著",
            [{"name": "贾宝玉", "identity": "公子"}],
            [{"name": "大观园", "description": "园林"}],
            [{"name": "事件1", "time": "某日"}],
            tmp_path,
        )
        assert path.name == "_index.md"
        content = path.read_text(encoding="utf-8")
        assert "红楼梦" in content


# ═══════════════════════════════════════════════════════════════
# 5. generate_vault 集成
# ═══════════════════════════════════════════════════════════════

class TestGenerateVault:
    """测试 generate_vault 函数。"""

    def test_full_generation(self, tmp_path):
        analysis = {
            "title": "测试作品",
            "characters": [
                {"name": "主角", "identity": "英雄", "personality": "勇敢",
                 "role_tags": ["主角"], "status": "活跃"},
            ],
            "settings": [{"name": "城堡", "type": "地点"}],
            "events": [{"name": "大冒险", "importance": "高"}],
            "summary": "一个冒险故事",
        }
        files = generate_vault(analysis, tmp_path)
        assert len(files) > 0
        # 验证目录结构
        book_dir = tmp_path / "测试作品"
        assert book_dir.exists()
        assert (book_dir / "characters").exists()
        assert (book_dir / "settings").exists()
        assert (book_dir / "events").exists()

    def test_empty_analysis(self, tmp_path):
        files = generate_vault({}, tmp_path)
        assert len(files) > 0  # 至少有 _index.md

    def test_no_events_no_timeline(self, tmp_path):
        analysis = {
            "title": "NoEventBook",
            "characters": [{"name": "Alice"}],
        }
        files = generate_vault(analysis, tmp_path)
        names = [Path(f).name for f in files]
        assert "timeline.md" not in names


class TestGenerateTimelinePage:
    """测试 generate_timeline_page 函数。"""

    def test_creates_timeline(self, tmp_path):
        events = [
            {"name": "事件1", "chapter": "第一章", "importance": "高", "participants": ["A"]},
            {"name": "事件2", "chapter": "第二章", "importance": "中"},
        ]
        path = generate_timeline_page("作品", events, tmp_path)
        assert path is not None
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "时间线" in content

    def test_no_events_returns_none(self, tmp_path):
        assert generate_timeline_page("作品", [], tmp_path) is None


# ═══════════════════════════════════════════════════════════════
# 6. 增量更新
# ═══════════════════════════════════════════════════════════════

class TestMergeCharacterData:
    """测试 _merge_character_data 函数。"""

    def test_takes_longer_text(self):
        old = {"identity": "短"}
        new = {"identity": "更长的身份描述"}
        merged = _merge_character_data(old, new)
        assert merged["identity"] == "更长的身份描述"

    def test_keeps_longer_old_text(self):
        old = {"identity": "更长的身份描述"}
        new = {"identity": "短"}
        merged = _merge_character_data(old, new)
        assert merged["identity"] == "更长的身份描述"

    def test_merges_lists(self):
        old = {"aliases": ["别名1"], "quotes": ["名言1"]}
        new = {"aliases": ["别名2"], "quotes": ["名言2"]}
        merged = _merge_character_data(old, new)
        assert set(merged["aliases"]) == {"别名1", "别名2"}
        assert set(merged["quotes"]) == {"名言1", "名言2"}

    def test_merges_relationships(self):
        old = {"relationships": [{"target": "A", "nature": "朋友"}]}
        new = {"relationships": [{"target": "B", "nature": "恋人"}]}
        merged = _merge_character_data(old, new)
        targets = {r["target"] for r in merged["relationships"]}
        assert "A" in targets
        assert "B" in targets


class TestMergeSettingData:
    """测试 _merge_setting_data 函数。"""

    def test_takes_longer_description(self):
        old = {"description": "短"}
        new = {"description": "更长的描述"}
        merged = _merge_setting_data(old, new)
        assert merged["description"] == "更长的描述"

    def test_merges_lists(self):
        old = {"related_characters": ["A"]}
        new = {"related_characters": ["B"]}
        merged = _merge_setting_data(old, new)
        assert set(merged["related_characters"]) == {"A", "B"}


class TestMergeEventData:
    """测试 _merge_event_data 函数。"""

    def test_takes_longer_description(self):
        old = {"description": "短"}
        new = {"description": "更长的描述"}
        merged = _merge_event_data(old, new)
        assert merged["description"] == "更长的描述"

    def test_merges_participants(self):
        old = {"participants": ["A"]}
        new = {"participants": ["B"]}
        merged = _merge_event_data(old, new)
        assert set(merged["participants"]) == {"A", "B"}


# ═══════════════════════════════════════════════════════════════
# 7. MD 文件解析
# ═══════════════════════════════════════════════════════════════

class TestParseCharacterMd:
    """测试 _parse_character_md 函数。"""

    def test_basic_parse(self):
        md = """---
type: character
gender: 男
---
# 贾宝玉

> 🟢 活跃 | 阵营：荣国府

## 身份
公子

## 性格
多情

## 人际关系
- [[characters/林黛玉|林黛玉]] — 恋人
"""
        char = _parse_character_md(md)
        assert char["name"] == "贾宝玉"
        assert char["gender"] == "男"
        assert char.get("status") == "活跃"

    def test_no_name_returns_none(self):
        assert _parse_character_md("no title here") is None

    def test_extracts_quotes(self):
        md = "# 人物\n\n## 💬 经典语录\n\n> \"名言1\"\n\n> \"名言2\""
        char = _parse_character_md(md)
        assert "名言1" in char.get("quotes", [])


class TestParseSettingMd:
    """测试 _parse_setting_md 函数。"""

    def test_basic_parse(self):
        md = "# 大观园\n\n**类型**：地点\n\n一个美丽的园林"
        setting = _parse_setting_md(md)
        assert setting["name"] == "大观园"
        assert setting["setting_type"] == "地点"

    def test_no_name_returns_none(self):
        assert _parse_setting_md("no title") is None


class TestParseEventMd:
    """测试 _parse_event_md 函数。"""

    def test_basic_parse(self):
        md = "---\ntype: event\ntime: 某日\n---\n# 宝黛初见\n\n重要事件"
        event = _parse_event_md(md)
        assert event["name"] == "宝黛初见"
        assert event.get("time") == "某日"

    def test_no_name_returns_none(self):
        assert _parse_event_md("no title") is None


# ═══════════════════════════════════════════════════════════════
# 8. 增量写入集成
# ═══════════════════════════════════════════════════════════════

class TestGenerateVaultIncremental:
    """测试 generate_vault_incremental 函数。"""

    def test_first_run_creates_files(self, tmp_path):
        analysis = {
            "title": "增量测试",
            "characters": [{"name": "角色A", "identity": "身份A"}],
            "settings": [],
            "events": [],
        }
        files = generate_vault_incremental(analysis, tmp_path)
        assert len(files) > 0

    def test_second_run_updates(self, tmp_path):
        analysis1 = {
            "title": "增量测试",
            "characters": [{"name": "角色A", "identity": "身份A", "aliases": ["别名1"]}],
        }
        generate_vault_incremental(analysis1, tmp_path)

        analysis2 = {
            "title": "增量测试",
            "characters": [{"name": "角色A", "identity": "更长的身份描述", "aliases": ["别名2"]}],
        }
        files = generate_vault_incremental(analysis2, tmp_path)
        assert len(files) > 0

        # 验证合并结果
        char_file = tmp_path / "增量测试" / "characters" / "其他人物" / "角色A.md"
        content = char_file.read_text(encoding="utf-8")
        assert "更长的身份描述" in content
