"""
Story Wiki - Web 全局搜索 API 测试
重点：空库（从未建索引）的健壮性——CI 首跑抓到的真 bug：
LIKE 兜底查询在无表环境抛 OperationalError 导致 500。
"""

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

import src.db as sdb  # noqa: E402
from web.app import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """搜索指向临时空库，且确保鉴权关闭（走公开路径）。"""
    monkeypatch.setattr(sdb, "DEFAULT_DB_PATH", tmp_path / "wiki.db")
    monkeypatch.delenv("STORY_WIKI_PASSWORD", raising=False)
    return TestClient(app)


def test_search_on_fresh_db_returns_empty(client):
    """全新机器（从未建索引）搜索应返回空结果而非 500。"""
    res = client.get("/api/search", params={"q": "孙少安"})
    assert res.status_code == 200
    assert res.json() == {"results": [], "total": 0}


def test_search_blank_query(client):
    res = client.get("/api/search", params={"q": "   "})
    assert res.status_code == 200
    assert res.json() == {"results": [], "total": 0}


def test_search_with_index(client):
    """建好索引后同一路径能搜到实体。"""
    conn = sdb.connect(sdb.DEFAULT_DB_PATH)
    sdb.init_schema(conn)
    doc_id = sdb.upsert_document(conn, "测试之书", "测试之书/测试之书")
    sdb.upsert_entity(conn, doc_id, "character", "孙少安",
                      md_path="x.md", category="主要人物", summary="少安")
    conn.commit()
    conn.close()

    res = client.get("/api/search", params={"q": "孙少安"})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["results"][0]["name"] == "孙少安"
