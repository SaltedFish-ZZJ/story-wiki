"""
Story Wiki - AI 分析模块
调用 DeepSeek API，从文本中提取人物、设定、关系等结构化数据。
"""
import json
import re
import time
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

# ── 重试配置 ──
MAX_RETRIES = 3          # 最大重试次数
RETRY_BASE_DELAY = 2     # 首次重试等待秒数（指数退避）

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
      "related_settings": ["设定名1", "设定名2"],
      "relationships": [
        {"target": "另一人名", "nature": "关系类型"}
      ]
    }
  ],
  "settings": [
    {
      "name": "设定名",
      "type": "地点/组织/体系",
      "description": "描述",
      "related_characters": ["人名1", "人名2"],
      "related_settings": ["另一设定名"]
    }
  ],
  "events": [
    {
      "name": "事件名（简洁概括，4-8字，如'宝黛初见'、'抄检大观园'）",
      "time": "时间（从文本推断，如'某年'、'春天'、null）",
      "participants": ["参与人物名"],
      "location": "发生地点（可选，引用设定名）",
      "description": "一句话描述事件内容",
      "cause": ["导致此事件的前置事件名（可选）"]
    }
  ],
  "summary": "一句话概括文本内容"
}

规则：
1. 只提取文本中明确提到的信息，不要推测
2. 没有信息的字段填 null
3. 关系类型用简洁的词：恋人/父子/母子/师徒/敌对/朋友/主仆/同门/夫妻/兄弟/姐妹/君臣/同事/邻居/其他
4. aliases 如果没有别名就填空数组 []
5. characters、settings、events 如果没有就填空数组 []
6. related_settings：该人物与哪些设定相关（如所属势力、居住地、使用的体系等）
7. related_characters：该设定与哪些人物相关（如创建者、主要使用者、所在地居民等）
8. related_settings（设定之间）：该设定与哪些其他设定相关（如包含关系、对立关系等）
9. events：提取文本中的关键事件（转折点、重要情节、冲突等）
10. events 的 participants 必须引用文本中出现的人物名
11. events 的 location 引用文本中出现的地点/设定名
12. events 的 cause 引用其他事件名（表示因果关系，可选）
13. 整个响应必须是一个合法的 JSON 对象，不能包含任何其他内容"""


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

    # 后处理：校验引用 + 模糊匹配
    result = _postprocess_result(result)

    # 保存原始响应（调试用）
    _save_raw_response(raw_response, "success")

    return result


def _call_deepseek(text: str) -> str:
    """调用 DeepSeek API，返回原始响应文本。"""
    return _call_deepseek_with_prompt(SYSTEM_PROMPT, text)


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


# ── 后处理：引用校验 + 模糊匹配 ──────────────────────────────

def _normalize_name(name: str) -> str:
    """去除括号内容和空格，用于模糊匹配。"""
    return re.sub(r'[（\(][^）\)]*[）\)]', '', name).strip()


def _build_name_map(characters: list) -> dict[str, str]:
    """构建 {别名/标准名: 标准名} 映射表。"""
    name_map = {}
    for c in characters:
        canonical = c.get("name", "")
        if not canonical:
            continue
        name_map[canonical] = canonical
        for alias in (c.get("aliases") or []):
            if alias:
                name_map.setdefault(alias, canonical)
    return name_map


def _resolve_name(name: str, name_map: dict[str, str]) -> str:
    """将名称解析为标准名：精确 → 去括号 → 子串匹配。"""
    if name in name_map:
        return name_map[name]
    norm = _normalize_name(name)
    if norm in name_map:
        return name_map[norm]
    for alias, canonical in name_map.items():
        if norm and (norm in alias or alias in norm):
            return canonical
    return name


def _clean_character_refs(characters: list, setting_names: set, name_map: dict) -> None:
    """清理人物中的无效引用（就地修改）。"""
    for c in characters:
        c["relationships"] = [
            r for r in (c.get("relationships") or [])
            if _resolve_name(r.get("target", ""), name_map) in name_map
        ]
        for r in c.get("relationships", []):
            r["target"] = _resolve_name(r["target"], name_map)
        c["related_settings"] = [
            s for s in (c.get("related_settings") or [])
            if s in setting_names
        ]


def _clean_setting_refs(settings: list, char_names: set, setting_names: set) -> None:
    """清理设定中的无效引用（就地修改）。"""
    for s in settings:
        s["related_characters"] = [
            c for c in (s.get("related_characters") or [])
            if c in char_names
        ]
        s["related_settings"] = [
            st for st in (s.get("related_settings") or [])
            if st in setting_names and st != s.get("name", "")
        ]


def _merge_group(group: list[dict]) -> dict:
    """合并一组模糊匹配的人物，取最长名作为标准名。"""
    best = max(group, key=lambda c: len(c.get("name", "")))

    # 合并别名
    aliases = set(best.get("aliases") or [])
    for c in group:
        aliases.add(c.get("name", ""))
        aliases.update(c.get("aliases") or [])
    aliases.discard(best.get("name", ""))
    best["aliases"] = list(aliases)

    # 合并关系（去重）
    seen = set()
    rels = []
    for c in group:
        for r in (c.get("relationships") or []):
            k = (r.get("target", ""), r.get("nature", ""))
            if k not in seen:
                seen.add(k)
                rels.append(r)
    best["relationships"] = rels

    # 合并关联设定
    all_rs = set()
    for c in group:
        all_rs.update(c.get("related_settings") or [])
    best["related_settings"] = list(all_rs)

    return best


def _is_name_pair(a: str, b: str) -> bool:
    """判断两个 normalized name 是否应该合并（子串匹配）。"""
    return bool(a and b and (a in b or b in a))


def _find_clusters(characters: list) -> list[list[int]]:
    """
    按子串匹配分组人物索引。
    '宝玉' 是 '贾宝玉' 的子串 → 同一组。
    """
    n = len(characters)
    norms = [_normalize_name(c.get("name", "")) for c in characters]
    group_of = list(range(n))

    def find_group(i):
        while group_of[i] != i:
            group_of[i] = group_of[group_of[i]]
            i = group_of[i]
        return i

    def merge_groups(i, j):
        gi, gj = find_group(i), find_group(j)
        if gi != gj:
            group_of[gi] = gj

    _merge_by_substring(norms, n, merge_groups)

    result: dict[int, list[int]] = {}
    for i in range(n):
        result.setdefault(find_group(i), []).append(i)
    return list(result.values())


def _merge_by_substring(norms: list[str], n: int, merge_fn) -> None:
    """对所有名字对执行子串匹配合并。"""
    for i in range(n):
        for j in range(i + 1, n):
            if _is_name_pair(norms[i], norms[j]):
                merge_fn(i, j)


def _merge_similar_characters(characters: list) -> list:
    """合并子串匹配的同名人物（如 '贾宝玉' 和 '宝玉'）。"""
    if len(characters) <= 1:
        return characters

    clusters = _find_clusters(characters)
    merged = []
    for indices in clusters:
        group = [characters[i] for i in indices]
        if len(group) == 1:
            merged.append(group[0])
        else:
            merged.append(_merge_group(group))
    return merged


def _postprocess_result(result: dict) -> dict:
    """校验引用完整性 + 合并模糊匹配的同名人物。"""
    characters = result.get("characters", [])
    settings = result.get("settings", [])

    name_map = _build_name_map(characters)
    setting_names = {s.get("name", "") for s in settings}

    _clean_character_refs(characters, setting_names, name_map)
    _clean_setting_refs(settings, {c.get("name", "") for c in characters}, setting_names)
    result["characters"] = _merge_similar_characters(characters)

    return result


def _save_raw_response(raw: str, tag: str):
    """保存原始 API 响应到 state 目录，用于调试。"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = STATE_DIR / f"response_{tag}_{timestamp}.txt"
    filepath.write_text(raw, encoding="utf-8")


