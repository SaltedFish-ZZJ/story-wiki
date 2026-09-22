"""
Story Wiki - Graph View 分色 + 子文件夹分类函数测试

覆盖 generator.py 中新增的颜色/子文件夹分类逻辑。
"""
from src.generator import (
    _get_character_color,
    _get_setting_color,
    _get_event_color,
    _get_character_subfolder,
    _get_setting_subfolder,
    _get_event_subfolder,
    _build_entity_maps,
    _char_link,
    _setting_link,
    _event_link,
)


class TestCharacterColor:
    """人物颜色分类。"""

    def test_protagonist(self):
        assert _get_character_color(["主角"]) == "character-protagonist"

    def test_heroine(self):
        assert _get_character_color(["女主"]) == "character-protagonist"

    def test_hero(self):
        assert _get_character_color(["男主"]) == "character-protagonist"

    def test_antagonist(self):
        assert _get_character_color(["反派"]) == "character-protagonist"

    def test_supporting(self):
        assert _get_character_color(["配角"]) == "character-important"

    def test_mentor(self):
        assert _get_character_color(["导师"]) == "character-important"

    def test_partner(self):
        assert _get_character_color(["伙伴"]) == "character-important"

    def test_boss(self):
        assert _get_character_color(["BOSS"]) == "character-important"

    def test_hidden(self):
        assert _get_character_color(["隐藏角色"]) == "character-important"

    def test_minor_no_tags(self):
        assert _get_character_color([]) == "character-minor"

    def test_minor_none(self):
        assert _get_character_color(None) == "character-minor"

    def test_minor_unknown_tag(self):
        assert _get_character_color(["路人"]) == "character-minor"

    def test_mixed_tags_protagonist_wins(self):
        assert _get_character_color(["配角", "主角"]) == "character-protagonist"

    def test_mixed_tags_important_wins(self):
        assert _get_character_color(["路人", "导师"]) == "character-important"


class TestSettingColor:
    """设定颜色分类。"""

    def test_location(self):
        assert _get_setting_color("地点") == "setting-location"

    def test_city(self):
        assert _get_setting_color("城市") == "setting-location"

    def test_country(self):
        assert _get_setting_color("国家") == "setting-location"

    def test_organization(self):
        assert _get_setting_color("组织") == "setting-organization"

    def test_company(self):
        assert _get_setting_color("公司") == "setting-organization"

    def test_faction(self):
        assert _get_setting_color("势力") == "setting-organization"

    def test_concept(self):
        assert _get_setting_color("概念") == "setting-concept"

    def test_concept_none(self):
        assert _get_setting_color(None) == "setting-concept"

    def test_concept_empty(self):
        assert _get_setting_color("") == "setting-concept"


class TestEventColor:
    """事件颜色分类。"""

    def test_major(self):
        assert _get_event_color("高") == "event-major"

    def test_normal(self):
        assert _get_event_color("中") == "event-normal"

    def test_minor(self):
        assert _get_event_color("低") == "event-minor"

    def test_empty(self):
        assert _get_event_color("") == "event-normal"

    def test_none(self):
        assert _get_event_color(None) == "event-normal"


class TestCharacterSubfolder:
    """人物子文件夹分类。"""

    def test_protagonist_folder(self):
        assert _get_character_subfolder(["主角"]) == "主要人物"

    def test_supporting_folder(self):
        assert _get_character_subfolder(["配角"]) == "次要人物"

    def test_other_folder(self):
        assert _get_character_subfolder([]) == "其他人物"

    def test_none_folder(self):
        assert _get_character_subfolder(None) == "其他人物"


class TestSettingSubfolder:
    """设定子文件夹分类。"""

    def test_location_folder(self):
        assert _get_setting_subfolder("地点") == "地点"

    def test_organization_folder(self):
        assert _get_setting_subfolder("组织") == "组织"

    def test_concept_folder(self):
        assert _get_setting_subfolder("概念") == "概念"

    def test_none_folder(self):
        assert _get_setting_subfolder(None) == "概念"


class TestEventSubfolder:
    """事件子文件夹分类。"""

    def test_major_folder(self):
        assert _get_event_subfolder("高") == "重大事件"

    def test_normal_folder(self):
        assert _get_event_subfolder("中") == "一般事件"

    def test_minor_folder(self):
        assert _get_event_subfolder("低") == "一般事件"

    def test_empty_folder(self):
        assert _get_event_subfolder("") == "一般事件"


class TestBuildEntityMaps:
    """实体映射表构建。"""

    def test_basic_maps(self):
        characters = [
            {"name": "主角", "role_tags": ["主角"]},
            {"name": "配角", "role_tags": ["配角"]},
            {"name": "路人"},
        ]
        settings = [
            {"name": "北京", "type": "地点"},
            {"name": "魔教", "type": "组织"},
            {"name": "规则", "type": "体系"},
        ]
        events = [
            {"name": "大战", "importance": "高"},
            {"name": "日常", "importance": "中"},
        ]

        char_map, setting_map, event_map = _build_entity_maps(characters, settings, events)

        assert char_map == {"主角": "主要人物", "配角": "次要人物", "路人": "其他人物"}
        assert setting_map == {"北京": "地点", "魔教": "组织", "规则": "概念"}
        assert event_map == {"大战": "重大事件", "日常": "一般事件"}

    def test_empty_maps(self):
        char_map, setting_map, event_map = _build_entity_maps([], [], [])
        assert char_map == {}
        assert setting_map == {}
        assert event_map == {}


class TestWikilinkHelpers:
    """Wikilink 生成函数。"""

    def test_char_link_known(self):
        assert _char_link("主角", {"主角": "主要人物"}) == "[[characters/主要人物/主角|主角]]"

    def test_char_link_unknown(self):
        assert _char_link("路人", {}) == "[[characters/其他人物/路人|路人]]"

    def test_setting_link_known(self):
        assert _setting_link("北京", {"北京": "地点"}) == "[[settings/地点/北京|北京]]"

    def test_setting_link_unknown(self):
        assert _setting_link("未知", {}) == "[[settings/概念/未知|未知]]"

    def test_event_link_known(self):
        assert _event_link("大战", {"大战": "重大事件"}) == "[[events/重大事件/大战|大战]]"

    def test_event_link_unknown(self):
        assert _event_link("小事", {}) == "[[events/一般事件/小事|小事]]"
