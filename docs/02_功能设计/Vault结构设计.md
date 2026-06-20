# Vault 结构设计

## 设计原则

1. **单 Vault 多作品**：一个 vault 管理所有作品，每作品一个文件夹
2. **Graph 隔离**：Obsidian Graph View 用 `path:作品名` 过滤单作品关系
3. **格式统一**：分析来的和创作来的用同一套格式，靠 frontmatter 的 `source` 字段区分

## 目录结构

```
D:\Obsidian_Work\story_wiki\     ← Obsidian vault 根目录
├── .obsidian/                     ← Obsidian 配置
├── _templates/                    ← 笔记模板
│   ├── character.md
│   └── setting.md
│
├── 红楼梦/                        ← 作品 A
│   ├── _index.md                  ← 作品索引
│   ├── characters/
│   │   ├── 贾宝玉.md
│   │   ├── 林黛玉.md
│   │   └── ...
│   └── settings/
│       ├── 荣国府.md
│       └── ...
│
├── 三体/                          ← 作品 B
│   ├── _index.md
│   ├── characters/
│   └── settings/
│
└── my_novel/                      ← 创作项目
    ├── _index.md
    ├── characters/
    ├── settings/
    └── chapters/                  ← 生成的章节
```

## .obsidian 配置建议

### app.json（推荐设置）

```json
{
  "showLineNumber": true,
  "strictLineBreaks": false,
  "alwaysUpdateLinks": true
}
```

### Graph View 过滤

在 Obsidian Graph View 中使用过滤器查看单部作品：
- `path:红楼梦` → 只看红楼梦的关系图
- `path:三体` → 只看三体的关系图
- 不加过滤 → 看所有作品的全局关系图

## 多作品管理

### 全局索引

vault 根目录放一个全局 `_index.md`，列出所有已分析的作品：

```markdown
# Story Wiki

## 已分析作品
- [[红楼梦/_index|红楼梦]] — 曹雪芹
- [[三体/_index|三体]] — 刘慈欣

## 创作项目
- [[my_novel/_index|我的小说]] — 进行中
```

### 跨作品查询（Dataview 插件）

安装 Dataview 插件后可以做动态查询：

```dataview
TABLE gender, faction
FROM "红楼梦/characters"
```
