"""
Story Wiki - AI 分析模块
调用 DeepSeek API，从文本中提取人物、设定、关系等结构化数据。
"""
import json
import re
from datetime import datetime
from pathlib import Path

import requests

from src.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    MAX_TEXT_LENGTH,
    MAX_TOKENS,
    STATE_DIR,
    TEMPERATURE,
)

# ── System Prompt ──────────────────────────────────────────
SYSTEM_PROMPT = """你是一个专业的文学分析助手。请从给定文本中提取以下信息，严格以 JSON 格式返回，不要添加任何 markdown 包裹、代码块标记或额外文字。

JSON 结构：
{
  "title": "作品名（从文本推断，如果推断不出则填 null）",
  "characters": [
    {
      "name": "人名",
      "aliases": ["别名1", "别名2"],
      "identity": "身份描述",
      "personality": "性格特征",
      "gender": "男/女/未知",
      "faction": "所属势力/群体",
      "relationships": [
        {"target": "另一人名", "nature": "关系类型"}
      ]
    }
  ],
  "settings": [
    {
      "name": "设定名",
      "type": "地点/组织/体系",
      "description": "描述"
    }
  ],
  "summary": "一句话概括文本内容"
}

规则：
1. 只提取文本中明确提到的信息，不要推测
2. 没有信息的字段填 null
3. 关系类型用简洁的词：恋人/父子/母子/师徒/敌对/朋友/主仆/同门/夫妻/兄弟/姐妹/君臣/同事/邻居/其他
4. aliases 如果没有别名就填空数组 []
5. characters 和 settings 如果没有就填空数组 []
6. 整个响应必须是一个合法的 JSON 对象，不能包含任何其他内容"""


def analyze_text(text: str, title: str = None) -> dict:
    """
    分析文本，提取人物、设定、关系。

    Args:
        text: 纯文本内容
        title: 可选的作品名（覆盖 AI 推断）

    Returns:
        结构化分析结果 dict
    """
    # 截取过长文本
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        print(f"[提示] 文本过长，已截取前 {MAX_TEXT_LENGTH} 字进行分析")

    # 调用 API
    raw_response = _call_deepseek(text)

    # 解析 JSON
    try:
        result = _parse_response(raw_response)
    except (ValueError, json.JSONDecodeError) as e:
        # 解析失败，保存原始响应用于调试
        _save_raw_response(raw_response, "parse_error")
        raise ValueError(f"AI 返回内容无法解析为 JSON: {e}\n原始响应已保存到 data/state/")

    # 覆盖标题
    if title:
        result["title"] = title

    # 保存原始响应（调试用）
    _save_raw_response(raw_response, "success")

    return result


def _call_deepseek(text: str) -> str:
    """调用 DeepSeek API，返回原始响应文本。"""
    if not DEEPSEEK_API_KEY:
        raise ValueError(
            "未配置 API Key！请设置环境变量 STORY_WIKI_API_KEY 或在 .env 文件中配置"
        )

    url = f"{DEEPSEEK_BASE_URL.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请分析以下文本：\n\n{text}"},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.HTTPError as e:
        raise RuntimeError(f"API 请求失败: HTTP {e.response.status_code} - {e.response.text[:200]}")
    except requests.ConnectionError:
        raise RuntimeError("无法连接到 DeepSeek API，请检查网络或 VPN")
    except Exception as e:
        raise RuntimeError(f"API 调用异常: {e}")


def _parse_response(raw: str) -> dict:
    """
    解析 AI 返回的 JSON，带多种容错策略。
    """
    # 策略 1：直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 策略 2：提取 ```json ... ``` 中的内容
    match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 策略 3：提取第一个 { ... } 块
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError("所有解析策略均失败")


def _save_raw_response(raw: str, tag: str):
    """保存原始 API 响应到 state 目录，用于调试。"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = STATE_DIR / f"response_{tag}_{timestamp}.txt"
    filepath.write_text(raw, encoding="utf-8")
