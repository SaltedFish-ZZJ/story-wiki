# Story Wiki 开发日志

> 下次打开这个文件就知道：做到哪了、下一步干什么、怎么跑。

## 当前状态：v0.8.1（关系图谱增强）

```
功能: txt/epub/pdf 输入 → 自动分章 → 逐章AI分析（带上下文） → 合并去重 → Obsidian 笔记生成
新增: 进度条 + 缓存 + 增量分析 + 事件卡片 + 关系图谱
优化: 基于 DeepSeek 建议，支持《西游记》等超长文本（80万字+）的完整处理
新增: 知识库管理 + 情节生成 + 章节生成 + 日志记录（并行开发）
新增: 创作管线（create.py — 串联分析→知识库→大纲→逐章生成→合并）
新增: 质量检测 + 格式转换 + 商业化管理
新增: 关系图谱颜色区分（人物/事件/设定不同颜色）
修复: vault_manager 更新卡片时 color frontmatter 丢失
优化: graph.json 配置 colorGroups + 布局参数优化
新增: GRAPH_COLORS_GUIDE.md 图谱颜色使用指南
验证: 223 个测试全部通过 ✅
API: 小米 mimo-v2.5（token-plan API）
```

## 快速启动

```bash
cd D:\agent_workspace\story_wiki

# ═══ 分析模式 ═══

# 查看内存状态
python src/main.py --memory-status

# 单次分析（自动使用缓存）
python src/main.py --input story/红楼梦.txt --title "红楼梦"

# 禁用缓存（强制重新分析）
python src/main.py --input story/红楼梦.txt --title "红楼梦" --no-cache

# 清除缓存
python src/main.py --clear-cache

# 增量分析
python src/main.py --input data/input/xxx.txt --title "书名" --incremental

# 交互式
python src/agent.py

# ═══ 创作模式 ═══

# 从知识库创作小说（需先有分析结果）
python src/main.py --create --title "红楼梦" --chapters 5

# 只生成大纲预览
python src/main.py --create --title "红楼梦" --outline-only

# 断点续写
python src/main.py --create --title "红楼梦" --chapters 5 --resume

# 指定章节范围
python src/main.py --create --title "红楼梦" --chapter-start 1 --chapter-end 10

# ═══ 测试 ═══

# 运行全部测试（216 个）
python -m pytest tests/ -v

# 运行优化测试
python test_optimization.py
python test_deepseek_optimization.py

# ═══ 查看结果 ═══

# 用 Obsidian 打开 D:\Obsidian_Work\story_wiki
```

## 项目结构

```
story_wiki/
├── src/
│   ├── interfaces.py      ← 接口规范（8 接口 + 5 数据结构）
│   ├── config.py          ← 配置（API key、路径、参数、内存监控）
│   ├── utils.py           ← 工具函数（文件名处理、frontmatter、名称归一化）
│   │
│   │  ── 分析管线 ──
│   ├── extractor.py       ← 文本读取（txt/epub/pdf、流式读取、HTML 清理）
│   ├── splitter.py        ← 章节切分（按标题模式/按字数、重叠窗口、句子边界）
│   ├── analyzer.py        ← AI 分析核心 + 分章 prompt + 前文摘要
│   ├── pipeline.py        ← 分章分析管线（切分→逐章分析→合并去重+进度+缓存）
│   ├── generator.py       ← Obsidian .md 文件生成（增量写入、节点颜色）
│   │
│   │  ── 创作管线 ──
│   ├── vault_manager.py   ← 知识库管理（读取/解析 Obsidian 笔记）
│   ├── plot_generator.py  ← 情节大纲生成（4 个 AI Prompt）
│   ├── chapter_generator.py← 章节生成 + 质量检查（AI + 规则双模式）
│   ├── novel_logger.py    ← 章节保存、进度追踪、断点续写、小说合并
│   ├── create.py          ← 创作管线入口（串联 VM→PG→CG→NL）
│   ├── quality_checker.py ← 质量检测（逻辑一致性、字数、重复、敏感词）
│   ├── converter.py       ← 格式转换（EPUB/TXT/平台格式）
│   ├── commercial_manager.py← 商业化管理（收益估算、平台比较）
│   │
│   │  ── 入口 ──
│   ├── main.py            ← CLI 入口（分析模式 + 创作模式）
│   └── agent.py           ← 交互式分析（支持分章/缓存管理）
│
├── tests/                 ← 216 个测试函数
├── data/
│   ├── input/             ← 待分析文本放这里
│   ├── novels/            ← 生成的小说输出
│   └── state/cache/analysis/ ← 分析结果缓存（7天过期）
├── story/                 ← 原始文本文件（红楼梦、水浒传等）
├── .env                   ← API Key（git 不跟踪）
├── log.md                 ← 项目变更日志
└── AGENTS.md              ← AI Agent 指令
```

