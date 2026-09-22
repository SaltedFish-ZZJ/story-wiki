# 角色标签（role_tags）准确性改进

> **目标**：让 AI 能准确区分主角/配角/路人，提升人物概览页的可读性

**改动范围**：3 个文件，1 个测试文件

---

## 改动文件

| 文件 | 改动内容 |
|------|----------|
| `src/analyzer.py` | prompt 中 role_tags 规则细化（2 处：全文分析 + 分章分析） |
| `src/merger.py` | `_merge_single_character` 中 role_tags 合并逻辑优化 |
| `src/generator.py` | `_write_book_index` 中人物按角色分组显示 |
| `tests/test_role_tags.py` | 新增：测试 role_tags 合并逻辑和分组排序 |

---

## 任务 1：analyzer.py — prompt 规则细化

**现状**：第 93 行和第 295 行的 role_tags 规则只有一行：
```
13. role_tags：角色定位标签，从以下词汇中选择：主角/女主/男主/反派/配角/导师/伙伴/路人/BOSS/隐藏角色
```

**改为**：给每个标签加判断标准

```
13. role_tags：角色定位标签，从以下词汇中选择（每人物只选 1-2 个最贴切的）：
    - 主角/女主/男主：叙事视角人物，或出场频率最高、与核心冲突直接相关的人物
    - 反派：与主角对立、推动核心矛盾的关键人物
    - 配角：有独立性格和故事线，但出场频率低于主角
    - 导师：引导主角成长的关键人物
    - 伙伴：与主角同行、频繁互动的同伴
    - 路人：仅出现 1-2 次、无独立故事线的人物
    - BOSS：阶段性主要对手
    - 隐藏角色：真实身份/目的未完全揭示的人物
    判断依据：出场频率 × 叙事权重 × 与核心冲突的关系。不要把所有人物都标为主角。
```

## 任务 2：merger.py — role_tags 合并优化

**现状**：`_merge_single_character` 没有处理 role_tags，会丢失。

**改动**：合并时取权重更高的标签（而非简单追加），确保"主角"不会被后续章节的"配角"覆盖。

在 `_merge_single_character` 中加入：
```python
# role_tags：取权重更高的标签
_ROLE_TAG_WEIGHTS = {"主角": 10, "女主": 10, "男主": 10, "反派": 9, "BOSS": 8,
                     "隐藏角色": 7, "导师": 6, "伙伴": 5, "配角": 4, "路人": 1}

def _merge_role_tags(old_tags: list, new_tags: list) -> list:
    """合并角色标签，取权重更高的标签集合。"""
    all_tags = set(old_tags or []) | set(new_tags or [])
    if not all_tags:
        return []
    # 按权重排序，保留权重最高的 2 个
    sorted_tags = sorted(all_tags, key=lambda t: _ROLE_TAG_WEIGHTS.get(t, 0), reverse=True)
    return sorted_tags[:2]
```

## 任务 3：generator.py — 人物概览分组显示

**现状**：`_write_book_index` 中人物列表是平铺的，没有分组。

**改动**：在 `_write_book_index` 中按角色分组：
- 🔴 **核心人物**：role_tags 含"主角/女主/男主/反派"
- 🟡 **重要配角**：role_tags 含"配角/导师/伙伴/BOSS"
- ⚪ **其他人物**：其余

```python
# 人物按角色分组
_PROTAGONIST_TAGS = {"主角", "女主", "男主", "反派"}
_IMPORTANT_TAGS = {"配角", "导师", "伙伴", "BOSS", "隐藏角色"}

def _group_characters_by_role(characters: list) -> dict[str, list]:
    groups = {"核心人物": [], "重要配角": [], "其他人物": []}
    for c in characters:
        tags = set(c.get("role_tags") or [])
        if tags & _PROTAGONIST_TAGS:
            groups["核心人物"].append(c)
        elif tags & _IMPORTANT_TAGS:
            groups["重要配角"].append(c)
        else:
            groups["其他人物"].append(c)
    return groups
```

## 任务 4：测试

- 测试 `_merge_role_tags`：主角 + 配角 → 保留主角
- 测试 `_group_characters_by_role`：分组正确性
- 运行全量测试确保不破坏现有功能

## 任务 5：用富爸爸穷爸爸测试

```bash
python src/main.py --input "story/富爸爸穷爸爸_(罗伯特·清崎,莎伦·莱希特,萧明)_(z-library.sk,_1lib.sk,_z-lib.sk).txt" --title "富爸爸穷爸爸"
```

验证：
- [ ] 人物 role_tags 是否准确（罗伯特=主角，富爸爸=导师，穷爸爸=配角）
- [ ] _index.md 是否按角色分组显示
- [ ] 角色标签合并逻辑正确
