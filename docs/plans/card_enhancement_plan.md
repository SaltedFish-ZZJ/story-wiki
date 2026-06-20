# 卡片优化计划 — B+C+D+E 组合方案

> 创建时间：2026-06-20
> 状态：进行中

## 目标

让单个卡片内容更丰富、更具视觉吸引力，参考 RPG 游戏但适配各类书籍题材。

## 方案设计

### B. 状态栏 + 标签云

**人物卡片**
```
> 🟢 活跃 | 阵营：荣国府 | 定位：主角 · 女主 · 恋人
```

- 状态：🟢活跃 / ⚫已故 / 🔴失踪 / 🟡退场（从文本推断）
- 阵营：直接用 faction 字段
- 定位：AI 提取的角色类型标签（主角/反派/导师/配角/路人等）

**设定卡片**
```
> 类型：地点 | 影响力：⭐⭐⭐⭐ | 关联人物：6
```

**事件卡片**
```
> 📍 大观园 | 👥 5人参与 | 🔗 前置：2个事件
```

---

### C. 成就/里程碑

人物卡片新增 `## 🏆 高光时刻` 区域，列出该人物参与的关键事件：

```markdown
## 🏆 高光时刻
- [[events/宝黛初见|宝黛初见]] — 初次相遇，一见如故
- [[events/黛玉葬花|黛玉葬花]] — 感伤身世，以花自喻
- [[events/焚稿断情|焚稿断情]] — 绝望焚稿，断绝情丝
```

**数据来源**：从 events 中筛选 participants 包含该人物的事件，按重要程度排序。

---

### D. 语录卡片

人物卡片新增 `## 💬 经典语录` 区域：

```markdown
## 💬 经典语录
> "我是为我的心。"
> "你既为我之知己，自然我亦为你之知己。"
> "早知今日，何必当初。"
```

**实现方式**：
- 修改 analyzer.py prompt，让 AI 提取 2-3 句角色代表性台词
- 新增字段 `quotes: ["语录1", "语录2", ...]`

---

### E. 关系子图

人物卡片新增 `## 🕸️ 关系网` 区域，嵌入小型 Mermaid 图：

```markdown
## 🕸️ 关系网
```mermaid
graph LR
    宝玉 -- "恋人" --> 黛玉
    宝玉 -- "夫妻" --> 宝钗
    宝玉 -- "母子" --> 王夫人
    宝玉 -- "父子" --> 贾政
`` `
```

**实现方式**：
- generator.py 新增 `_build_character_mermaid()` 函数
- 只展示该人物的直接关系（一级关系），最多 8 条
- 边的标签用 relationship.nature

---

## 数据结构变更

### analyzer.py prompt 新增字段

```json
{
  "characters": [
    {
      "name": "人名",
      "identity": "身份描述",
      "personality": "性格特征",
      "role_tags": ["主角", "女主"],  // 新增
      "status": "活跃",                // 新增：活跃/已故/失踪/退场
      "quotes": ["语录1", "语录2"],   // 新增
      // ... 其他字段不变
    }
  ]
}
```

### generator.py 新增函数

| 函数 | 用途 |
|------|------|
| `_build_status_bar(char)` | 生成状态栏 |
| `_build_role_tags(char)` | 生成角色定位标签 |
| `_build_achievements(char, events)` | 生成高光时刻列表 |
| `_build_quotes_section(char)` | 生成语录区域 |
| `_build_character_mermaid(char)` | 生成关系子图 |

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `src/analyzer.py` | SYSTEM_PROMPT 新增 role_tags/status/quotes 字段 |
| `src/analyzer.py` | CHAPTER_SYSTEM_PROMPT 同步新增字段 |
| `src/generator.py` | 新增 5 个辅助函数 |
| `src/generator.py` | `_write_character_card()` 添加新区域 |
| `src/generator.py` | `_write_setting_card()` 添加状态栏 |
| `src/generator.py` | `_write_event_card()` 添加状态栏 |
| `src/generator.py` | `_merge_character_data()` 处理新字段合并 |

---

## 兼容性

- 新字段（role_tags/status/quotes）为可选，旧数据无这些字段时自动降级
- 不影响现有测试，新增字段不影响 JSON 解析
- 增量合并逻辑需同步更新

---

## 验证方式

1. 运行现有单元测试：`python -m pytest tests/`
2. 用红楼梦片段测试生成效果
3. 检查 Obsidian 中卡片渲染效果
