"""
角色标签（role_tags）改进测试
测试：合并逻辑、分组显示、prompt 规则验证
"""
import pytest
from src.merger import _merge_role_tags, _merge_single_character
from src.generator import _build_character_list_grouped


# ── _merge_role_tags 测试 ──────────────────────────────────────────

class TestMergeRoleTags:
    """测试角色标签合并逻辑。"""

    def test_empty_both(self):
        assert _merge_role_tags([], []) == []

    def test_empty_old(self):
        assert _merge_role_tags([], ["主角"]) == ["主角"]

    def test_empty_new(self):
        assert _merge_role_tags(["配角"], []) == ["配角"]

    def test_protagonist_wins_over_supporting(self):
        """主角应优先于配角（主角排在前面）。"""
        result = _merge_role_tags(["配角"], ["主角"])
        assert "主角" in result
        assert result[0] == "主角"

    def test_supporting_does_not_overwrite_protagonist(self):
        """后续章节的配角不应覆盖主角（主角排在前面）。"""
        result = _merge_role_tags(["主角"], ["配角"])
        assert "主角" in result
        assert result[0] == "主角"

    def test_dedup_same_tag(self):
        """相同标签去重。"""
        result = _merge_role_tags(["主角"], ["主角"])
        assert result == ["主角"]

    def test_two_high_weight_tags(self):
        """保留权重最高的 2 个标签。"""
        result = _merge_role_tags(["主角", "女主"], ["导师"])
        assert len(result) == 2
        assert "主角" in result
        assert "女主" in result

    def test_mixed_tags_keeps_highest(self):
        """混合标签时保留权重最高的。"""
        result = _merge_role_tags(["配角", "路人"], ["反派"])
        assert "反派" in result
        assert len(result) == 2

    def test_protagonist_and_mentor(self):
        """主角 + 导师应保留这两个。"""
        result = _merge_role_tags(["主角"], ["导师"])
        assert "主角" in result
        assert "导师" in result

    def test_mentor_vs_antagonist(self):
        """反派权重高于导师。"""
        result = _merge_role_tags(["导师"], ["反派"])
        assert result[0] == "反派"

    def test_all_types(self):
        """所有标签类型按权重排序。"""
        all_tags = ["路人", "配角", "主角", "伙伴", "导师", "反派", "BOSS"]
        result = _merge_role_tags([], all_tags)
        assert len(result) == 2
        assert result == ["主角", "反派"]


# ── _merge_single_character 中 role_tags 合并测试 ──────────────────

class TestMergeCharacterRoleTags:
    """测试人物合并时 role_tags 的行为。"""

    def test_chapter1_mentor_chapter2_mentor(self):
        """连续章节都是导师 → 保持导师。"""
        old = {"name": "富爸爸", "role_tags": ["导师"]}
        new = {"name": "富爸爸", "role_tags": ["导师"]}
        result = _merge_single_character(old, new)
        assert result["role_tags"] == ["导师"]

    def test_chapter1_supporting_chapter2_protagonist(self):
        """第一章节是配角，后续章节变主角 → 升级为主角。"""
        old = {"name": "罗伯特", "role_tags": ["配角"]}
        new = {"name": "罗伯特", "role_tags": ["主角"]}
        result = _merge_single_character(old, new)
        assert "主角" in result["role_tags"]

    def test_chapter1_protagonist_chapter2_supporting(self):
        """第一章节是主角，后续章节被标为配角 → 保持主角。"""
        old = {"name": "罗伯特", "role_tags": ["主角"]}
        new = {"name": "罗伯特", "role_tags": ["配角"]}
        result = _merge_single_character(old, new)
        assert "主角" in result["role_tags"]

    def test_empty_role_tags(self):
        """两方都无标签 → 空列表。"""
        old = {"name": "路人甲", "role_tags": []}
        new = {"name": "路人甲", "role_tags": []}
        result = _merge_single_character(old, new)
        assert result["role_tags"] == []

    def test_no_role_tags_field(self):
        """缺少 role_tags 字段 → 不报错。"""
        old = {"name": "某人"}
        new = {"name": "某人", "role_tags": ["反派"]}
        result = _merge_single_character(old, new)
        assert "反派" in result["role_tags"]


# ── _build_character_list_grouped 测试 ──────────────────────────────

class TestBuildCharacterListGrouped:
    """测试人物概览分组显示。"""

    def test_empty_characters(self):
        result = _build_character_list_grouped([])
        assert result == ["## 人物", ""]

    def test_protagonist_group(self):
        """主角应进入"核心人物"组。"""
        chars = [{"name": "罗伯特", "role_tags": ["主角"], "identity": "作者"}]
        result = _build_character_list_grouped(chars)
        text = "\n".join(result)
        assert "核心人物" in text
        assert "罗伯特" in text

    def test_antagonist_in_core_group(self):
        """反派应进入"核心人物"组。"""
        chars = [{"name": "大反派", "role_tags": ["反派"]}]
        result = _build_character_list_grouped(chars)
        text = "\n".join(result)
        assert "核心人物" in text

    def test_mentor_in_important_group(self):
        """导师应进入"重要配角"组。"""
        chars = [{"name": "富爸爸", "role_tags": ["导师"], "identity": "导师"}]
        result = _build_character_list_grouped(chars)
        text = "\n".join(result)
        assert "重要配角" in text

    def test_no_tags_in_other_group(self):
        """无标签人物应进入"其他人物"组。"""
        chars = [{"name": "路人甲"}]
        result = _build_character_list_grouped(chars)
        text = "\n".join(result)
        assert "其他人物" in text

    def test_mixed_groups(self):
        """混合分组：主角 + 导师 + 路人。"""
        chars = [
            {"name": "罗伯特", "role_tags": ["主角"], "identity": "作者"},
            {"name": "富爸爸", "role_tags": ["导师"], "identity": "导师"},
            {"name": "路人甲", "identity": "村民"},
        ]
        result = _build_character_list_grouped(chars)
        text = "\n".join(result)
        assert "核心人物" in text
        assert "重要配角" in text
        assert "其他人物" in text

    def test_role_tags_displayed(self):
        """标签应以代码格式显示。"""
        chars = [{"name": "罗伯特", "role_tags": ["主角"]}]
        result = _build_character_list_grouped(chars)
        text = "\n".join(result)
        assert "`主角`" in text
