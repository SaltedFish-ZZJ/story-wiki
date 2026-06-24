# Story Wiki — AI Agent 指令

## 项目简介

Story Wiki 是一个 AI 驱动的故事知识库系统，包含**分析管线**和**创作管线**两大核心能力：

- **分析**：输入任意文字材料（小说/历史事件/传记），AI 自动提取人物、设定、事件，生成 Obsidian 笔记，支持人物关系图谱可视化
- **创作**：基于知识库驱动 AI 创作新小说（情节大纲 → 逐章生成 → 质量检查 → 合并输出）

## 技术栈

- **语言**：Python 3.13
- **AI 模型**：小米 mimo-v2.5（通过 token-plan API，OpenAI 兼容格式）
- **输出格式**：Obsidian Markdown（frontmatter + wikilink）
- **依赖**：requests, psutil, ebooklib（epub）, pymupdf（pdf）

## 项目结构

```
story_wiki/
├── AGENTS.md                ← 你正在看的文件
├── README.md                ← 项目说明
├── src/                     ← 源代码（20 个模块）
│   ├── interfaces.py        ← 接口规范（8 个接口 + 5 个数据结构）
│   ├── config.py            ← 配置（API key、路径、参数、内存监控）
│   ├── utils.py             ← 工具函数（文件名处理、frontmatter、名称归一化）
│   │
│   │  ── 分析管线 ──
│   ├── extractor.py         ← 文本提取（txt/epub/pdf，流式读取，HTML 清理）
│   ├── splitter.py          ← 章节切分（按标题模式/按字数，重叠窗口，句子边界）
│   ├── analyzer.py          ← AI 分析核心（API 调用 + JSON 解析 + 分章 prompt）
│   ├── pipeline.py          ← 分章分析管线（切分→逐章分析→合并去重+进度+缓存）
│   ├── generator.py         ← Obsidian .md 文件生成（增量写入，节点颜色）
│   │
│   │  ── 创作管线 ──
│   ├── vault_manager.py     ← 知识库管理（读取/解析 Obsidian 笔记）
│   ├── plot_generator.py    ← 情节大纲生成（4 个 AI Prompt）
│   ├── chapter_generator.py ← 章节生成 + 质量检查（AI + 规则双模式）
│   ├── novel_logger.py      ← 章节保存、进度追踪、断点续写、小说合并
│   ├── create.py            ← 创作管线入口（串联 VM→PG→CG→NL）
│   ├── quality_checker.py   ← 质量检测（逻辑一致性、字数、重复、敏感词）
│   ├── converter.py         ← 格式转换（EPUB/TXT/平台格式）
│   ├── commercial_manager.py← 商业化管理（收益估算、平台比较）
│   ├── project_manager.py   ← 跨作品管理（多书对比、相似人物、跨书时间线）
│   ├── character_growth.py  ← 角色成长曲线（事件提取、曲线分析、阶段识别）
│   │
│   │  ── 入口 ──
│   ├── main.py              ← CLI 入口（分析模式 + 创作模式）
│   └── agent.py             ← 交互式分析（支持分章/缓存管理）
│
├── tests/                   ← 测试（516 个测试函数）
├── data/
│   ├── input/               ← 待分析文本放这里
│   ├── novels/              ← 生成的小说输出
│   └── state/cache/analysis/← 分析结果缓存（7天过期）
├── story/                   ← 原始文本文件（红楼梦、水浒传等）
└── docs/                    ← 项目文档
```

## 核心流程

### 分析管线
```
输入文本 → 文本提取 → (章节切分) → AI 分析 → JSON 结构化 → 生成 Obsidian MD → 验证
```

### 创作管线
```
知识库(VaultManager) → 情节大纲(PlotGenerator) → 逐章生成(ChapterGenerator) → 保存合并(NovelLogger)
```

### 端到端
```
输入文本 → 分析 → 知识库 → 情节大纲 → 逐章生成 → 保存/合并 → 完整小说
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

### 事件卡片 frontmatter
```yaml
type: event
name: 事件名（如"宝黛初见"）
time: 时间描述
participants: [人物名1, 人物名2]
location: 地点名
description: 一句话描述
cause: [前置事件名]
chapter: 章节名
```

### 关系表达
直接在人物卡的「人际关系」章节用 wikilink：
```markdown
- [[林黛玉]] — 恋人
- [[贾政]] — 父子
```
Obsidian Graph View 自动识别为边。

## 开发约定

1. **代码风格**：中文注释，函数/变量名用英文 snake_case
2. **配置管理**：API key 存 `.env` 文件，不硬编码
3. **错误处理**：AI 返回非 JSON 时有 fallback，不崩溃
4. **增量开发**：每次只改一个模块，改完测试再继续
5. **输出验证**：每次生成后必须用 Obsidian 打开验证 Graph View
6. **测试**：修改代码后运行 `python -m pytest tests/ -v` 确保通过

## 当前阶段

**Phase 1：最小 Demo** ✅ 已完成 (2026-06-20)
- [x] 项目文档骨架、Vault 结构搭建
- [x] 文本读取模块（txt/epub/pdf）
- [x] AI 分析 prompt + API 调用
- [x] Obsidian 笔记生成 + Graph View 验证

**Phase 2：扩展功能** ✅ 已完成 (2026-06-22)
- [x] 章节切分器（splitter.py — 按"第X章/第X回"等模式切分）
- [x] 逐章分析 + 上下文传递（pipeline.py + analyzer.py 分章 prompt）
- [x] 全局合并去重（同名人物合并、关系去重）
- [x] main.py / agent.py 自动判断分章
- [x] epub/pdf 格式支持（extractor.py — ebooklib + pymupdf）
- [x] 事件卡片 + 时间线 + 关系图谱（Mermaid 可视化）
- [x] 增量分析（新章节追加到已有笔记，不覆盖）
- [x] 分析进度条 + 结果缓存（md5 哈希，7天过期）
- [x] 长文本处理优化（重叠窗口、句子边界、元数据携带、HTML 清理）

**Phase 3：创作方向** ✅ 已完成 (2026-06-22)
- [x] 接口规范定义（interfaces.py — 8 个接口 + 5 个数据结构）
- [x] 知识库管理（vault_manager.py — Obsidian 笔记读写/搜索/时间线）
- [x] 情节大纲生成（plot_generator.py — 4 个 AI Prompt）
- [x] 章节生成 + 质量检查（chapter_generator.py — AI + 规则双模式）
- [x] 章节保存、断点续写、小说合并（novel_logger.py）
- [x] 创作管线入口（create.py — 串联全流程）
- [x] 质量检测（quality_checker.py — 逻辑一致性、字数、重复、敏感词）
- [x] 格式转换（converter.py — EPUB/TXT/平台格式）
- [x] 商业化管理（commercial_manager.py — 收益估算、平台比较）

**Phase 4：体验优化** ✅ 已完成 (2026-06-24)
- [x] 人物去重增强（别名匹配 + AI 辅助判断）
- [x] 章节摘要合并（全书摘要生成）
- [x] 多本书管理（跨作品人物关联）— project_manager.py + VaultManager.list_books() + CLI 命令
- [x] 角色成长曲线 — character_growth.py（追踪人物状态变化，成长事件提取，阶段分析）
- [x] 输出格式转换增强 — converter.py + main.py/agent.py（EPUB/TXT/平台格式导出，交互式导出命令）
