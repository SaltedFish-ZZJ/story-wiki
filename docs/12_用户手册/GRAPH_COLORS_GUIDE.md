# 关系图谱颜色使用指南

> 完整的 Graph View 颜色配置说明，帮助你充分利用故事知识库的可视化功能。

## 概述

Story Wiki 为不同类型的实体自动分配不同颜色，让你在 Obsidian Graph View 中一眼区分人物、事件和设定。

| 实体类型 | 颜色 | frontmatter 字段 |
|----------|------|-----------------|
| 人物 | 🔵 蓝色 `#4A90E2` | `color: character` |
| 事件 | 🟠 橙色 `#F5A623` | `color: event` |
| 设定 | 🟢 绿色 `#7ED321` | `color: setting` |

## 颜色实现原理

节点颜色通过两层机制实现（双重保障）：

### 1. CSS Snippet（主要方式）

`.obsidian/snippets/graph-colors.css` 定义了基于 CSS 类选择器的颜色规则：

```css
.graph-view.color-character {
  --color: #4A90E2;
  --dot-color: #4A90E2;
}
```

当笔记的 frontmatter 包含 `color: character` 时，Obsidian 自动为该节点添加 `color-character` CSS 类，从而应用蓝色。

### 2. graph.json colorGroups（备用方式）

`.obsidian/graph.json` 中配置了基于 frontmatter 查询的分组规则：

```json
"colorGroups": [
  { "query": "color:character", "color": { "a": 1, "rgb": 4997346 } },
  { "query": "color:event",     "color": { "a": 1, "rgb": 16098851 } },
  { "query": "color:setting",   "color": { "a": 1, "rgb": 8311585 } }
]
```

即使 CSS snippet 未启用，colorGroups 也能确保节点颜色正确显示。

## 如何自定义颜色

### 修改 CSS Snippet

编辑 `.obsidian/snippets/graph-colors.css`，修改对应节点的 `--color` 值：

```css
/* 将人物颜色改为紫色 */
.graph-view.color-character {
  --color: #9B59B6;
  --dot-color: #9B59B6;
}
```

修改后在 Obsidian 中重新启用 CSS snippet 即可生效。

### 修改 graph.json colorGroups

编辑 `.obsidian/graph.json`，修改 `colorGroups` 中的 RGB 值：

```json
{ "query": "color:character", "color": { "a": 1, "rgb": 10233606 } }
```

RGB 值计算方式：`R × 65536 + G × 256 + B`（例如紫色 `#9B59B6` = 154 × 65536 + 89 × 256 + 182 = 10140598）。

## 按作品筛选图谱

在 Graph View 的搜索框中输入路径过滤器，可以只查看某部作品的图谱：

```
path:红楼梦
```

这会过滤出所有路径包含"红楼梦"的节点及其连接。组合使用：

```
path:红楼梦 AND color:character
```

只查看红楼梦中的人物节点。

## Mermaid 图谱 vs Obsidian Graph View

项目同时使用两种图谱展示方式：

| 特性 | Mermaid 图谱 | Obsidian Graph View |
|------|-------------|-------------------|
| 位置 | 嵌入在笔记内部 | Obsidian 全局面板 |
| 交互 | 静态图片 | 可拖拽、缩放、点击 |
| 颜色 | 代码中固定 | 由 CSS / colorGroups 控制 |
| 范围 | 单个笔记的关系 | 整个 vault 的关系网络 |
| 适用 | 快速查看某人物的关系 | 全局关系探索 |

- **Mermaid**：在每张人物卡底部显示该人物的直接关系（最多 8 条）
- **Graph View**：在 Obsidian 左侧面板显示所有人物、事件、设定的完整关系网络

## 图谱布局优化

`graph.json` 中的力导向布局参数已针对故事图谱优化：

| 参数 | 值 | 说明 |
|------|-----|------|
| `repelStrength` | 20 | 节点排斥力，值越大间距越大 |
| `centerStrength` | 0.7 | 居中力，值越大图谱越集中 |
| `linkDistance` | 250 | 连线目标长度（像素） |
| `linkStrength` | 1 | 连线弹性 |

如果图谱太散，增大 `centerStrength`；如果节点重叠，增大 `repelStrength`。

## 常见问题

### Q: 节点没有颜色？

1. 确认 CSS snippet 已启用：设置 → 外观 → CSS 代码片段 → 启用 `graph-colors`
2. 确认笔记 frontmatter 包含 `color: character/setting/event`
3. 如果是通过 VaultManager 更新的卡片，确保使用 v0.8.0+ 版本（已修复 color 字段丢失问题）

### Q: 如何让更多节点显示在 Graph View 中？

在 Graph View 设置中勾选 "Show orphan nodes"（显示孤立节点），并确保笔记之间有 `[[wikilink]]` 连接。

### Q: 如何导出 Graph View 图片？

Obsidian 原生支持右键 Graph View → "Export as PNG"。也可以使用社区插件 "Graph Analysis" 获得更多导出选项。

### Q: 边（连线）能着色吗？

Obsidian Graph View 目前不支持为单条边设置颜色。所有连线统一为默认颜色。如需按关系类型区分，建议使用 Mermaid 图谱（嵌入在笔记中）。
