"""Web 设置页接口测试：LLM 配置读取/保存/.env 写回/热更新/鉴权/连接测试。

.env 写入通过 monkeypatch PROJECT_ROOT 隔离到 tmp_path，不会碰真实配置。
"""
from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """鉴权关闭 + 环境变量与 .env 隔离的 TestClient。"""
    monkeypatch.delenv("STORY_WIKI_PASSWORD", raising=False)
    monkeypatch.delenv("STORY_WIKI_API_KEY", raising=False)
    monkeypatch.delenv("STORY_WIKI_BASE_URL", raising=False)
    monkeypatch.delenv("STORY_WIKI_MODEL", raising=False)
    monkeypatch.setattr("src.config.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("web.app.BASE_DIR", tmp_path)  # .env 持久化路径隔离
    from web.app import app

    return TestClient(app)


@pytest.fixture()
def fake_consumer_module(monkeypatch):
    """在 sys.modules 里造一个模拟 `from config import DEEPSEEK_*` 的消费模块。"""
    mod = types.ModuleType("src._fake_consumer")
    mod.DEEPSEEK_API_KEY = "old-key"
    mod.DEEPSEEK_BASE_URL = "https://old.example.com"
    mod.DEEPSEEK_MODEL = "old-model"
    monkeypatch.setitem(sys.modules, "src._fake_consumer", mod)
    monkeypatch.setattr(
        "src.config._LLM_CONSUMER_MODULES",
        ("src._fake_consumer",),
    )
    return mod


# ── GET /api/settings ────────────────────────────────────────


def test_get_settings_masks_key(client, monkeypatch):
    monkeypatch.setenv("STORY_WIKI_API_KEY", "sk-1234567890abcdef")
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["api_key_masked"] == "sk-***cdef"
    assert data["has_api_key"] is True
    # 响应里绝不能出现完整 Key
    assert "sk-1234567890abcdef" not in res.text


def test_get_settings_empty(client):
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["has_api_key"] is False
    assert data["api_key_masked"] == ""
    assert data["base_url"]  # 有默认值
    assert data["model"]


# ── POST /api/settings ───────────────────────────────────────


def test_save_settings_writes_env_and_runtime(client, tmp_path):
    res = client.post(
        "/api/settings",
        json={
            "api_key": "sk-newkey123456",
            "base_url": "https://api.example.com",
            "model": "test-model",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["saved"] is True
    assert data["api_key_masked"] == "sk-***3456"

    # .env 写入 tmp_path（PROJECT_ROOT 已被打补丁）
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "STORY_WIKI_API_KEY=sk-newkey123456" in env_text
    assert "STORY_WIKI_BASE_URL=https://api.example.com" in env_text
    assert "STORY_WIKI_MODEL=test-model" in env_text

    # 运行时配置同步生效
    from src import config

    assert config.DEEPSEEK_API_KEY == "sk-newkey123456"
    assert config.DEEPSEEK_BASE_URL == "https://api.example.com"


def test_save_settings_blank_key_keeps_old(client, tmp_path, monkeypatch):
    monkeypatch.setenv("STORY_WIKI_API_KEY", "sk-existing123456")
    res = client.post(
        "/api/settings",
        json={"api_key": "", "model": "mimo-v2.5"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["has_api_key"] is True
    # 留空的 Key 不应被写进 .env
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "STORY_WIKI_API_KEY" not in env_text
    assert "STORY_WIKI_MODEL=mimo-v2.5" in env_text


def test_save_settings_rejects_bad_base_url(client):
    res = client.post("/api/settings", json={"base_url": "ftp://bad.example.com"})
    assert res.status_code == 400


def test_save_settings_preserves_env_comments(client, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# 我的注释\nSTORY_WIKI_MODEL=old-model\nSTORY_WIKI_VAULT=./vault\n",
        encoding="utf-8",
    )
    res = client.post("/api/settings", json={"model": "new-model"})
    assert res.status_code == 200
    text = env_file.read_text(encoding="utf-8")
    assert "# 我的注释" in text
    assert "STORY_WIKI_MODEL=new-model" in text
    assert "STORY_WIKI_VAULT=./vault" in text  # 无关键保留
    assert "old-model" not in text


# ── 热更新：已加载消费模块的绑定同步 ─────────────────────────


def test_set_llm_config_rebinds_consumers(fake_consumer_module):
    from src import config

    config.set_llm_config(
        api_key="sk-fresh1234567",
        base_url="https://fresh.example.com",
        model="fresh-model",
        env_path=None,  # 不落盘：持久化必须显式传路径
    )
    assert fake_consumer_module.DEEPSEEK_API_KEY == "sk-fresh1234567"
    assert fake_consumer_module.DEEPSEEK_BASE_URL == "https://fresh.example.com"
    assert fake_consumer_module.DEEPSEEK_MODEL == "fresh-model"


def test_mask_key_edge_cases():
    from src.config import mask_key

    assert mask_key("") == ""
    assert mask_key("short") == "***"
    assert mask_key("12345678") == "***"
    assert mask_key("123456789") == "123***6789"


# ── 鉴权 ─────────────────────────────────────────────────────


def test_settings_require_auth_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("STORY_WIKI_PASSWORD", "unit-pw")
    monkeypatch.setattr("src.config.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("web.app.BASE_DIR", tmp_path)
    from web.app import app

    with TestClient(app) as c:
        assert c.get("/api/settings").status_code == 401
        assert c.post("/api/settings", json={}).status_code == 401
        assert c.post("/api/settings/test", json={}).status_code == 401

        # 登录后可访问
        res = c.post("/login", data={"password": "unit-pw"}, follow_redirects=False)
        assert res.status_code == 303
        assert c.get("/api/settings").status_code == 200


# ── POST /api/settings/test（mock 网络）─────────────────────


class _FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text

    def json(self):
        return {"error": {"message": "boom"}}


def test_settings_test_ok(client, monkeypatch):
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["json"] = kwargs.get("json")
        return _FakeResp(200)

    monkeypatch.setattr("requests.post", fake_post)
    res = client.post(
        "/api/settings/test",
        json={"base_url": "https://api.example.com", "api_key": "sk-x", "model": "m1"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "m1" in data["message"]
    assert calls["url"] == "https://api.example.com/v1/chat/completions"
    assert calls["json"]["max_tokens"] == 1  # 最小请求，省钱


def test_settings_test_auth_failure(client, monkeypatch):
    monkeypatch.setattr("requests.post", lambda url, **kw: _FakeResp(401))
    res = client.post(
        "/api/settings/test",
        json={"base_url": "https://api.example.com", "api_key": "bad"},
    )
    data = res.json()
    assert data["ok"] is False
    assert "API Key 无效" in data["message"]


def test_settings_test_no_key(client):
    res = client.post("/api/settings/test", json={"base_url": "https://x.example.com"})
    data = res.json()
    assert data["ok"] is False
    assert "API Key" in data["message"]


def test_settings_test_bad_base_url(client):
    res = client.post(
        "/api/settings/test",
        json={"base_url": "notaurl", "api_key": "sk-x"},
    )
    assert res.status_code == 400
