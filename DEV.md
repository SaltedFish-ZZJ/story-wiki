# Story Wiki 开发日志

> 下次打开这个文件就知道：做到哪了、下一步干什么、怎么跑。

## 当前状态：v0.12.1（平凡的世界实战验证 + Bug 修复）

```
功能完整: txt/epub/pdf → 分章 → AI分析 → Obsidian笔记 → 关系图谱
创作完整: 知识库 → 大纲 → 逐章生成 → 质量检查 → 断点续写 → 多格式导出
代码质量: 三轮优化（架构重构 + 日志统一 + 异常处理细化）
新增: 角色标签准确性改进 + Graph View 分色 + 子文件夹结构重构
测试: 587 passed, 0 failed
API: 小米 mimo-v2.5（token-plan-cn.xiaomimimo.com）
最近验证: 平凡的世界（82万字/107章 → 1251个笔记文件）
```

## 子文件夹结构（v0.12.0 新增）

```
characters/主要人物/   ← 主角/女主/男主/反派（红色节点）
characters/次要人物/   ← 配角/导师/伙伴/BOSS/隐藏角色（蓝色节点）
characters/其他人物/   ← 其余（灰色节点）
settings/地点/         ← 地点/地名/城市/国家（绿色节点）
settings/组织/         ← 组织/公司/势力/团体（紫色节点）
settings/概念/         ← 其他（青色节点）
events/重大事件/       ← importance=高（深橙色节点）
events/一般事件/       ← importance=中或低（橙色节点）
```

## 下一步方向（待讨论/待开发）

| 方向 | 优先级 | 工作量 | 说明 |
|------|--------|--------|------|
| ~~**启动时 .env 校验**~~ | ~~P1~~ | ✅ 已完成 | v0.12.0 已实现 |
| **日志文件输出** | P2 | 小 | logger 同时输出到文件 |
| **DOCX 格式支持** | P2 | 1 天 | python-docx 读取 |
| **Graph View 性能优化** | P2 | 中 | 大作品（1000+节点）卡顿，需过滤低关联节点或分层索引 |
| **SQLite 索引层** | P3 | 5-6 天 | 查询加速，只读索引 |
| **Web UI** | P3 | 2-3 周 | Flask/FastAPI 可视化界面 |
| **Obsidian 图谱插件** | P3 | 1 周 | CSS snippets → 正式插件 |

### SQLite 索引层设计思路（如需开发）

- **定位**：Obsidian Vault 的"只读查询镜像"，不替换现有文件结构
- **Schema**：characters / settings / events / relationships 四张表
- **同步**：手动 `--sync-index` 触发，从 Markdown 解析写入 SQLite
- **查询**：搜索/统计/时间线走 SQLite，文件读取仍走 Obsidian
- **核心文件**：`src/index_db.py`（新增）+ CLI 参数集成
- **向后兼容**：现有功能完全不受影响

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

# 运行全部测试（587 个）
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
│   ├── config.py          ← 配置（API key、路径、参数、平台规则）
│   ├── utils.py           ← 工具函数（文件名处理、frontmatter、名称归一化）
│   ├── api_client.py      ← API 调用层（DeepSeek/OpenAI 兼容接口，v0.9.0 新增）
│   │
│   │  ── 分析管线 ──
│   ├── extractor.py       ← 文本读取（txt/epub/pdf、流式读取、HTML 清理）
│   ├── splitter.py        ← 章节切分（按标题模式/按字数、重叠窗口、句子边界）
│   ├── analyzer.py        ← AI 分析核心 + 分章 prompt + 前文摘要
│   ├── pipeline.py        ← 分章分析管线（切分→逐章分析→合并去重+进度+缓存）
│   ├── merger.py          ← 分析结果合并去重（v0.9.0 从 pipeline.py 抽取）
│   ├── generator.py       ← Obsidian .md 文件生成（增量写入、节点颜色）
│   │
│   │  ── 创作管线 ──
│   ├── vault_manager.py   ← 知识库管理（读取/解析 Obsidian 笔记）
│   ├── plot_generator.py  ← 情节大纲生成（委托 api_client）
│   ├── chapter_generator.py← 章节生成 + 质量检查
│   ├── novel_logger.py    ← 章节保存、进度追踪、断点续写、小说合并
│   ├── create.py          ← 创作管线入口（串联 VM→PG→CG→NL）
│   ├── quality_checker.py ← 质量检测（逻辑一致性、字数、重复、敏感词）
│   ├── converter.py       ← 格式转换（EPUB/TXT/平台格式，平台规则从 config.py 读取）
│   ├── commercial_manager.py← 商业化管理（收益估算、平台比较）
│   │
│   │  ── 增强功能 ──
│   ├── character_growth.py← 角色成长曲线（追踪 + Mermaid 可视化）
│   ├── project_manager.py ← 多作品管理（跨作品搜索、统计）
│   │
│   │  ── CLI（v0.9.0 拆分） ──
│   ├── main.py            ← CLI 入口（参数解析 + 调度，~116 行）
│   ├── agent.py           ← 交互式分析（支持分章/缓存管理）
│   └── commands/
│       ├── analysis.py    ← 分析管线命令
│       ├── growth.py      ← 成长曲线命令
│       ├── project.py     ← 项目管理命令
│       ├── export.py      ← 格式导出命令
│       └── create.py      ← 创作模式命令
│
├── tests/                 ← 516 个测试（全部通过）
├── data/
│   ├── input/             ← 待分析文本放这里
│   ├── novels/            ← 生成的小说输出
│   └── state/cache/analysis/ ← 分析结果缓存（7天过期）
├── story/                 ← 原始文本文件（红楼梦、水浒传等）
├── .env                   ← API Key（git 不跟踪）
├── CHANGELOG.md           ← 项目变更日志
├── AGENTS.md              ← AI Agent 指令
├── TODO.md                ← 优化待办（当前已完成）
└── docs/                  ← 完整文档体系
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
| v0.8.2 | 2026-06-23 | 角色成长曲线 + 多格式导出增强 + 集成测试 |
| v0.9.0 | 2026-06-24 | 第一轮优化：API 层独立、main.py 拆分、merger 抽取、样板消除 |
| v0.10.0 | 2026-06-24 | 第二/三轮优化：日志统一 + 异常处理细化 + 测试修复 |
| v0.11.0 | 2026-06-24 | 角色标签改进：prompt 规则细化 + 合并逻辑优化 + 人物概览分组显示 |

## 已知问题

| 问题 | 状态 |
|------|------|
| 长文本分析内容偏少 | ✅ v0.2.0 分章处理已解决 |
| 只支持 .txt 格式 | ✅ v0.2.1 已支持 epub/pdf |
| 输出 token 限制 8192 | ✅ 已调整为可配置 |
| 分析无进度显示 | ✅ v0.5.0 已添加进度条 |
| 重复分析浪费时间 | ✅ v0.5.0 已添加缓存 |
| 代码架构耦合 | ✅ v0.9.0 API 层独立 + main.py 拆分 |
| 内部日志不统一 | ✅ v0.10.0 全部统一为 logger |
| 异常处理过于宽泛 | ✅ v0.10.0 38处改为具体异常类型 |

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