# ── 分章分析 ──────────────────────────────────────────────────

CHAPTER_SYSTEM_PROMPT = """你是一个专业的文学分析助手。你正在逐章分析一部作品。

当前已知信息如下（可能为空）：
{context}

你的任务是分析用户提供的章节文本，返回 JSON。规则：
1. 提取本章中**新出现**的人物和设定（已知的不要重复提取）
2. 提取本章中**新出现**的人物关系（包括已知人物之间的新关系）
3. 提取人物与设定之间的关联（如某人属于某势力、住在某地、使用某体系）
4. 如果已知人物在本章有新的信息（身份补充、性格展现等），也请补充
5. 严格以 JSON 格式返回，不要添加任何 markdown 包裹或额外文字

JSON 结构：
{{
  "characters": [
    {{
      "name": "人名",
      "aliases": ["别名1", "别名2"],
      "identity": "身份描述",
      "personality": "性格特征",
      "gender": "男/女/未知",
      "faction": "所属势力/群体",
      "related_settings": ["设定名1", "设定名2"],
      "relationships": [
        {{"target": "另一人名", "nature": "关系类型"}}
      ]
    }}
  ],
  "settings": [
    {{
      "name": "设定名",
      "type": "地点/组织/体系",
      "description": "描述",
      "related_characters": ["人名1", "人名2"],
      "related_settings": ["另一设定名"]
    }}
  ],
  "events": [
    {{
      "name": "事件名（4-8字概括，如'宝黛初见'）",
      "time": "时间（从文本推断，null 表示未知）",
      "participants": ["参与人物名"],
      "location": "发生地点（可选）",
      "description": "一句话描述",
      "cause": ["前置事件名（可选）"],
      "chapter": "{chapter_title}"
    }}
  ],
  "chapter_summary": "本章内容简述（一句话）"
}}

规则：
1. 只提取文本中明确提到的信息，不要推测
2. 没有信息的字段填 null
3. 关系类型用简洁的词：恋人/父子/母子/师徒/敌对/朋友/主仆/同门/夫妻/兄弟/姐妹/君臣/同事/邻居/其他
4. aliases 如果没有别名就填空数组 []
5. characters、settings、events 如果没有就填空数组 []
6. related_settings（人物）：该人物与哪些设定相关
7. related_characters（设定）：该设定与哪些人物相关
8. related_settings（设定之间）：该设定与哪些其他设定相关
9. events：提取本章中的关键事件（转折点、重要情节、冲突等）
10. events 的 participants 必须引用已知人物名
11. events 的 cause 引用已知事件名（表示因果关系）
12. 整个响应必须是一个合法的 JSON 对象"""


