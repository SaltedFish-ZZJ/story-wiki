"""核心分析链路的端到端 smoke test。"""

from src.generator import generate_vault
from src.pipeline import analyze_chaptered
from src.vault_manager import VaultManager


def test_analysis_to_vault_round_trip(tmp_path, monkeypatch):
    """固定 AI 响应经过分章、合并和生成后，必须能被 VaultManager 重读。"""
    chapter_results = iter([
        {
            "characters": [
                {
                    "name": "沈星",
                    "identity": "调查员",
                    "personality": "谨慎而坚定",
                    "gender": "女",
                    "faction": "城南调查局",
                    "role_tags": ["主角"],
                    "status": "活跃",
                    "aliases": ["阿星"],
                    "relationships": [{"target": "周野", "nature": "搭档"}],
                    "related_settings": ["旧钟楼"],
                }
            ],
            "settings": [
                {
                    "name": "旧钟楼",
                    "type": "地点",
                    "description": "城南废弃多年的钟楼。",
                    "related_characters": ["沈星", "周野"],
                }
            ],
            "events": [
                {
                    "name": "钟楼相遇",
                    "time": "雨夜",
                    "chapter": "第一章 雨夜",
                    "description": "沈星在旧钟楼遇见周野。",
                    "participants": ["沈星", "周野"],
                    "location": "旧钟楼",
                    "importance": "高",
                    "cause": [],
                }
            ],
            "chapter_summary": "沈星进入旧钟楼调查。",
        },
        {
            "characters": [
                {
                    "name": "沈星",
                    "identity": "调查员",
                    "relationships": [{"target": "周野", "nature": "搭档"}],
                },
                {
                    "name": "周野",
                    "identity": "守钟人",
                    "personality": "沉默敏锐",
                    "gender": "男",
                    "role_tags": ["配角"],
                    "status": "活跃",
                    "relationships": [{"target": "沈星", "nature": "搭档"}],
                    "related_settings": ["旧钟楼"],
                },
            ],
            "settings": [],
            "events": [
                {
                    "name": "钟楼相遇",
                    "participants": ["沈星", "周野"],
                    "cause": [],
                }
            ],
            "chapter_summary": "",
        },
    ])

    def fake_analyze_chapter(**_kwargs):
        return next(chapter_results)

    monkeypatch.setattr("src.pipeline.analyze_chapter", fake_analyze_chapter)
    monkeypatch.setattr("src.pipeline.generate_context_summary", lambda _result: "前章摘要")

    first_chapter = "沈星来到旧钟楼调查失踪案。" * 20
    second_chapter = "周野现身，并决定协助沈星。" * 20
    text = f"第一章 雨夜\n{first_chapter}\n第二章 守钟人\n{second_chapter}"
    analysis = analyze_chaptered(text, title="雾城来信", use_cache=False)

    assert {item["name"] for item in analysis["characters"]} == {"沈星", "周野"}
    assert [item["name"] for item in analysis["settings"]] == ["旧钟楼"]
    assert [item["name"] for item in analysis["events"]] == ["钟楼相遇"]

    generated = generate_vault(analysis, output_dir=tmp_path)
    assert generated

    manager = VaultManager({"vault_dir": tmp_path, "book_title": "雾城来信"})
    loaded = manager.load_all_cards()

    assert {item["name"] for item in loaded["characters"]} == {"沈星", "周野"}
    assert [item["name"] for item in loaded["settings"]] == ["旧钟楼"]
    assert [item["name"] for item in loaded["events"]] == ["钟楼相遇"]

    shen_xing = next(item for item in loaded["characters"] if item["name"] == "沈星")
    assert shen_xing["role_tags"] == ["主角"]
    assert shen_xing["relationships"] == [{"target": "周野", "nature": "搭档"}]
    assert shen_xing["related_settings"] == ["旧钟楼"]

    event = loaded["events"][0]
    assert set(event["participants"]) == {"沈星", "周野"}
    assert event["location"] == "旧钟楼"

    character_file = next((tmp_path / "雾城来信" / "characters").rglob("沈星.md"))
    character_text = character_file.read_text(encoding="utf-8")
    assert "type: character" in character_text
    assert "[[characters/次要人物/周野|周野]]" in character_text
    assert "[[settings/地点/旧钟楼|旧钟楼]]" in character_text
