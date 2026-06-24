"""
Story Wiki - VaultManager 单元测试
使用临时目录模拟 Obsidian Vault，测试读取、更新、添加、搜索、时间线等功能。
"""
import tempfile
from pathlib import Path

from src.vault_manager import (
    VaultManager,
    _parse_character_md,
    _parse_setting_md,
    _parse_event_md,
    _character_to_markdown,
    _setting_to_markdown,
    _event_to_markdown,
    _dict_to_character,
    _dict_to_setting,
    _dict_to_event,
    _character_to_dict,
    _setting_to_dict,
    _event_to_dict,
    _safe_filename,
    _card_matches_keyword,
)
from src.interfaces import Character, Setting, Event


# ── 辅助：创建测试用 Vault ──────────────────────────────────

def _create_test_vault(base_dir: Path, book_title: str = "测试作品"):
    """在临时目录中创建一个测试 Vault。"""
    book_dir = base_dir / _safe_filename(book_title)
    char_dir = book_dir / "characters"
    setting_dir = book_dir / "settings"
    event_dir = book_dir / "events"
    for d in [char_dir, setting_dir, event_dir]:
        d.mkdir(parents=True, exist_ok=True)
    return book_dir, char_dir, setting_dir, event_dir


def _sample_character_md(name: str = "贾宝玉") -> str:
    return f"""---
type: character
source: analyzed
origin: 测试作品
gender: 男
faction: 荣国府
aliases: [宝二爷, 怡红公子]
role_tags: [主角, 男主]
tags: [character]
created: 2026-01-01
---

# {name}

> 🟢 活跃 | 阵营：荣国府 | 定位：主角 · 男主

## 身份
荣国府公子，衔玉而生

## 性格
叛逆多情，厌恶仕途经济

## 人际关系
- [[characters/林黛玉|林黛玉]] — 恋人
- [[characters/薛宝钗|薛宝钗]] — 妻子

## 关联设定
- [[settings/大观园|大观园]]

## 🏆 高光时刻
- [[events/宝黛初见|宝黛初见]] — 宝黛二人初次相见

## 💬 经典语录
> "女儿是水作的骨肉，男人是泥作的骨肉。"

## 🕸️ 关系网

```mermaid
graph LR
    贾宝玉["贾宝玉"] -- "恋人" --> 林黛玉["林黛玉"]
```
"""


def _sample_setting_md(name: str = "大观园") -> str:
    return f"""---
type: setting
source: analyzed
origin: 测试作品
setting_type: 地点
tags: [setting]
created: 2026-01-01
---

# {name}

> 类型：地点 | 关联人物：2

**类型**：地点

贾府花园，是贾宝玉和众姐妹的居住地

## 关联人物
- [[characters/贾宝玉|贾宝玉]]
- [[characters/林黛玉|林黛玉]]

## 关联设定
- [[settings/荣国府|荣国府]]
"""


def _sample_event_md(name: str = "宝黛初见", time: str = "某日") -> str:
    return f"""---
type: event
source: analyzed
origin: 测试作品
time: {time}
chapter: 第三回
tags: [event]
created: 2026-01-01
---

# {name}

> 📍 荣国府 | 👥 3人参与 | 🔗 前置：1个事件

**时间**：{time}

林黛玉初入贾府，与贾宝玉初次相见

## 参与人物
- [[characters/林黛玉|林黛玉]]
- [[characters/贾宝玉|贾宝玉]]
- [[characters/贾母|贾母]]

## 发生地点
- [[settings/荣国府|荣国府]]

## 前置事件
- [[events/黛玉进贾府|黛玉进贾府]]
"""


# ══════════════════════════════════════════════════════════════
# 解析测试
# ══════════════════════════════════════════════════════════════

