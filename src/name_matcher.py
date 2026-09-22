"""
Story Wiki - 名称匹配与实体合并模块

将 analyzer / pipeline 中的相似名称匹配与合并逻辑统一维护，
避免两处实现出现行为漂移。

公开 API：
- normalize_name(name):  去除括号内容和首尾空格
- is_similar_name(a, b):  判定两个名称是否指同一实体
- is_name_pair(a, b):     按归一化名做严格的子串匹配（带长度约束）
- find_matching_canonical(name, items, key):  在 items 列表中查找匹配项的标准名
- merge_similar_characters(characters):   合并子串匹配的人物
- merge_with_aliases(existing, new_items, find_match):  通用带别名合并
- merge_by_name(existing, new_items, find_match, merge_two):  按名称合并的通用模板
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional

from src.utils import normalize_name as _normalize_name


# ── 名称相似度判断 ──────────────────────────────────────────────

# 最小匹配长度：低于此长度的名字不做子串匹配（避免单字误匹配）
MIN_NAME_LENGTH = 2
# 子串匹配时短/长 比值下限：避免过度合并
SUBSTRING_RATIO = 0.4


def is_similar_name(a: str, b: str) -> bool:
    """
    判断两个名称是否相似（可能指同一实体）。

    规则：
    1. 精确匹配
    2. 子串匹配（如"贾宝玉"和"宝玉"）
    3. 去括号后匹配
    """
    if not a or not b:
        return False

    # 规则1：精确匹配
    if a == b:
        return True

    # 规则2：子串匹配
    if a in b or b in a:
        return True

    # 规则3：去括号后匹配
    norm_a = _normalize_name(a)
    norm_b = _normalize_name(b)
    if not norm_a or not norm_b:
        return False
    if norm_a == norm_b:
        return True
    if norm_a in norm_b or norm_b in norm_a:
        return True

    return False


def is_name_pair(a: str, b: str) -> bool:
    """
    判断两个归一化名是否应该合并（带长度限制的子串匹配）。

    优化：
    1. 最小长度限制（≥2 字符），避免单字符误匹配
    2. 长度差异不超过 60%（shorter/longer ≥ 0.4）
    """
    if not a or not b:
        return False

    if len(a) < MIN_NAME_LENGTH or len(b) < MIN_NAME_LENGTH:
        return False

    if a in b or b in a:
        shorter, longer = min(len(a), len(b)), max(len(a), len(b))
        if shorter / longer < SUBSTRING_RATIO:
            return False
        return True

    return False


# ── 通用查找匹配项 ──────────────────────────────────────────────

def find_matching_canonical(
    name: str,
    items: dict,
    *,
    check_aliases_of: Optional[Callable[[dict], list[str]]] = None,
) -> Optional[str]:
    """
    在 ``items``（{canonical: item_dict}）中查找与 ``name`` 匹配的标准名。

    Args:
        name: 待匹配的名称
        items: 已有项的 {标准名: 项字典} 映射
        check_aliases_of: 从 item_dict 提取别名的回调；为 None 时不查别名

    Returns:
        匹配到的标准名；未匹配返回 None
    """
    if not name or not items:
        return None

    # 规则1：精确匹配
    if name in items:
        return name

    norm_name = _normalize_name(name)

    # 规则2：归一化后精确 / 子串匹配
    for canonical in items:
        norm_canonical = _normalize_name(canonical)
        if norm_name and norm_canonical and (norm_name == norm_canonical or
                                              norm_name in norm_canonical or
                                              norm_canonical in norm_name):
            return canonical

    # 规则3：模糊相似匹配
    for canonical in items:
        if is_similar_name(name, canonical):
            return canonical

    # 规则4：检查已有项的别名
    if check_aliases_of is not None:
        for canonical, item in items.items():
            aliases = check_aliases_of(item) or []
            if name in aliases:
                return canonical
            for alias in aliases:
                if is_similar_name(name, alias):
                    return canonical

    return None


# ── 模糊人物分组（用于 analyzer 单批去重）────────────────────────

def _find_clusters(characters: list) -> list[list[int]]:
    """按子串匹配分组人物索引（并查集）。"""
    n = len(characters)
    norms = [_normalize_name(c.get("name", "")) for c in characters]
    group_of = list(range(n))

    def find_group(i: int) -> int:
        while group_of[i] != i:
            group_of[i] = group_of[group_of[i]]
            i = group_of[i]
        return i

    def merge_groups(i: int, j: int) -> None:
        gi, gj = find_group(i), find_group(j)
        if gi != gj:
            group_of[gi] = gj

    for i in range(n):
        for j in range(i + 1, n):
            if is_name_pair(norms[i], norms[j]):
                merge_groups(i, j)

    result: dict[int, list[int]] = {}
    for i in range(n):
        result.setdefault(find_group(i), []).append(i)
    return list(result.values())


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

    # 合并关系（按 (target, nature) 去重）
    seen = set()
    rels: list[dict] = []
    for c in group:
        for r in (c.get("relationships") or []):
            k = (r.get("target", ""), r.get("nature", ""))
            if k not in seen:
                seen.add(k)
                rels.append(r)
    best["relationships"] = rels

    # 合并关联设定
    all_rs: set[str] = set()
    for c in group:
        all_rs.update(c.get("related_settings") or [])
    best["related_settings"] = list(all_rs)

    return best


def merge_similar_characters(characters: list[dict]) -> list[dict]:
    """合并子串匹配的同名人物（如 '贾宝玉' 和 '宝玉'）。"""
    if len(characters) <= 1:
        return characters
    clusters = _find_clusters(characters)
    merged: list[dict] = []
    for indices in clusters:
        group = [characters[i] for i in indices]
        if len(group) == 1:
            merged.append(group[0])
        else:
            merged.append(_merge_group(group))
    return merged


# ── 通用带别名合并模板（用于人物/设定/事件）─────────────────────

def merge_by_name(
    existing: Iterable[dict],
    new_items: Iterable[dict],
    *,
    find_match: Callable[[str, dict], Optional[str]],
    merge_two: Callable[[dict, dict], dict],
    name_field: str = "name",
) -> list[dict]:
    """
    按名称匹配合并两个列表的通用模板。

    Args:
        existing: 已有项列表
        new_items: 新增项列表
        find_match: 从已有项中查找匹配项标准名的回调 (name, result_map) -> canonical | None
        merge_two: 合并两条记录的回调 (old, new) -> merged
        name_field: 用于取名字段的 key（默认 'name'）

    Returns:
        合并后的列表
    """
    import copy

    existing_list = list(existing)
    new_list = list(new_items)

    if not existing_list:
        return [copy.deepcopy(c) for c in new_list]
    if not new_list:
        return [copy.deepcopy(c) for c in existing_list]

    # result_map: 标准名 -> 实体（保留对实体的引用，便于就地更新）
    result_map: dict[str, dict] = {}
    for c in existing_list:
        name = c.get(name_field, "")
        if name and name not in result_map:
            result_map[name] = copy.deepcopy(c)

    for c in new_list:
        name = c.get(name_field, "")
        if not name:
            continue

        matched_canonical = find_match(name, result_map)
        if matched_canonical:
            old = result_map[matched_canonical]
            merged = merge_two(old, c)
            result_map[matched_canonical] = merged

            # 如果新名字更长，把旧名也作为别名保留
            if len(name) > len(matched_canonical):
                new_canonical = name
                merged[name_field] = new_canonical
                # 旧标准名加入 aliases
                old_aliases = set(merged.get("aliases") or [])
                old_aliases.add(matched_canonical)
                for alias in c.get("aliases") or []:
                    old_aliases.add(alias)
                merged["aliases"] = list(old_aliases)
                result_map[new_canonical] = merged
                if new_canonical != matched_canonical:
                    del result_map[matched_canonical]
        else:
            result_map[name] = copy.deepcopy(c)

    return list(result_map.values())
