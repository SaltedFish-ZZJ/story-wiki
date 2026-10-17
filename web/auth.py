"""
Story Wiki - 最小权限鉴权（P2）
单用户密码登录 + HMAC 签名 session cookie，只用标准库 hashlib/hmac/secrets。

设计原则（最小可用）：
- 密码来自环境变量 STORY_WIKI_PASSWORD；未设置时鉴权关闭（本机单用户场景）
- session cookie 携带过期时间戳 + HMAC-SHA256 签名，服务端无状态校验
- 签名密钥优先取 STORY_WIKI_SECRET，未设置时从密码派生
- 只保护写操作（POST），概览类 GET 继续公开
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

from fastapi import HTTPException, Request, Response

COOKIE_NAME = "sw_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 天


def _get_password() -> str:
    return os.environ.get("STORY_WIKI_PASSWORD", "").strip()


def _get_secret() -> bytes:
    secret = os.environ.get("STORY_WIKI_SECRET", "").strip()
    if secret:
        return secret.encode("utf-8")
    # 从密码派生固定密钥（同密码同密钥，重启后会话仍有效）
    return hashlib.sha256(
        ("story-wiki:" + _get_password()).encode("utf-8")
    ).digest()


def auth_enabled() -> bool:
    """设置了 STORY_WIKI_PASSWORD 才启用鉴权。"""
    return bool(_get_password())


def verify_password(input_password: str) -> bool:
    """恒定时间比较密码。"""
    return hmac.compare_digest(
        (input_password or "").encode("utf-8"), _get_password().encode("utf-8")
    )


def _sign(expires_at: int) -> str:
    return hmac.new(_get_secret(), str(expires_at).encode(), hashlib.sha256).hexdigest()


def make_session_cookie() -> str:
    """生成 '过期时间戳.签名' 形式的 cookie 值。"""
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    return f"{expires_at}.{_sign(expires_at)}"


def verify_session_cookie(value: str | None) -> bool:
    """校验 cookie：签名正确且未过期。"""
    if not value or "." not in value:
        return False
    expires_part, _, sig = value.rpartition(".")
    if not expires_part.isdigit():
        return False
    expires_at = int(expires_part)
    if expires_at < int(time.time()):
        return False
    return hmac.compare_digest(sig, _sign(expires_at))


def set_session(response: Response) -> None:
    response.set_cookie(
        COOKIE_NAME,
        make_session_cookie(),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


def require_auth(request: Request) -> None:
    """FastAPI 依赖：鉴权开启时校验 session cookie，失败返回 401。"""
    if not auth_enabled():
        return
    if verify_session_cookie(request.cookies.get(COOKIE_NAME)):
        return
    raise HTTPException(401, "未登录或会话已过期")