**Obsidian vault:** `D:\Obsidian_Work\story_wiki\`

## 版本历史

| 版本 | 日期 | 主要内容 |
|------|------|----------|
| v0.1.0 | 2026-06-20 | Phase 1 最小 Demo：AI 分析 + Obsidian 笔记生成 |
| v0.1.1 | 2026-06-20 | 1M 上下文支持 + 交互式分析 Agent |
| v0.2.0 | 2026-06-20 | 分章分析核心完成 |
| v0.2.1 | 2026-06-20 | epub/pdf 格式支持 |
| v0.3.0 | 2026-06-20 | 增量分析 |
| v0.4.0 | 2026-06-20 | 卡片优化（RPG 风格）+ 事件卡片 + 关系图谱 |
| v0.5.0 | 2026-06-22 | 体验优化：进度条 + 缓存 |
| v0.6.0 | 2026-06-22 | 长文本处理优化（基于 DeepSeek 建议） |
| v0.7.0 | 2026-06-22 | 并行开发 4 模块 + 关系图谱颜色区分 |
| v0.8.0 | 2026-06-22 | 创作管线端到端打通（create.py）+ 质量检测 + 格式转换 |
| v0.8.1 | 2026-06-23 | 关系图谱增强：colorGroups + 布局优化 + 修复 vault_manager bug |

## 已知问题

| 问题 | 状态 |
|------|------|
| 长文本分析内容偏少 | ✅ v0.2.0 分章处理已解决 |
| 只支持 .txt 格式 | ✅ v0.2.1 已支持 epub/pdf |
| 输出 token 限制 8192 | ✅ 已调整为可配置 |
| 分析无进度显示 | ✅ v0.5.0 已添加进度条 |
| 重复分析浪费时间 | ✅ v0.5.0 已添加缓存 |
| Bun 运行时崩溃 | ✅ v0.6.0 已优化内存使用 |
| 人物近似名重复 | 🔧 待修复（P2 优先级） |
| 章节摘要拼接过长 | 🔧 待优化（P2 优先级） |

## 技术备忘

- **API:** 小米 mimo-v2.5（`https://token-plan-cn.xiaomimimo.com`），OpenAI 兼容格式
- **API Key:** `.env` 文件，变量名 `STORY_WIKI_API_KEY`（tp- 开头）
- **Base URL:** `.env` 文件，变量名 `STORY_WIKI_BASE_URL`
- **模型名:** `.env` 文件，变量名 `STORY_WIKI_MODEL`（默认 `mimo-v2.5`）
- **编码容错:** txt 读取按 utf-8 → gbk → gb2312 → latin-1 顺序尝试
- **JSON 解析:** 三层容错（直接解析 → 提取 ```json``` → 提取 `{}`）
- **wikilink:** 人物关系用 `[[人名]]` 写在人物卡里，Graph View 自动识别
- **分章阈值:** 文本 > 5000 字自动启用分章（`CHAPTER_THRESHOLD`）
- **缓存机制:** 每章文本 md5 哈希作为缓存键，7天过期
- **进度显示:** `[进度] 20% (3/15) — 分析: 第2章 (23365字)`
- **内存监控:** 启动时自动显示系统和进程内存状态
- **大文件阈值:** >1MB 自动启用流式读取（`LARGE_FILE_THRESHOLD`）
- **重叠窗口:** 200 字重叠，保持跨块上下文连续性（`OVERLAP_SIZE`）
- **图谱颜色:** 人物=蓝色，事件=橙色，设定=绿色
- **接口规范:** `src/interfaces.py` 定义所有模块的接口规范
