# Story Wiki — AI Agent 指令

## 项目简介

Story Wiki 是一个 AI 驱动的故事知识库系统。能将任意文字材料（小说、历史事件、传记等）自动分析为结构化的 Obsidian 笔记，支持人物关系图谱可视化。

未来方向：基于分析结果反向创作——用户提供想法/人物卡，AI 协作构建世界观并驱动人物推演，生成小说。

## 技术栈

- **语言**：Python 3.13
- **AI 模型**：小米 mimo-v2.5（通过 token-plan API）
- **输出格式**：Obsidian Markdown（frontmatter + wikilink）
- **依赖**：requests, json, re, pathlib

## 项目结构

```
story_wiki/
├── AGENTS.md              ← 你正在看的文件
├── README.md              ← 项目说明
├── src/                   ← 源代码
│   ├── config.py          ← 配置（API key、路径、参数）
│   ├── extractor.py       ← 文本提取（txt）
│   ├── splitter.py        ← 章节切分
│   ├── analyzer.py        ← AI 分析核心 + 分章 prompt
│   ├── pipeline.py        ← 分章分析管线
│   ├── generator.py       ← Obsidian 笔记生成
│   ├── main.py            ← CLI 入口（自动判断分章）
│   └── agent.py           ← 交互式分析（支持分章）
├── data/                  ← 输入文本和中间数据
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

**Phase 1：最小 Demo** ✅ 已完成 (2026-06-20)
- [x] 项目文档骨架
- [x] Vault 结构搭建
- [x] 文本读取模块
- [x] AI 分析 prompt + API 调用
- [x] Obsidian 笔记生成
- [x] 用真实文本验证 Graph View

**Phase 2：扩展功能** 🔧 开发中
- [x] 章节切分器（splitter.py — 按"第X章/第X回"等模式切分）
- [x] 逐章分析 + 上下文传递（pipeline.py + analyzer.py 分章 prompt）
- [x] 全局合并去重（同名人物合并、关系去重）
- [x] main.py / agent.py 自动判断分章
- [ ] epub/pdf 格式支持
- [ ] 事件卡片、时间线
- [ ] 多本书管理

**Phase 3：创作方向** 🔮 远期
- [ ] 种子输入 → AI 提问协作 → 世界观构建
- [ ] 人物卡 + 设定 → AI 驱动人物推演
- [ ] 推演结果 → 章节化小说输出
