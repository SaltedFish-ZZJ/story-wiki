"""
Story Wiki - 合并模块
负责人物/设定/事件的模糊匹配与合并逻辑。

从 pipeline.py 中抽取，便于独立测试和复用。
"""
import re

from src.name_matcher import (
    find_matching_canonical as _find_matching_canonical,
    merge_by_name,
)


# ── 内部匹配器 ──────────────────────────────────────────────

def _find_matching_character(name: str, result_map: dict) -> str | None:
    """在 result_map 中查找与 name 匹配的人物标准名。"""
    return _find_matching_canonical(
        name,
        result_map,
        check_aliases_of=lambda c: c.get("aliases") or [],
    )


def _find_matching_setting(name: str, result_map: dict) -> str | None:
    """在 result_map 中查找与 name 匹配的设定标准名。"""
    return _find_matching_canonical(name, result_map)


def _find_matching_event(name: str, result_map: dict) -> str | None:
    """在 result_map 中查找与 name 匹配的事件标准名（含事件名归一化）。"""
    matched = _find_matching_canonical(name, result_map)
    if matched:
        return matched

    # 事件名归一化匹配（去除动作词+地点后缀）
    norm_event = _normalize_event_name(name)
    if not norm_event or len(norm_event) < 2:
        return None
    for canonical in result_map:
        norm_canonical = _normalize_event_name(canonical)
        if not norm_canonical:
            continue
        if norm_event == norm_canonical:
            return canonical
        if norm_event in norm_canonical or norm_canonical in norm_event:
            return canonical
    return None


# ── 内部合并器 ──────────────────────────────────────────────

def _merge_set_list(old: dict, new: dict, key: str) -> list:
    """合并两个 dict 中同名 key 的列表，去重返回。"""
    old_vals = set(old.get(key) or [])
    new_vals = set(new.get(key) or [])
    return list(old_vals | new_vals)


def _merge_rel_list(old: dict, new: dict, key: str) -> list:
    """合并关系列表，按 (target, nature) 去重。"""
    seen = set()
    result = []
    for rel in (old.get(key) or []) + (new.get(key) or []):
        k = (rel.get("target", ""), rel.get("nature", ""))
        if k not in seen:
            seen.add(k)
            result.append(rel)
    return result


def _merge_single_character(old: dict, new: dict) -> dict:
    """合并同一个人物的两条记录。"""
    merged = old.copy()

    # 文本字段取更长的（通常更详细）
    for key in ["identity", "personality", "faction", "gender"]:
        old_val = merged.get(key) or ""
        new_val = new.get(key) or ""
        if new_val and (not old_val or len(new_val) > len(old_val)):
            merged[key] = new_val

    # 集合类字段合并
    merged["aliases"] = _merge_set_list(merged, new, "aliases")
    merged["related_settings"] = _merge_set_list(merged, new, "related_settings")
    merged["relationships"] = _merge_rel_list(merged, new, "relationships")

    # role_tags：取权重更高的标签（而非简单追加，避免主角被后续章节的配角覆盖）
    merged["role_tags"] = _merge_role_tags(
        merged.get("role_tags") or [],
        new.get("role_tags") or [],
    )
    return merged


_ROLE_TAG_WEIGHTS = {
    "主角": 10, "女主": 10, "男主": 10,
    "反派": 9, "BOSS": 8, "隐藏角色": 7,
    "导师": 6, "伙伴": 5, "配角": 4, "路人": 1,
}


def _merge_role_tags(old_tags: list, new_tags: list) -> list:
    """合并角色标签，取权重最高的标签（最多 2 个）。"""
    all_tags = set(old_tags) | set(new_tags)
    if not all_tags:
        return []
    sorted_tags = sorted(all_tags, key=lambda t: _ROLE_TAG_WEIGHTS.get(t, 0), reverse=True)
    return sorted_tags[:2]


def _merge_single_setting(old: dict, new: dict) -> dict:
    """合并同一条设定的两条记录。"""
    merged = old.copy()

    # 取更长的描述
    old_desc = merged.get("description") or ""
    new_desc = new.get("description") or ""
    if len(new_desc) > len(old_desc):
        merged["description"] = new_desc

    # 取更具体的类型（优先有值的）
    if not merged.get("type") and new.get("type"):
        merged["type"] = new["type"]

    # 合并关联关系
    merged["related_characters"] = _merge_set_list(merged, new, "related_characters")
    merged["related_settings"] = _merge_set_list(merged, new, "related_settings")
    return merged


_IMPORTANCE_ORDER = {"高": 3, "中": 2, "低": 1}


def _merge_single_event(old: dict, new: dict) -> dict:
    """合并同一事件的两条记录。"""
    merged = old.copy()

    # 集合类字段（并集）
    for key in ("participants", "cause", "effect"):
        merged[key] = list(set(
            (merged.get(key) or []) + (new.get(key) or [])
        ))

    # 取更长的描述
    old_desc = merged.get("description") or ""
    new_desc = new.get("description") or ""
    if len(new_desc) > len(old_desc):
        merged["description"] = new_desc

    # 取 time/location（如果原来没有）
    for key in ("time", "location"):
        if not merged.get(key) and new.get(key):
            merged[key] = new[key]

    # importance 取较高值
    old_imp = _IMPORTANCE_ORDER.get(merged.get("importance") or "", 0)
    new_imp = _IMPORTANCE_ORDER.get(new.get("importance") or "", 0)
    if new_imp > old_imp:
        merged["importance"] = new["importance"]
    return merged


# ── 事件名归一化 ──────────────────────────────────────────────

def _normalize_event_name(name: str) -> str:
    """
    事件名归一化：去除动作词和地点后缀，用于模糊匹配。

    例：
    - "宝钗进贾府" → "宝钗"
    - "宝钗进府" → "宝钗"
    - "宝钗入贾府" → "宝钗"
    - "宝玉摔玉" → "宝玉摔玉"（无匹配则保留原名）
    """
    from src.utils import normalize_name as _normalize_name
    norm = _normalize_name(name)  # 先去括号

    # 去除常见动作词（进/入/到/上/下）
    norm = re.sub(r'[进入上下到]+', '', norm)

    # 去除常见地点后缀（贾府/府/府中/府上/府里）
    norm = re.sub(r'府[中上里]*$', '', norm)

    return norm.strip()


# ── 公开合并函数 ──────────────────────────────────────────────

def merge_characters(existing: list, new_items: list) -> list:
    """合并人物列表，支持模糊匹配去重。"""
    return merge_by_name(
        existing,
        new_items,
        find_match=_find_matching_character,
        merge_two=_merge_single_character,
    )


def merge_settings(existing: list, new_items: list) -> list:
    """合并设定列表，支持模糊匹配去重。"""
    return merge_by_name(
        existing,
        new_items,
        find_match=_find_matching_setting,
        merge_two=_merge_single_setting,
    )


def merge_events(existing: list, new_items: list) -> list:
    """合并事件列表，支持模糊匹配去重。"""
    return merge_by_name(
        existing,
        new_items,
        find_match=_find_matching_event,
        merge_two=_merge_single_event,
    )