def test_parse_character_md():
    """测试人物 Markdown 解析。"""
    print("测试人物 Markdown 解析...")
    content = _sample_character_md()
    data = _parse_character_md(content)

    assert data is not None, "解析不应返回 None"
    assert data["name"] == "贾宝玉", f"名称应为贾宝玉，实际为 {data['name']}"
    assert data["gender"] == "男", f"性别应为男，实际为 {data['gender']}"
    assert data["faction"] == "荣国府", f"阵营应为荣国府，实际为 {data['faction']}"
    assert data["status"] == "活跃", f"状态应为活跃，实际为 {data['status']}"
    assert "宝二爷" in data["aliases"], "应包含别名宝二爷"
    assert "怡红公子" in data["aliases"], "应包含别名怡红公子"
    assert "主角" in data["role_tags"], "应包含角色标签主角"
    assert "衔玉而生" in data["identity"], "身份应包含衔玉而生"
    assert "叛逆多情" in data["personality"], "性格应包含叛逆多情"
    assert len(data["relationships"]) == 2, f"应有 2 条关系，实际为 {len(data['relationships'])}"
    assert data["relationships"][0]["target"] == "林黛玉", "第一个关系目标应为林黛玉"
    assert data["relationships"][0]["nature"] == "恋人", "第一个关系性质应为恋人"
    assert "大观园" in data["related_settings"], "应关联设定大观园"
    assert len(data["quotes"]) > 0, "应有语录"

    print("  [PASS] 人物 Markdown 解析测试通过")


def test_parse_setting_md():
    """测试设定 Markdown 解析。"""
    print("测试设定 Markdown 解析...")
    content = _sample_setting_md()
    data = _parse_setting_md(content)

    assert data is not None, "解析不应返回 None"
    assert data["name"] == "大观园", f"名称应为大观园，实际为 {data['name']}"
    assert data["type"] == "地点", f"类型应为地点，实际为 {data['type']}"
    assert "贾府花园" in data["description"], "描述应包含贾府花园"
    assert "贾宝玉" in data["related_characters"], "应关联人物贾宝玉"
    assert "荣国府" in data["related_settings"], "应关联设定荣国府"

    print("  [PASS] 设定 Markdown 解析测试通过")


def test_parse_event_md():
    """测试事件 Markdown 解析。"""
    print("测试事件 Markdown 解析...")
    content = _sample_event_md()
    data = _parse_event_md(content)

    assert data is not None, "解析不应返回 None"
    assert data["name"] == "宝黛初见", f"名称应为宝黛初见，实际为 {data['name']}"
    assert data["time"] == "某日", f"时间应为某日，实际为 {data['time']}"
    assert data["chapter"] == "第三回", f"章节应为第三回，实际为 {data['chapter']}"
    assert "林黛玉" in data["participants"], "应包含参与者林黛玉"
    assert "贾宝玉" in data["participants"], "应包含参与者贾宝玉"
    assert data["location"] == "荣国府", f"地点应为荣国府，实际为 {data['location']}"
    assert "黛玉进贾府" in data["cause"], "应包含前置事件黛玉进贾府"

    print("  [PASS] 事件 Markdown 解析测试通过")


# ══════════════════════════════════════════════════════════════
# Markdown 生成测试
# ══════════════════════════════════════════════════════════════

def test_character_to_markdown():
    """测试 Character -> Markdown 生成。"""
    print("测试 Character -> Markdown 生成...")
    char = Character(
        name="林黛玉",
        identity="林如海之女",
        personality="多愁善感",
        gender="女",
        faction="贾府",
        aliases=["颦儿"],
        role_tags=["女主"],
        status="活跃",
        relationships=[{"target": "贾宝玉", "nature": "恋人"}],
        related_settings=["潇湘馆"],
        quotes=["花谢花飞花满天"],
    )
    md = _character_to_markdown(char)

    assert "# 林黛玉" in md, "应包含标题"
    assert "type: character" in md, "应包含 frontmatter type"
    assert "林如海之女" in md, "应包含身份"
    assert "多愁善感" in md, "应包含性格"
    assert "[[characters/贾宝玉" in md, "应包含人际关系 wikilink"
    assert "恋人" in md, "应包含关系性质"
    assert "[[settings/潇湘馆" in md, "应包含关联设定"
    assert "花谢花飞花满天" in md, "应包含语录"

    print("  [PASS] Character -> Markdown 生成测试通过")


