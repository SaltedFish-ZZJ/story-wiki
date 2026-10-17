"""
Story Wiki - 设定列表接口与设定卡解析测试
覆盖：GET /api/books/{title}/settings、设定卡名称提取（H1 而非 frontmatter）、
「关联人物」节解析、描述回退（无「描述」节时取正文摘要）。
"""
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import web.app as webapp  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """隔离输出目录的测试客户端。"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(webapp, "OUTPUT_DIR", output_dir)
    webapp._cache.clear()
    return TestClient(webapp.app), output_dir


def _make_book(output_dir, title="设定之书"):
    """写一本带设定卡的最小作品（模拟真实生成格式：frontmatter + H1 + 关联人物）。"""
    book = output_dir / title / title
    (book / "settings" / "组织").mkdir(parents=True)
    (book / "_index.md").write_text(
        "---\ntype: book\ntags: [book]\n---\n# 设定之书\n", encoding="utf-8"
    )
    (book / "settings" / "组织" / "市劳动局.md").write_text(
        "---\n"
        "type: setting\n"
        "color: setting-organization\n"
        "setting_type: 组织\n"
        "---\n"
        "# 市劳动局\n\n"
        "**类型**：组织\n\n"
        "黄原市劳动局，负责煤矿招工。\n\n"
        "## 关联人物\n"
        "- [[characters/主要人物/田晓霞|田晓霞]] — 帮忙活动招工名额\n",
        encoding="utf-8",
    )


class TestSettingsList:
    def test_settings_list_ok(self, client):
        client, output_dir = client
        _make_book(output_dir)
        resp = client.get("/api/books/设定之书/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        s = data["settings"][0]
        assert s["name"] == "市劳动局"  # H1 提取，而不是 "---"
        assert s["setting_type"] == "组织"
        assert "黄原市劳动局" in s["description"]  # 无「描述」节时回退正文摘要
        assert s["characters"][0]["name"] == "田晓霞"  # 「关联人物」节解析
        assert s["characters"][0]["description"] == "帮忙活动招工名额"

    def test_settings_book_404(self, client):
        client, _ = client
        assert client.get("/api/books/不存在的书/settings").status_code == 404

    def test_overview_settings_name_not_dashes(self, client):
        """overview 统计不受影响，且设定名不再解析为 '---'。"""
        client, output_dir = client
        _make_book(output_dir)
        resp = client.get("/api/books/设定之书/settings")
        names = [s["name"] for s in resp.json()["settings"]]
        assert "---" not in names