# ── 上下文构建（分层压缩策略）──────────────────────────────────

_MAIN_CHAR_LIMIT = 15
_MAIN_SETTING_LIMIT = 15


def _char_summary(c: dict) -> str:
    """构建单个人物的一行摘要：名字（身份），势力。"""
    name = c.get("name", "?")
    identity = c.get("identity") or ""
    faction = c.get("faction") or ""
    parts = [name]
    if identity:
        parts[0] += f"（{identity}）"
    if faction:
        parts.append(faction)
    return "，".join(parts)


def _rank_characters(characters: list) -> tuple[list, list]:
    """按关系数量排序，返回 (主要人物, 次要人物)。"""
    ranked = sorted(characters, key=lambda c: len(c.get("relationships") or []), reverse=True)
    return ranked[:_MAIN_CHAR_LIMIT], ranked[_MAIN_CHAR_LIMIT:]


def _group_by_faction(chars: list) -> dict[str, list[str]]:
    """按势力分组，返回 {势力名: [人名]}。"""
    groups = {}
    for c in chars:
        faction = c.get("faction") or "其他"
        groups.setdefault(faction, []).append(c.get("name", "?"))
    return groups


def _format_faction_groups(groups: dict[str, list[str]]) -> str:
    """格式化势力分组为字符串。"""
    parts = []
    for faction, names in groups.items():
        label = faction if faction != "其他" else "其他"
        parts.append(f"{label}：{'、'.join(names)}")
    return "；".join(parts)