def test_setting_to_markdown():
    """测试 Setting -> Markdown 生成。"""
    print("测试 Setting -> Markdown 生成...")
    setting = Setting(
        name="潇湘馆",
        type="地点",
        description="林黛玉居住的竹林小院",
        related_characters=["林黛玉"],
        related_settings=["大观园"],
    )
    md = _setting_to_markdown(setting)

    assert "# 潇湘馆" in md, "应包含标题"
    assert "type: setting" in md, "应包含 frontmatter type"
    assert "林黛玉居住的竹林小院" in md, "应包含描述"
    assert "[[characters/林黛玉" in md, "应包含关联人物"
    assert "[[settings/大观园" in md, "应包含关联设定"

    print("  [PASS] Setting -> Markdown 生成测试通过")


def test_event_to_markdown():
    """测试 Event -> Markdown 生成。"""
    print("测试 Event -> Markdown 生成...")
    event = Event(
        name="元妃省亲",
        time="元宵节",
        participants=["贾元春", "贾宝玉"],
        location="大观园",
        description="贾元春回贾府省亲",
        cause=["建造大观园"],
        chapter="第十八回",
    )
    md = _event_to_markdown(event)

    assert "# 元妃省亲" in md, "应包含标题"
    assert "type: event" in md, "应包含 frontmatter type"
    assert "元宵节" in md, "应包含时间"
    assert "[[characters/贾元春" in md, "应包含参与人物"
    assert "[[settings/大观园" in md, "应包含发生地点"
    assert "[[events/建造大观园" in md, "应包含前置事件"

    print("  [PASS] Event -> Markdown 生成测试通过")


# ══════════════════════════════════════════════════════════════
# 数据结构转换测试
# ══════════════════════════════════════════════════════════════

def test_dict_character_roundtrip():
    """测试 Character dict -> dataclass -> dict 往返转换。"""
    print("测试 Character 往返转换...")
    original = {
        "name": "贾宝玉",
        "identity": "荣国府公子",
        "personality": "叛逆多情",
        "gender": "男",
        "faction": "荣国府",
        "aliases": ["宝二爷"],
        "role_tags": ["主角"],
        "status": "活跃",
        "relationships": [{"target": "林黛玉", "nature": "恋人"}],
        "related_settings": ["大观园"],
        "quotes": ["女儿是水作的骨肉"],
        "motivation": "追求自由",
        "current_state": "在贾府",
    }
    char = _dict_to_character(original)
    result = _character_to_dict(char)

    for key in original:
        assert result[key] == original[key], f"字段 {key} 不一致: {result[key]} != {original[key]}"

    print("  [PASS] Character 往返转换测试通过")


def test_dict_setting_roundtrip():
    """测试 Setting dict -> dataclass -> dict 往返转换。"""
    print("测试 Setting 往返转换...")
    original = {
        "name": "大观园",
        "type": "地点",
        "description": "贾府花园",
        "related_characters": ["贾宝玉"],
        "related_settings": ["荣国府"],
    }
    setting = _dict_to_setting(original)
    result = _setting_to_dict(setting)

    for key in original:
        assert result[key] == original[key], f"字段 {key} 不一致"

    print("  [PASS] Setting 往返转换测试通过")


def test_dict_event_roundtrip():
    """测试 Event dict -> dataclass -> dict 往返转换。"""
    print("测试 Event 往返转换...")
    original = {
        "name": "宝黛初见",
        "time": "某日",
        "participants": ["贾宝玉", "林黛玉"],
        "location": "荣国府",
        "description": "初次相见",
        "cause": ["黛玉进贾府"],
        "effect": [],
        "chapter": "第三回",
        "importance": "重要",
    }
    event = _dict_to_event(original)
    result = _event_to_dict(event)

    for key in original:
        assert result[key] == original[key], f"字段 {key} 不一致"

    print("  [PASS] Event 往返转换测试通过")


# ══════════════════════════════════════════════════════════════
# VaultManager 功能测试
# ══════════════════════════════════════════════════════════════

