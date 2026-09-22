"""
Story Wiki - API 调用客户端
统一管理与 AI API 的通信：请求构建、重试、大小检查、内存监控。
所有需要调用 AI API 的模块应使用此模块，而非自行实现。
"""
import json
import time

import requests

from src.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    MAX_TEXT_LENGTH,
    MAX_TOKENS,
    TEMPERATURE,
    REQUEST_SIZE_WARNING,
    REQUEST_SIZE_LIMIT,
    MAX_RETRIES,
    API_TIMEOUT,
    RETRY_BASE_DELAY,
)
from src.logging_setup import get_logger

logger = get_logger("api_client")


def get_memory_usage() -> dict:
    """获取当前内存使用情况。"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
        }
    except ImportError:
        return {"rss_mb": 0, "vms_mb": 0}


def check_request_size(payload: dict) -> tuple[bool, str]:
    """
    检查请求体大小。

    Returns:
        (is_ok, message): 是否正常，以及提示信息
    """
    try:
        payload_json = json.dumps(payload, ensure_ascii=False)
        size_bytes = len(payload_json.encode('utf-8'))
        size_mb = size_bytes / 1024 / 1024

        if size_bytes > REQUEST_SIZE_LIMIT:
            return False, f"请求体过大 ({size_mb:.1f}MB)，超过限制 ({REQUEST_SIZE_LIMIT // 1024 // 1024}MB)"
        elif size_bytes > REQUEST_SIZE_WARNING:
            return True, f"⚠️ 请求体较大 ({size_mb:.1f}MB)，可能影响性能"
        else:
            return True, ""
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        return True, f"无法检查请求体大小: {e}"


def call_api(system_prompt: str, text: str, *, api_key: str = None, base_url: str = None, model: str = None) -> str:
    """
    调用 AI API，带指数退避重试。
    仅对网络错误和限流（429/5xx）重试，4xx 客户端错误直接失败。

    Args:
        system_prompt: 系统提示词
        text: 用户输入文本
        api_key: 覆盖默认 API Key（可选）
        base_url: 覆盖默认 Base URL（可选）
        model: 覆盖默认模型名（可选）

    Returns:
        API 返回的文本内容

    Raises:
        ValueError: API Key 未配置、请求体过大
        RuntimeError: 网络连接失败、请求超时、重试耗尽
    """
    effective_key = api_key or DEEPSEEK_API_KEY
    effective_url = base_url or DEEPSEEK_BASE_URL
    effective_model = model or DEEPSEEK_MODEL

    if not effective_key:
        raise ValueError(
            "未配置 API Key！请设置环境变量 STORY_WIKI_API_KEY 或在 .env 文件中配置"
        )

    # 检查文本长度
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        logger.warning(f"文本过长，已截取前 {MAX_TEXT_LENGTH} 字进行分析")

    # 构建请求
    url = f"{effective_url.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {effective_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": effective_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请分析以下章节文本：\n\n{text}"},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }

    # 检查请求体大小
    is_ok, size_message = check_request_size(payload)
    if not is_ok:
        raise ValueError(size_message)
    if size_message:
        logger.warning(size_message)

    # 显示内存使用情况
    memory = get_memory_usage()
    if memory["rss_mb"] > 0:
        logger.info(f"内存当前使用: {memory['rss_mb']:.1f}MB")

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"发送请求... (尝试 {attempt + 1}/{MAX_RETRIES})")
            response = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)

            # 限流或服务端错误 → 重试
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"API 返回 {response.status_code}，{delay}s 后重试...")
                    time.sleep(delay)
                    continue
                response.raise_for_status()

            response.raise_for_status()
            data = response.json()

            if "choices" not in data or not data["choices"]:
                raise ValueError("API 返回格式错误：缺少 choices 字段")

            content = data["choices"][0]["message"]["content"].strip()
            logger.info(f"响应成功，长度: {len(content)} 字")

            return content

        except requests.ConnectionError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"网络连接失败，{delay}s 后重试...")
                time.sleep(delay)
                continue
            raise RuntimeError("无法连接到 API，请检查网络或 VPN")

        except requests.Timeout as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"请求超时，{delay}s 后重试...")
                time.sleep(delay)
                continue
            raise RuntimeError("API 请求超时，请稍后重试")

    raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {last_error}")


# ── 向后兼容别名 ──
_call_deepseek_with_prompt = call_api
