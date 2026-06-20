# Story Wiki — AI Agent 指令

## 项目简介

Story Wiki 是一个 AI 驱动的故事知识库系统。能将任意文字材料（小说、历史事件、传记等）自动分析为结构化的 Obsidian 笔记，支持人物关系图谱可视化。

未来方向：基于分析结果反向创作——用户提供想法/人物卡，AI 协作构建世界观并驱动人物推演，生成小说。

## 技术栈

- **语言**：Python 3.13
- **AI 模型**：DeepSeek API
- **输出格式**：Obsidian Markdown（frontmatter + wikilink）
- **依赖**：requests, json, re, pathlib

## 项目结构

```
story_wiki/
├── AGENTS.md              ← 你正在看的文件
├── README.md              ← 项目说明
├── src/                   ← 源代码（待创建）
│   ├── analyzer.py        ← AI 分析核心
│   ├── extractor.py       ← 文本提取（txt/epub/pdf）
│   ├── splitter.py        ← 章节切分
│   ├── generator.py       ← Obsidian 笔记生成
│   └── config.py          ← 配置（API key、路径等）
├── vault/                 ← Obsidian vault 输出目录（待创建）
├── data/                  ← 输入文本和中间数据（待创建）
│   └── input/             ← 放入待分析的文本
└── docs/                  ← 项目文档
```

## 开发约定

1. **代码风格**：中文注释，函数/变量名用英文 snake_case
2. **配置管理**：API key 存环境变量或 config.py，不硬编码
3. **错误处理**：AI 返回非 JSON 时有 fallback，不崩溃
4. **增量开发**：每次只改一个模块，改完测试再继续
5. **输出验证**：每次生成后必须用 Obsidian 打开验证 Graph View

## 核心流程

```
输入文本 → 文本提取 → (章节切分) → AI 分析 → JSON 结构化 → 生成 Obsidian MD → 验证
```

## 数据模型

### 人物卡片 frontmatter
```yaml
type: character
source: analyzed | generated
origin: 作品名
tags: [character, 势力名]
aliases: [别名]
```

### 设定卡片 frontmatter
```yaml
type: setting
source: analyzed | generated
origin: 作品名
tags: [setting, 地点|组织|体系]
```

### 关系表达
直接在人物卡的「人际关系」章节用 wikilink：
```markdown
- [[林黛玉]] — 恋人
- [[贾政]] — 父子
```
Obsidian Graph View 自动识别为边。

## 当前阶段

**Phase 1：最小 Demo**
- [x] 项目文档骨架
- [ ] Vault 结构搭建
- [ ] 文本读取模块
- [ ] AI 分析 prompt + API 调用
- [ ] Obsidian 笔记生成
- [ ] 用真实文本验证 Graph View