def test_load_all_cards():
    """测试 load_all_cards 功能。"""
    print("测试 load_all_cards...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, char_dir, setting_dir, event_dir = _create_test_vault(base)

        # 写入测试文件
        (char_dir / "贾宝玉.md").write_text(_sample_character_md("贾宝玉"), encoding="utf-8")
        (setting_dir / "大观园.md").write_text(_sample_setting_md("大观园"), encoding="utf-8")
        (event_dir / "宝黛初见.md").write_text(_sample_event_md("宝黛初见", "某日"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        all_cards = vm.load_all_cards()

        assert len(all_cards["characters"]) == 1, f"应有 1 个人物，实际为 {len(all_cards['characters'])}"
        assert all_cards["characters"][0]["name"] == "贾宝玉"
        assert len(all_cards["settings"]) == 1, f"应有 1 个设定，实际为 {len(all_cards['settings'])}"
        assert all_cards["settings"][0]["name"] == "大观园"
        assert len(all_cards["events"]) == 1, f"应有 1 个事件，实际为 {len(all_cards['events'])}"
        assert all_cards["events"][0]["name"] == "宝黛初见"

    print("  [PASS] load_all_cards 测试通过")


def test_load_single_character():
    """测试 load_character 功能。"""
    print("测试 load_character...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, char_dir, _, _ = _create_test_vault(base)
        (char_dir / "贾宝玉.md").write_text(_sample_character_md("贾宝玉"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        char = vm.load_character("贾宝玉")

        assert char is not None, "不应返回 None"
        assert isinstance(char, Character), "应返回 Character 对象"
        assert char.name == "贾宝玉"
        assert char.gender == "男"
        assert char.faction == "荣国府"
        assert len(char.relationships) == 2

        # 测试不存在的人物
        char_none = vm.load_character("不存在的人")
        assert char_none is None, "不存在的人物应返回 None"

    print("  [PASS] load_character 测试通过")


def test_load_single_setting():
    """测试 load_setting 功能。"""
    print("测试 load_setting...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, _, setting_dir, _ = _create_test_vault(base)
        (setting_dir / "大观园.md").write_text(_sample_setting_md("大观园"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        setting = vm.load_setting("大观园")

        assert setting is not None, "不应返回 None"
        assert isinstance(setting, Setting), "应返回 Setting 对象"
        assert setting.name == "大观园"
        assert setting.type == "地点"
        assert "贾宝玉" in setting.related_characters

    print("  [PASS] load_setting 测试通过")


def test_load_single_event():
    """测试 load_event 功能。"""
    print("测试 load_event...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, _, _, event_dir = _create_test_vault(base)
        (event_dir / "宝黛初见.md").write_text(_sample_event_md("宝黛初见", "某日"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        event = vm.load_event("宝黛初见")

        assert event is not None, "不应返回 None"
        assert isinstance(event, Event), "应返回 Event 对象"
        assert event.name == "宝黛初见"
        assert event.time == "某日"
        assert "贾宝玉" in event.participants

    print("  [PASS] load_event 测试通过")


def test_update_character():
    """测试 update_character 功能。"""
    print("测试 update_character...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, char_dir, _, _ = _create_test_vault(base)
        (char_dir / "贾宝玉.md").write_text(_sample_character_md("贾宝玉"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})

        # 更新身份
        vm.update_character("贾宝玉", {"identity": "荣国府公子，衔玉而生，贾政次子"})
        char = vm.load_character("贾宝玉")
        assert char.identity == "荣国府公子，衔玉而生，贾政次子", f"身份更新失败: {char.identity}"

        # 更新状态
        vm.update_character("贾宝玉", {"status": "已故"})
        char = vm.load_character("贾宝玉")
        assert char.status == "已故", f"状态更新失败: {char.status}"

        # 更新不存在的人物应抛出异常
        try:
            vm.update_character("不存在", {"identity": "test"})
            assert False, "应抛出 FileNotFoundError"
        except FileNotFoundError:
            pass

    print("  [PASS] update_character 测试通过")


def test_update_setting():
    """测试 update_setting 功能。"""
    print("测试 update_setting...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, _, setting_dir, _ = _create_test_vault(base)
        (setting_dir / "大观园.md").write_text(_sample_setting_md("大观园"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})

        vm.update_setting("大观园", {"description": "贾府花园，面积很大"})
        setting = vm.load_setting("大观园")
        assert "面积很大" in setting.description, f"描述更新失败: {setting.description}"

    print("  [PASS] update_setting 测试通过")


def test_update_event():
    """测试 update_event 功能。"""
    print("测试 update_event...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, _, _, event_dir = _create_test_vault(base)
        (event_dir / "宝黛初见.md").write_text(_sample_event_md("宝黛初见", "某日"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})

        vm.update_event("宝黛初见", {"time": "春天"})
        event = vm.load_event("宝黛初见")
        assert event.time == "春天", f"时间更新失败: {event.time}"

    print("  [PASS] update_event 测试通过")


def test_add_character():
    """测试 add_character 功能。"""
    print("测试 add_character...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})

        char = Character(name="王熙凤", identity="贾琏之妻", personality="精明强干", gender="女")
        vm.add_character(char)

        loaded = vm.load_character("王熙凤")
        assert loaded is not None, "添加后应能加载"
        assert loaded.name == "王熙凤"
        assert loaded.identity == "贾琏之妻"

    print("  [PASS] add_character 测试通过")


def test_add_setting():
    """测试 add_setting 功能。"""
    print("测试 add_setting...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})

        setting = Setting(name="潇湘馆", type="地点", description="林黛玉居所")
        vm.add_setting(setting)

        loaded = vm.load_setting("潇湘馆")
        assert loaded is not None, "添加后应能加载"
        assert loaded.name == "潇湘馆"

    print("  [PASS] add_setting 测试通过")


def test_add_event():
    """测试 add_event 功能。"""
    print("测试 add_event...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})

        event = Event(
            name="刘姥姥进大观园",
            time="秋天",
            participants=["刘姥姥", "贾宝玉"],
            location="大观园",
            description="刘姥姥二进荣国府",
        )
        vm.add_event(event)

        loaded = vm.load_event("刘姥姥进大观园")
        assert loaded is not None, "添加后应能加载"
        assert loaded.name == "刘姥姥进大观园"
        assert "刘姥姥" in loaded.participants

    print("  [PASS] add_event 测试通过")


def test_search_cards():
    """测试 search_cards 功能。"""
    print("测试 search_cards...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, char_dir, setting_dir, event_dir = _create_test_vault(base)
        (char_dir / "贾宝玉.md").write_text(_sample_character_md("贾宝玉"), encoding="utf-8")
        (setting_dir / "大观园.md").write_text(_sample_setting_md("大观园"), encoding="utf-8")
        (event_dir / "宝黛初见.md").write_text(_sample_event_md("宝黛初见", "某日"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})

        # 搜索人物名
        results = vm.search_cards("贾宝玉")
        assert len(results["characters"]) == 1, "应搜到贾宝玉"
        assert results["characters"][0]["name"] == "贾宝玉"

        # 搜索设定名
        results = vm.search_cards("大观园")
        assert len(results["settings"]) == 1, "应搜到大观园"

        # 搜索事件名
        results = vm.search_cards("宝黛初见")
        assert len(results["events"]) == 1, "应搜到宝黛初见"

        # 搜索关键词（在身份中）
        results = vm.search_cards("荣国府")
        assert len(results["characters"]) == 1, "应通过身份搜到贾宝玉"

        # 搜索不存在的内容
        results = vm.search_cards("完全无关的关键词")
        assert len(results["characters"]) == 0
        assert len(results["settings"]) == 0
        assert len(results["events"]) == 0

    print("  [PASS] search_cards 测试通过")


def test_get_timeline():
    """测试 get_timeline 功能。"""
    print("测试 get_timeline...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, _, _, event_dir = _create_test_vault(base)
        (event_dir / "事件A.md").write_text(
            _sample_event_md("事件A", "2024-01-01"), encoding="utf-8"
        )
        (event_dir / "事件B.md").write_text(
            _sample_event_md("事件B", "2023-06-15"), encoding="utf-8"
        )
        (event_dir / "事件C.md").write_text(
            _sample_event_md("事件C", "2025-03-20"), encoding="utf-8"
        )

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        timeline = vm.get_timeline()

        assert len(timeline) == 3, f"应有 3 个事件，实际为 {len(timeline)}"
        # 按时间排序
        assert timeline[0]["time"] == "2023-06-15", f"第一个事件时间应为 2023-06-15，实际为 {timeline[0]['time']}"
        assert timeline[1]["time"] == "2024-01-01", f"第二个事件时间应为 2024-01-01，实际为 {timeline[1]['time']}"
        assert timeline[2]["time"] == "2025-03-20", f"第三个事件时间应为 2025-03-20，实际为 {timeline[2]['time']}"

    print("  [PASS] get_timeline 测试通过")


# ══════════════════════════════════════════════════════════════
# run() 和 validate() 接口测试
# ══════════════════════════════════════════════════════════════

def test_run_load_all():
    """测试 run(action=load_all)。"""
    print("测试 run(load_all)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, char_dir, _, _ = _create_test_vault(base)
        (char_dir / "贾宝玉.md").write_text(_sample_character_md("贾宝玉"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        result = vm.run({"action": "load_all"})

        assert "characters" in result
        assert len(result["characters"]) == 1
        assert vm.validate(result)

    print("  [PASS] run(load_all) 测试通过")


def test_run_load_single():
    """测试 run(action=load)。"""
    print("测试 run(load)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, char_dir, _, _ = _create_test_vault(base)
        (char_dir / "贾宝玉.md").write_text(_sample_character_md("贾宝玉"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        result = vm.run({"action": "load", "card_type": "character", "name": "贾宝玉"})

        assert "result" in result
        assert result["result"]["name"] == "贾宝玉"
        assert vm.validate(result)

    print("  [PASS] run(load) 测试通过")


def test_run_update():
    """测试 run(action=update)。"""
    print("测试 run(update)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, char_dir, _, _ = _create_test_vault(base)
        (char_dir / "贾宝玉.md").write_text(_sample_character_md("贾宝玉"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        result = vm.run({
            "action": "update",
            "card_type": "character",
            "name": "贾宝玉",
            "updates": {"identity": "更新后的身份"},
        })

        assert result.get("success") is True
        char = vm.load_character("贾宝玉")
        assert char.identity == "更新后的身份"

    print("  [PASS] run(update) 测试通过")


def test_run_add():
    """测试 run(action=add)。"""
    print("测试 run(add)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})

        result = vm.run({
            "action": "add",
            "card_type": "event",
            "card_data": {
                "name": "测试事件",
                "time": "某天",
                "participants": ["测试人物"],
            },
        })

        assert result.get("success") is True
        event = vm.load_event("测试事件")
        assert event is not None

    print("  [PASS] run(add) 测试通过")


def test_run_search():
    """测试 run(action=search)。"""
    print("测试 run(search)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, char_dir, _, _ = _create_test_vault(base)
        (char_dir / "贾宝玉.md").write_text(_sample_character_md("贾宝玉"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        result = vm.run({"action": "search", "keyword": "贾宝玉"})

        assert "characters" in result
        assert len(result["characters"]) == 1
        assert vm.validate(result)

    print("  [PASS] run(search) 测试通过")


def test_run_timeline():
    """测试 run(action=timeline)。"""
    print("测试 run(timeline)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, _, _, event_dir = _create_test_vault(base)
        (event_dir / "事件1.md").write_text(
            _sample_event_md("事件1", "2024-01-01"), encoding="utf-8"
        )

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        result = vm.run({"action": "timeline"})

        assert "timeline" in result
        assert len(result["timeline"]) == 1
        assert vm.validate(result)

    print("  [PASS] run(timeline) 测试通过")


def test_run_unknown_action():
    """测试未知操作。"""
    print("测试 run(unknown_action)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        result = vm.run({"action": "nonexistent"})
        assert "error" in result
        assert vm.validate(result)

    print("  [PASS] run(unknown_action) 测试通过")


def test_validate():
    """测试 validate 方法。"""
    print("测试 validate 方法...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})

        assert vm.validate({"characters": [], "settings": [], "events": []})
        assert vm.validate({"result": None})
        assert vm.validate({"success": True})
        assert vm.validate({"error": "test"})
        assert vm.validate({"timeline": []})
        assert not vm.validate("not a dict")
        assert not vm.validate({"random_key": 123})

    print("  [PASS] validate 方法测试通过")


# ══════════════════════════════════════════════════════════════
# 辅助函数测试
# ══════════════════════════════════════════════════════════════

def test_safe_filename():
    """测试安全文件名。"""
    print("测试安全文件名...")
    assert _safe_filename("正常名称") == "正常名称"
    assert _safe_filename('含<>特殊字符') == "含__特殊字符"
    assert _safe_filename("含/\\斜杠") == "含__斜杠"
    assert _safe_filename("含:?引号") == "含__引号"

    print("  [PASS] 安全文件名测试通过")


def test_card_matches_keyword():
    """测试卡片关键词匹配。"""
    print("测试卡片关键词匹配...")
    card = {
        "name": "贾宝玉",
        "identity": "荣国府公子",
        "personality": "叛逆多情",
        "faction": "荣国府",
        "aliases": ["宝二爷"],
        "relationships": [{"target": "林黛玉", "nature": "恋人"}],
    }

    assert _card_matches_keyword(card, "贾宝玉")
    assert _card_matches_keyword(card, "荣国府")
    assert _card_matches_keyword(card, "叛逆")
    assert _card_matches_keyword(card, "宝二爷")
    assert _card_matches_keyword(card, "林黛玉")
    assert _card_matches_keyword(card, "恋人")
    assert not _card_matches_keyword(card, "不存在的内容")

    print("  [PASS] 卡片关键词匹配测试通过")


def test_load_empty_vault():
    """测试加载空 Vault（无文件）。"""
    print("测试加载空 Vault...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        vm = VaultManager({"vault_dir": base, "book_title": "空作品"})
        all_cards = vm.load_all_cards()

        assert all_cards["characters"] == []
        assert all_cards["settings"] == []
        assert all_cards["events"] == []

    print("  [PASS] 空 Vault 测试通过")


def test_load_nonexistent_vault():
    """测试加载不存在的 Vault 目录。"""
    print("测试加载不存在的 Vault...")
    vm = VaultManager({"vault_dir": Path("/nonexistent/path"), "book_title": "不存在"})
    all_cards = vm.load_all_cards()

    assert all_cards["characters"] == []
    assert all_cards["settings"] == []
    assert all_cards["events"] == []

    print("  [PASS] 不存在 Vault 测试通过")


def test_corrupt_file_handling():
    """测试损坏文件的容错处理。"""
    print("测试损坏文件容错...")
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        book_dir, char_dir, _, _ = _create_test_vault(base)
        # 写入一个没有标题的损坏文件
        (char_dir / "损坏.md").write_text("这不是一个有效的人物卡片", encoding="utf-8")
        # 写入一个正常的文件
        (char_dir / "贾宝玉.md").write_text(_sample_character_md("贾宝玉"), encoding="utf-8")

        vm = VaultManager({"vault_dir": base, "book_title": "测试作品"})
        all_cards = vm.load_all_cards()

        # 损坏文件应被跳过，正常文件应被加载
        assert len(all_cards["characters"]) == 1
        assert all_cards["characters"][0]["name"] == "贾宝玉"

    print("  [PASS] 损坏文件容错测试通过")


# ══════════════════════════════════════════════════════════════
# 主函数
# ══════════════════════════════════════════════════════════════

def run_all_tests():
    """运行所有测试。"""
    print("=" * 60)
    print("VaultManager 单元测试")
    print("=" * 60)

    tests = [
        # 解析测试
        test_parse_character_md,
        test_parse_setting_md,
        test_parse_event_md,
        # Markdown 生成测试
        test_character_to_markdown,
        test_setting_to_markdown,
        test_event_to_markdown,
        # 数据结构转换测试
        test_dict_character_roundtrip,
        test_dict_setting_roundtrip,
        test_dict_event_roundtrip,
        # VaultManager 功能测试
        test_load_all_cards,
        test_load_single_character,
        test_load_single_setting,
        test_load_single_event,
        test_update_character,
        test_update_setting,
        test_update_event,
        test_add_character,
        test_add_setting,
        test_add_event,
        test_search_cards,
        test_get_timeline,
        # 接口测试
        test_run_load_all,
        test_run_load_single,
        test_run_update,
        test_run_add,
        test_run_search,
        test_run_timeline,
        test_run_unknown_action,
        test_validate,
        # 辅助函数测试
        test_safe_filename,
        test_card_matches_keyword,
        test_load_empty_vault,
        test_load_nonexistent_vault,
        test_corrupt_file_handling,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test.__name__} 失败: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {test.__name__} 异常: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 个")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
