# 子文件夹重构方案

> 状态：规划中 | 优先级：中 | 工作量：2-3 天
> 目标：按角色分组建立物理子文件夹，为后续扩展（Web UI、多维视图）打基础

---

## 目标结构

```
作品名/
├── _index.md
├── timeline.md
├── characters/
│   ├── 主要人物/
│   │   ├── 罗伯特.md
│   │   └── 富爸爸.md
│   ├── 次要人物/
│   │   ├── 穷爸爸.md
│   │   └── 迈克.md
│   └── 其他人物/
│       └── 乞丐.md
├── settings/
│   ├── 地点/
│   │   └── 凤凰城.md
│   ├── 组织/
│   │   └── 麦当劳.md
│   └── 概念/
│       └── 现金流游戏.md
└── events/
    ├── 重大事件/
    │   └── 免费工作学习.md
    └── 一般事件/
        └── 凤凰城房产投资.md
```

## 分类规则

### characters 分类（基于 role_tags）
| 子文件夹 | 匹配规则 |
|----------|----------|
| 主要人物 | role_tags 含 `主角/女主/男主/反派` |
| 次要人物 | role_tags 含 `配角/导师/伙伴/BOSS/隐藏角色` |
| 其他人物 | 其余（路人、无标签） |

### settings 分类（基于 type 字段）
| 子文件夹 | 匹配规则 |
|----------|----------|
| 地点 | type 含 `地点/地名/城市/国家` |
| 组织 | type 含 `组织/公司/势力/团体` |
| 概念 | type 含 `概念/体系/规则/制度/工具` |
| 其他 | 其余 |

### events 分类（基于 importance 字段）
| 子文件夹 | 匹配规则 |
|----------|----------|
| 重大事件 | importance == "高" |
| 一般事件 | importance == "中" 或 "低" |

---

## 影响范围扫描

### 需要修改的文件（按改动量排序）

#### 1. generator.py（57 处路径引用）
- **目录创建**：`char_dir` / `setting_dir` / `event_dir` → 需要创建子文件夹
- **文件写入**：`_write_character_card` / `_write_setting_card` / `_write_event_card` → 输出路径变化
- **wikilink 生成**（约 20 处）：
  - `[[characters/{name}|{name}]]` → `[[characters/{子文件夹}/{name}|{name}]]`
  - `[[settings/{name}|{name}]]` → `[[settings/{子文件夹}/{name}|{name}]]`
  - `[[events/{name}|{name}]]` → `[[events/{子文件夹}/{name}|{name}]]`
- **关键函数**：
  - `_write_book_index()` — 人物列表、设定列表、事件列表中的链接
  - `_write_character_card()` — 人际关系、关联设定、高光时刻中的链接
  - `_write_setting_card()` — 关联人物、关联设定中的链接
  - `_write_event_card()` — 参与人物、发生地点、前置事件中的链接
  - `generate_timeline_page()` — 时间线中的链接
  - `_build_mermaid_graph()` — Mermaid 图中无影响（只用节点名）

#### 2. vault_manager.py（45 处路径引用）
- **目录扫描**：遍历 `characters/` 查找人物文件 → 需要递归到子文件夹
- **wikilink 解析**：从文件内容提取链接时，路径格式变化
- **卡片更新**：更新已有卡片时，路径解析逻辑变化
- **关键函数**：
  - `_scan_books()` — 扫描 vault 目录识别作品
  - `_read_character_card()` / `_read_setting_card()` / `_read_event_card()` — 读取卡片
  - `_update_character_card()` / `_update_setting_card()` / `_update_event_card()` — 更新卡片
  - `_write_*_card()` 系列 — 写入卡片时的路径

#### 3. tests/conftest.py（10 处）
- 测试 fixtures 中的目录结构需要更新

#### 4. tests/test_generator.py（1 处）
- 可能有断言检查路径格式

#### 5. tests/test_vault_manager.py（19 处）
- 路径断言最多，需要全部更新

#### 6. tests/test_project_manager.py（3 处）

#### 7. tests/test_integration_growth.py（3 处）

#### 8. tests/test_character_growth.py（1 处）

---

## 实现方案

### 核心设计：路径解析函数

在 `generator.py` 中新增一个统一的路径解析函数，所有 wikilink 生成和文件写入都通过它：

