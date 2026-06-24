"""
Story Wiki - AI 分析模块
调用 DeepSeek API，从文本中提取人物、设定、关系等结构化数据。

优化：添加请求体大小检查，改进长文本处理。
"""
import json
import time
import sys
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
    REQUEST_SIZE_WARNING,
    REQUEST_SIZE_LIMIT,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
)
from src.utils import parse_ai_response as _parse_response, normalize_name as _normalize_name


def _get_memory_usage() -> dict:
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
        # psutil 未安装，返回估算值
        return {"rss_mb": 0, "vms_mb": 0}


def _check_request_size(payload: dict) -> tuple[bool, str]:
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
    except Exception as e:
        return True, f"无法检查请求体大小: {e}"

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
      "role_tags": ["主角", "女主"],
      "status": "活跃",
      "quotes": ["经典语录1", "经典语录2"],
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
      "time": "时间（必须从文本推断，如'某年'、'春天'、'第X回'，不要填 null）",
      "participants": ["参与人物名"],
      "location": "发生地点（引用设定名）",
      "description": "一句话描述事件内容（必须填写，概括事件的核心内容和结果）",
      "cause": ["导致此事件的前置事件名（可选）"],
      "effect": ["该事件导致的后果或影响（可选）"],
      "importance": "重要性：高/中/低（从文本推断，关键转折点=高，普通情节=中，细节=低）"
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
13. role_tags：角色定位标签，从以下词汇中选择：主角/女主/男主/反派/配角/导师/伙伴/路人/BOSS/隐藏角色
14. status：角色当前状态，填"活跃/已故/失踪/退场/未知"之一，从文本推断
15. quotes：该人物的经典语录或代表性台词，提取 2-3 句，没有则填空数组 []
16. 整个响应必须是一个合法的 JSON 对象，不能包含任何其他内容"""


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


# ── 后处理：引用校验 + 模糊匹配 ──────────────────────────────

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
    """
    判断两个 normalized name 是否应该合并（子串匹配）。
    
    优化：
    1. 添加最小长度限制（≥2字符），避免单字符误匹配
    2. 保留合理的子串匹配（如"宝玉"匹配"贾宝玉"）
    3. 添加长度差异限制，避免过度合并
    """
    if not a or not b:
        return False
    
    # 最小长度限制：至少2个字符
    MIN_NAME_LENGTH = 2
    if len(a) < MIN_NAME_LENGTH or len(b) < MIN_NAME_LENGTH:
        return False
    
    # 长度差异限制：避免过度合并（如"林"合并"林黛玉"）
    # 如果一个名字是另一个名字的子串，长度差异不能超过60%
    if a in b or b in a:
        shorter = min(len(a), len(b))
        longer = max(len(a), len(b))
        # 长度差异超过60%则不合并
        if shorter / longer < 0.4:
            return False
        return True
    
    return False


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
      "role_tags": ["主角"],
      "status": "活跃",
      "quotes": ["语录1"],
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
      "time": "时间（必须从文本推断，如'第X回'、'春天'，不要填 null）",
      "participants": ["参与人物名"],
      "location": "发生地点（引用设定名）",
      "description": "一句话描述事件核心内容（必须填写）",
      "cause": ["前置事件名（可选）"],
      "effect": ["该事件导致的后果（可选）"],
      "importance": "重要性：高/中/低",
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
12. role_tags：角色定位标签，从以下词汇中选择：主角/女主/男主/反派/配角/导师/伙伴/路人/BOSS/隐藏角色
13. status：角色当前状态，填"活跃/已故/失踪/退场/未知"之一
14. quotes：本章中该人物的经典语录或代表性台词，没有则填空数组 []
15. 整个响应必须是一个合法的 JSON 对象"""


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
    """
    多因素排序，返回 (主要人物, 次要人物)。
    
    优化：
    1. 多因素排序：角色标签权重 + 关系数量 + 状态 + 重要性
    2. 动态调整主要人物数量：
       - 人物总数 ≤ 20：全部作为主要人物
       - 人物总数 > 20：取前 20 个主要人物
    """
    if not characters:
        return [], []
    
    def character_importance(c):
        """计算人物重要性分数。"""
        # 角色标签权重
        role_tags = c.get("role_tags") or []
        tag_weight = 0
        if "主角" in role_tags:
            tag_weight = 100
        elif "女主" in role_tags or "男主" in role_tags:
            tag_weight = 90
        elif "反派" in role_tags:
            tag_weight = 80
        elif "配角" in role_tags:
            tag_weight = 70
        elif "导师" in role_tags or "伙伴" in role_tags:
            tag_weight = 60
        else:
            tag_weight = 50
        
        # 关系数量权重（每条关系+1分，上限30分）
        rel_count = len(c.get("relationships") or [])
        rel_weight = min(rel_count, 30)
        
        # 状态权重
        status = c.get("status", "活跃")
        status_weight = 0
        if status == "活跃":
            status_weight = 10
        elif status == "失踪":
            status_weight = 5
        elif status == "已故":
            status_weight = 3
        else:
            status_weight = 1
        
        # 总分 = 角色标签权重 * 10 + 关系权重 + 状态权重
        total_score = tag_weight * 10 + rel_weight + status_weight
        return total_score
    
    # 按重要性分数排序
    ranked = sorted(characters, key=character_importance, reverse=True)
    
    # 动态调整主要人物数量
    total_chars = len(characters)
    if total_chars <= 20:
        # 人物总数 ≤ 20：全部作为主要人物
        return ranked, []
    else:
        # 人物总数 > 20：取前 20 个主要人物
        return ranked[:20], ranked[20:]


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
    """
    提取并去重所有人物关系，返回 ['A—关系—B', ...] 格式。
    
    优化：
    1. 按关系重要性排序，保留最重要的 30 条关系
    2. 优先保留主角相关的关系
    3. 关系类型权重：恋人(10) > 父子/母子(9) > 师徒(8) > 敌对(7) > 朋友(6) > 其他(5)
    """
    # 构建人物重要性映射
    char_importance = {}
    for c in characters:
        name = c.get("name", "?")
        role_tags = c.get("role_tags") or []
        importance = 0
        if "主角" in role_tags:
            importance = 100
        elif "女主" in role_tags or "男主" in role_tags:
            importance = 90
        elif "反派" in role_tags:
            importance = 80
        elif "配角" in role_tags:
            importance = 70
        else:
            importance = 50
        char_importance[name] = importance
    
    # 关系类型权重
    relationship_weights = {
        "恋人": 10,
        "夫妻": 10,
        "父子": 9,
        "母子": 9,
        "父女": 9,
        "母女": 9,
        "师徒": 8,
        "敌对": 7,
        "朋友": 6,
        "主仆": 5,
        "同门": 5,
        "兄弟": 5,
        "姐妹": 5,
        "君臣": 4,
        "同事": 3,
        "邻居": 2,
        "其他": 1
    }
    
    seen = set()
    relationships_with_importance = []
    
    for c in characters:
        name = c.get("name", "?")
        for r in (c.get("relationships") or []):
            target = r.get("target", "?")
            nature = r.get("nature", "?")
            key = tuple(sorted([name, target]))
            if key not in seen:
                seen.add(key)
                # 计算关系重要性
                nature_weight = relationship_weights.get(nature, 1)
                # 关系重要性 = 源人物重要性 + 目标人物重要性 + 关系类型权重
                source_importance = char_importance.get(name, 50)
                target_importance = char_importance.get(target, 50)
                total_importance = source_importance + target_importance + nature_weight
                relationships_with_importance.append((f"{name}—{nature}—{target}", total_importance))
    
    # 按重要性排序
    relationships_with_importance.sort(key=lambda x: x[1], reverse=True)
    
    # 提取前30条最重要的关系
    return [rel[0] for rel in relationships_with_importance[:30]]


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
                     known_events: list = None, chapter_title: str = None,
                     context_before_summary: str = None) -> dict:
    """
    分析单个章节，携带已知人物/设定/事件上下文。

    优化（DeepSeek 建议）：
    1. 添加 context_before_summary 参数，传递前文摘要
    2. 提升跨块实体链接的准确性

    Args:
        text: 章节文本
        known_characters: 已知人物列表（之前章节提取的）
        known_settings: 已知设定列表
        known_events: 已知事件列表（之前章节提取的）
        chapter_title: 当前章节标题（填入 events.chapter 字段）
        context_before_summary: 前文摘要（用于跨块实体链接）

    Returns:
        本章的分析结果 dict（characters, settings, events, chapter_summary）
    """
    context_text = _build_chapter_context(known_characters, known_settings, known_events)

    # 添加前文摘要（DeepSeek 建议）
    if context_before_summary:
        context_text = f"{context_text}\n\n前情摘要：{context_before_summary}"

    # 构建 prompt（用 replace 而非 format，避免 context 中的花括号导致 KeyError）
    system_prompt = CHAPTER_SYSTEM_PROMPT.replace(
        "{context}", context_text
    ).replace(
        "{chapter_title}", chapter_title or "未知章节"
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


def generate_context_summary(analysis_result: dict, max_length: int = 200) -> str:
    """
    从前一个块的分析结果生成前文摘要（DeepSeek 建议）。

    用于 context_before_summary，帮助跨块实体链接。

    优化：
    1. 人物按重要性排序（角色标签、关系数量、状态）
    2. 包含身份描述，而不仅仅是名字
    3. 设定和事件也按重要性排序

    Args:
        analysis_result: 前一个块的分析结果
        max_length: 摘要最大长度

    Returns:
        前文摘要字符串
    """
    parts = []

    # 提取人物摘要（按重要性排序）
    characters = analysis_result.get("characters", [])
    if characters:
        # 按重要性排序：主角 > 女主 > 男主 > 反派 > 配角，然后按关系数量
        def char_importance(c):
            role_tags = c.get("role_tags") or []
            rel_count = len(c.get("relationships") or [])
            status = c.get("status", "活跃")
            # 角色标签权重
            tag_weight = 0
            if "主角" in role_tags:
                tag_weight = 100
            elif "女主" in role_tags or "男主" in role_tags:
                tag_weight = 90
            elif "反派" in role_tags:
                tag_weight = 80
            elif "配角" in role_tags:
                tag_weight = 70
            elif "导师" in role_tags or "伙伴" in role_tags:
                tag_weight = 60
            else:
                tag_weight = 50
            # 状态权重：活跃 > 失踪 > 已故 > 退场
            status_weight = 0
            if status == "活跃":
                status_weight = 10
            elif status == "失踪":
                status_weight = 5
            elif status == "已故":
                status_weight = 3
            else:
                status_weight = 1
            return (tag_weight, rel_count, status_weight)

        sorted_chars = sorted(characters, key=char_importance, reverse=True)
        # 取前5个主要人物，使用_char_summary生成带身份的摘要
        main_chars = sorted_chars[:5]
        char_summaries = [_char_summary(c) for c in main_chars]
        parts.append(f"已出现人物：{'、'.join(filter(None, char_summaries))}")

    # 提取设定摘要（按相关性排序）
    settings = analysis_result.get("settings", [])
    if settings:
        # 按相关人物数量排序
        def setting_importance(s):
            rel_chars = len(s.get("related_characters") or [])
            rel_settings = len(s.get("related_settings") or [])
            return rel_chars + rel_settings

        sorted_settings = sorted(settings, key=setting_importance, reverse=True)
        # 取前3个设定
        setting_summaries = [_setting_summary(s) for s in sorted_settings[:3]]
        parts.append(f"已出现设定：{'、'.join(filter(None, setting_summaries))}")

    # 提取事件摘要（按重要性排序）
    events = analysis_result.get("events", [])
    if events:
        # 按重要性排序：高 > 中 > 低
        def event_importance(e):
            importance = e.get("importance", "中")
            if importance == "高":
                return 3
            elif importance == "中":
                return 2
            else:
                return 1

        sorted_events = sorted(events, key=event_importance, reverse=True)
        # 取前3个事件
        event_summaries = []
        for e in sorted_events[:3]:
            name = e.get("name", "")
            if name:
                event_summaries.append(name)
        parts.append(f"已发生事件：{'、'.join(filter(None, event_summaries))}")

    # 提取章节摘要
    chapter_summary = analysis_result.get("chapter_summary", "")
    if chapter_summary:
        parts.append(f"本章概要：{chapter_summary}")

    # 合并并截断
    summary = "；".join(parts)
    if len(summary) > max_length:
        summary = summary[:max_length - 3] + "..."

    return summary


def _call_deepseek_with_prompt(system_prompt: str, text: str) -> str:
    """
    用自定义 system prompt 调用 DeepSeek API，带指数退避重试。
    仅对网络错误和限流（429/5xx）重试，4xx 客户端错误直接失败。

    优化：
    1. 添加请求体大小检查
    2. 添加内存使用监控
    3. 改进错误处理
    """
    if not DEEPSEEK_API_KEY:
        raise ValueError(
            "未配置 API Key！请设置环境变量 STORY_WIKI_API_KEY 或在 .env 文件中配置"
        )

    # 检查文本长度
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        print(f"[优化] 文本过长，已截取前 {MAX_TEXT_LENGTH} 字进行分析")

    # 构建请求
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

    # 检查请求体大小
    is_ok, size_message = _check_request_size(payload)
    if not is_ok:
        raise ValueError(size_message)
    if size_message:
        print(f"  {size_message}")

    # 显示内存使用情况
    memory = _get_memory_usage()
    if memory["rss_mb"] > 0:
        print(f"  [内存] 当前使用: {memory['rss_mb']:.1f}MB")

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            # 发送请求
            print(f"  [API] 发送请求... (尝试 {attempt + 1}/{MAX_RETRIES})")
            response = requests.post(url, headers=headers, json=payload, timeout=180)

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

            # 检查响应格式
            if "choices" not in data or not data["choices"]:
                raise ValueError("API 返回格式错误：缺少 choices 字段")

            content = data["choices"][0]["message"]["content"].strip()
            print(f"  [API] 响应成功，长度: {len(content)} 字")

            return content

        except requests.ConnectionError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                print(f"  ⚠️ 网络连接失败，{delay}s 后重试...")
                time.sleep(delay)
                continue
            raise RuntimeError("无法连接到 API，请检查网络或 VPN")

        except requests.Timeout as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                print(f"  ⚠️ 请求超时，{delay}s 后重试...")
                time.sleep(delay)
                continue
            raise RuntimeError("API 请求超时，请稍后重试")

    # 所有重试用尽
    raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {last_error}")
