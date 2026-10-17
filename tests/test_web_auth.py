"""
Story Wiki - 最小鉴权测试（P2）
覆盖：未设密码=开放、密码校验、session cookie 签发/过期/篡改、
登录页流转、POST 接口 401 保护。
"""
import time

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import web.app as webapp  # noqa: E402
from web import auth  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, "INPUT_DIR", tmp_path / "input")
    monkeypatch.setattr(webapp, "OUTPUT_DIR", tmp_path / "output")
    return TestClient(webapp.app)


@pytest.fixture()
def auth_on(monkeypatch):
    """开启鉴权并保证密钥派生缓存一致。"""
    monkeypatch.setenv("STORY_WIKI_PASSWORD", "test-pass-123")
    monkeypatch.delenv("STORY_WIKI_SECRET", raising=False)
    yield


# ── auth 模块单元 ────────────────────────────────────────────


class TestAuthUnit:
    def test_disabled_without_password(self, monkeypatch):
        monkeypatch.delenv("STORY_WIKI_PASSWORD", raising=False)
        assert auth.auth_enabled() is False

    def test_enabled_with_password(self, auth_on):
        assert auth.auth_enabled() is True

    def test_verify_password(self, auth_on):
        assert auth.verify_password("test-pass-123")
        assert not auth.verify_password("wrong")
        assert not auth.verify_password("")

    def test_session_roundtrip(self, auth_on):
        cookie = auth.make_session_cookie()
        assert auth.verify_session_cookie(cookie)

    def test_session_rejects_tampered(self, auth_on):
        cookie = auth.make_session_cookie()
        expires, _, sig = cookie.rpartition(".")
        assert not auth.verify_session_cookie(f"{expires}.deadbeef")
        assert not auth.verify_session_cookie("garbage")
        assert not auth.verify_session_cookie(None)

    def test_session_expires(self, auth_on, monkeypatch):
        expires_at = int(time.time()) - 10  # 已过期
        cookie = f"{expires_at}.{auth._sign(expires_at)}"
        assert not auth.verify_session_cookie(cookie)


# ── HTTP 层 ──────────────────────────────────────────────────


class TestAuthHttp:
    def test_open_when_no_password(self, client, monkeypatch):
        """未设密码：POST 直接放行。"""
        monkeypatch.delenv("STORY_WIKI_PASSWORD", raising=False)
        resp = client.post("/api/analyze", json={})
        assert resp.status_code == 400  # 业务校验错误，而非 401

    def test_post_requires_login(self, client, auth_on):
        resp = client.post("/api/analyze", json={"filename": "x.txt"})
        assert resp.status_code == 401

    def test_get_stays_public(self, client, auth_on):
        """GET 概览类接口继续公开。"""
        assert client.get("/api/books").status_code == 200
        assert client.get("/api/search", params={"q": "x"}).status_code == 200

    def test_login_flow(self, client, auth_on):
        # 登录页可访问
        page = client.get("/login")
        assert page.status_code == 200
        assert "密码" in page.text

        # 错误密码 → 401
        bad = client.post("/login", data={"password": "wrong"})
        assert bad.status_code == 401

        # 正确密码 → 303 跳首页 + 种 cookie
        good = client.post("/login", data={"password": "test-pass-123"},
                           follow_redirects=False)
        assert good.status_code == 303
        assert "sw_session" in good.cookies

        # 带 cookie 的 POST 放行
        ok = client.post("/api/analyze", json={})
        assert ok.status_code == 400  # 过了鉴权，进入业务校验

    def test_login_redirect_when_disabled(self, client, monkeypatch):
        monkeypatch.delenv("STORY_WIKI_PASSWORD", raising=False)
        resp = client.get("/login", follow_redirects=False)
        assert resp.status_code == 307  # RedirectResponse 默认 307
        assert resp.headers["location"] == "/"

    def test_logout_clears_session(self, client, auth_on):
        client.post("/login", data={"password": "test-pass-123"})
        out = client.post("/logout", follow_redirects=False)
        assert out.status_code == 303
        # cookie 被清除后（客户端不再携带有效会话）→ 401
        client.cookies.clear()
        assert client.post("/api/analyze", json={}).status_code == 401
