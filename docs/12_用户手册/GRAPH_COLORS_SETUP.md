# 关系图谱颜色配置 - 快速设置指南

> 配置时间：2026-06-22
> 文件路径：`D:\Obsidian_Work\story_wiki\.obsidian\snippets\graph-colors.css`

---

## 📍 文件位置

```
D:\Obsidian_Work\story_wiki\.obsidian\snippets\graph-colors.css
```

**目录结构：**
```
D:\Obsidian_Work\story_wiki\
└── .obsidian/
    └── snippets/
        └── graph-colors.css  ← CSS 配置文件
```

---

## 🎨 颜色配置

### 节点颜色

| 类型 | 颜色 | 说明 |
|------|------|------|
| 人物 | 🔵 蓝色 (#4A90E2) | 所有人物节点 |
| 事件 | 🟠 橙色 (#F5A623) | 所有事件节点 |
| 设定 | 🟢 绿色 (#7ED321) | 所有设定节点 |

### 边颜色

| 关系类型 | 颜色 |
|----------|------|
| 恋人/夫妻 | 🔴 红色 |
| 父子/母子 | 🔵 蓝色 |
| 师徒 | 🟣 紫色 |
| 敌对 | 🟠 橙色 |
| 朋友 | 🟢 绿色 |

---

## 🔧 启用步骤

### 步骤 1：确认文件存在

```bash
# 检查文件
ls -la "D:\Obsidian_Work\story_wiki\.obsidian\snippets\graph-colors.css"
```

### 步骤 2：在 Obsidian 中启用

1. 打开 Obsidian
2. 进入 **设置** → **外观** → **CSS 代码片段**
3. 点击 **文件夹图标** 📁，打开 snippets 目录
4. 确保 `graph-colors.css` 文件在目录中
5. 点击 **刷新按钮** 🔄
6. 找到 `graph-colors`，点击 **启用** 开关

### 步骤 3：重新生成卡片

```bash
cd D:\agent_workspace\story_wiki

# 重新分析红楼梦，生成带颜色的卡片
python src/main.py --input story/红楼梦.txt --title "红楼梦" --no-cache
```

### 步骤 4：查看 Graph View

1. 打开 Obsidian
2. 按 `Ctrl+G`（Windows）或 `Cmd+G`（Mac）
3. 查看不同颜色的节点

---

## 📊 效果预览

```
        🔵 贾宝玉 (蓝色)
       / | \
      /  |  \
🔵 林黛玉  |  🔵 薛宝钗
      \  |  /
       \ | /
        🟠 宝黛初见 (橙色)
         |
        🟢 荣国府 (绿色)
```

---

## ⚠️ 常见问题

### Q1: 节点没有颜色？

**原因：** CSS 文件未启用或 Frontmatter 缺少 `color` 字段

**解决：**
1. 检查 CSS 是否启用：设置 → 外观 → CSS 代码片段
2. 重新生成卡片：`python src/main.py --input story/红楼梦.txt --title "红楼梦" --no-cache`

### Q2: 文件在哪里？

**路径：**
```
D:\Obsidian_Work\story_wiki\.obsidian\snippets\graph-colors.css
```

### Q3: 如何自定义颜色？

编辑 CSS 文件，修改颜色值：

```css
/* 修改人物节点颜色 */
.graph-view.color-character {
  --color: #你的颜色;
  --dot-color: #你的颜色;
}
```

---

## 🎯 验证清单

- [ ] 文件存在于正确路径
- [ ] CSS 已在 Obsidian 中启用
- [ ] 卡片文件包含 `color` 字段
- [ ] Graph View 显示不同颜色

---

## 📚 相关文档

- [GRAPH_COLORS_GUIDE.md](GRAPH_COLORS_GUIDE.md) - 完整使用指南
- [PARALLEL_DEV_SUMMARY.md](../02_功能设计/PARALLEL_DEV_SUMMARY.md) - 并行开发总结

---

## 🎉 总结

**文件路径：** `D:\Obsidian_Work\story_wiki\.obsidian\snippets\graph-colors.css`

**启用方法：**
1. 确认文件在正确位置
2. 在 Obsidian 中启用 CSS Snippets
3. 重新生成卡片
4. 打开 Graph View 查看效果

**效果：**
- 人物：🔵 蓝色
- 事件：🟠 橙色
- 设定：🟢 绿色

现在你可以在 Obsidian 中看到丰富多彩的关系图谱了！ 🚀