def _dedupe_relationships(characters: list) -> list[str]:
    """提取并去重所有人物关系，返回 ['A—关系—B', ...] 格式。"""
    seen = set()
    result = []
    for c in characters:
        name = c.get("name", "?")
        for r in (c.get("relationships") or []):
            target = r.get("target", "?")
            nature = r.get("nature", "?")
            key = tuple(sorted([name, target]))
            if key not in seen:
                seen.add(key)
                result.append(f"{name}—{nature}—{target}")
    return result[:30]


def _setting_summary(s: dict) -> str:
    """构建单个设定的一行摘要：名字（类型）。"""
    name = s.get("name", "?")
    stype = s.get("type") or ""
    return f"{name}（{stype}）" if stype else name


def _build_chapter_context(known_characters: list, known_settings: list,
                           known_events: list = None) -> str:
    """
    构建分章分析的上下文摘要（分层压缩策略）。
    主要人物/设定保留完整描述，次要的只给名字，关系网络始终完整。
    """
    if not known_characters and not known_settings and not known_events:
        return "（暂无已知信息，这是第一个章节）"

    parts = []

    if known_characters:
        main, minor = _rank_characters(known_characters)
        if main:
            parts.append(f"已知人物（主要）：{'、'.join(_char_summary(c) for c in main)}")
        if minor:
            parts.append(f"次要人物：{_format_faction_groups(_group_by_faction(minor))}")
        rels = _dedupe_relationships(known_characters)
        if rels:
            parts.append(f"人物关系：{'；'.join(rels)}")

    if known_settings:
        main_s = known_settings[:_MAIN_SETTING_LIMIT]
        minor_s = known_settings[_MAIN_SETTING_LIMIT:]
        if main_s:
            parts.append(f"已知设定：{'、'.join(_setting_summary(s) for s in main_s)}")
        if minor_s:
            parts.append(f"其他设定：{'、'.join(s.get('name', '?') for s in minor_s)}")

    if known_events:
        event_names = [e.get("name", "?") for e in known_events[:20]]
        parts.append(f"已知事件：{'、'.join(event_names)}")

    return "\n".join(parts)


def analyze_chapter(text: str, known_characters: list = None, known_settings: list = None,
                     known_events: list = None, chapter_title: str = None) -> dict:
    """
    分析单个章节，携带已知人物/设定/事件上下文。

    Args:
        text: 章节文本
        known_characters: 已知人物列表（之前章节提取的）
        known_settings: 已知设定列表
        known_events: 已知事件列表（之前章节提取的）
        chapter_title: 当前章节标题（填入 events.chapter 字段）

    Returns:
        本章的分析结果 dict（characters, settings, events, chapter_summary）
    """
    context_text = _build_chapter_context(known_characters, known_settings, known_events)

    # 构建 prompt
    system_prompt = CHAPTER_SYSTEM_PROMPT.format(
        context=context_text,
        chapter_title=chapter_title or "未知章节",
    )

    # 调用 API
    raw_response = _call_deepseek_with_prompt(system_prompt, text)

    # 解析
    try:
        result = _parse_response(raw_response)
    except (ValueError, json.JSONDecodeError) as e:
        _save_raw_response(raw_response, "chapter_error")
        raise ValueError(f"章节分析返回无法解析: {e}")

    _save_raw_response(raw_response, "chapter_success")
    return result


def _call_deepseek_with_prompt(system_prompt: str, text: str) -> str:
    """
    用自定义 system prompt 调用 DeepSeek API，带指数退避重试。
    仅对网络错误和限流（429/5xx）重试，4xx 客户端错误直接失败。
    """
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
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请分析以下章节文本：\n\n{text}"},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)

            # 限流或服务端错误 → 重试
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    print(f"  ⚠️ API 返回 {response.status_code}，{delay}s 后重试...")
                    time.sleep(delay)
                    continue
                response.raise_for_status()

            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        except requests.ConnectionError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                print(f"  ⚠️ 网络连接失败，{delay}s 后重试...")
                time.sleep(delay)
                continue
            raise RuntimeError("无法连接到 API，请检查网络或 VPN")

    # 所有重试用尽
    raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {last_error}")