```python
def _get_subfolder(item: dict, item_type: str) -> str:
    """根据数据字段判断子文件夹名。"""
    if item_type == "character":
        tags = set(item.get("role_tags") or [])
        if tags & {"主角", "女主", "男主", "反派"}:
            return "主要人物"
        elif tags & {"配角", "导师", "伙伴", "BOSS", "隐藏角色"}:
            return "次要人物"
        return "其他人物"
    
    if item_type == "setting":
        stype = (item.get("type") or item.get("setting_type") or "").lower()
        if any(k in stype for k in ["地点", "地名", "城市", "国家"]):
            return "地点"
        elif any(k in stype for k in ["组织", "公司", "势力", "团体"]):
            return "组织"
        elif any(k in stype for k in ["概念", "体系", "规则", "制度", "工具"]):
            return "概念"
        return "其他"
    
    if item_type == "event":
        importance = item.get("importance") or ""
        if importance == "高":
            return "重大事件"
        return "一般事件"
    
    return "其他"


def _char_link(name: str, display: str = None, item: dict = None) -> str:
    """生成人物 wikilink，自动带子文件夹路径。"""
    if item:
        subfolder = _get_subfolder(item, "character")
        return f"[[characters/{subfolder}/{name}|{display or name}]]"
    # fallback：无法判断时用扁平路径
    return f"[[characters/{name}|{display or name}]]"


def _setting_link(name: str, display: str = None, item: dict = None) -> str:
    """生成设定 wikilink。"""
    if item:
        subfolder = _get_subfolder(item, "setting")
        return f"[[settings/{subfolder}/{name}|{display or name}]]"
    return f"[[settings/{name}|{display or name}]]"


def _event_link(name: str, display: str = None, item: dict = None) -> str:
    """生成事件 wikilink。"""
    if item:
        subfolder = _get_subfolder(item, "event")
        return f"[[events/{subfolder}/{name}|{display or name}]]"
    return f"[[events/{name}|{display or name}]]"
```

### 关键难点

**wikilink 中 item 信息缺失的场景**：
在生成人物卡片时，链接目标可能是另一个已知人物，但只有名字没有完整数据。
例如：`relationships = [{"target": "富爸爸", "nature": "导师"}]`，这里只有 `"富爸爸"` 这个名字。

**解决方案**：在 `generate_vault()` 中预构建一个名字→子文件夹的映射表，传给各个写入函数。

```python
def generate_vault(analysis: dict, output_dir: Path = None) -> list[str]:
    # 预构建映射
    char_folder_map = {c["name"]: _get_subfolder(c, "character") for c in characters}
    setting_folder_map = {s["name"]: _get_subfolder(s, "setting") for s in settings}
    event_folder_map = {e["name"]: _get_subfolder(e, "event") for e in events}
    
    for char in characters:
        _write_character_card(char, char_dir, title, events,
                              char_folder_map, setting_folder_map, event_folder_map)
    ...
```

### vault_manager.py 的兼容策略

扫描目录时递归查找，不再硬编码路径层级：

```python
def _scan_books(vault_dir: Path) -> list[dict]:
    for book_dir in vault_dir.iterdir():
        char_dir = book_dir / "characters"
        if char_dir.exists():
            # 递归查找所有 .md 文件（兼容子文件夹和扁平结构）
            char_files = list(char_dir.rglob("*.md"))
            ...
```

---

## 兼容性

- **已有笔记**：旧的扁平结构文件不会自动迁移，但 `vault_manager.py` 用 `rglob` 递归查找，所以旧文件仍然能被读取
- **Graph View**：wikilink 路径变了，Obsidian 会自动识别新路径
- **向后兼容**：不保留旧路径的双重写入，新分析全部走新结构

---

## 执行计划

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 1. 新增路径解析函数 | generator.py | 小 |
| 2. 改造目录创建逻辑 | generator.py | 小 |
| 3. 改造所有 wikilink 生成（~20 处） | generator.py | 中 |
| 4. 改造目录扫描逻辑（rglob） | vault_manager.py | 中 |
| 5. 改造卡片读写逻辑 | vault_manager.py | 中 |
| 6. 更新测试 fixtures | tests/conftest.py | 中 |
| 7. 更新测试断言（37 处） | 6 个测试文件 | 中 |
| 8. 运行全量测试 | — | 小 |
| 9. 端到端验证 | 富爸爸穷爸爸 | 小 |

**总工作量**：2-3 天（主要在 generator.py 的 20 处 wikilink 改造和 vault_manager.py 的扫描逻辑）

---

## 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| wikilink 路径错误导致 Graph View 断链 | 高 | 全量测试 + 端到端验证 |
| vault_manager 扫描遗漏子文件夹中的人物 | 高 | 用 rglob 替代 iterdir |
| settings/events 的 type 字段为空导致分类错误 | 低 | fallback 到"其他" |
| 旧笔记不兼容 | 中 | rglob 递归兼容 |

---

## 决策点

**是否值得做？**

优点：
- 文件组织更清晰，手动浏览时一目了然
- 为后续 Web UI 的分类展示打基础
- Obsidian 文件浏览器中直接看到分组

缺点：
- 改动量大（约 100 处路径引用）
- 旧笔记需要重新分析才能享受新结构
- 增加了路径解析的复杂度

**建议**：如果确定要做，趁现在代码量可控时做，越晚做改动越大。
