# Story Wiki

[![CI](https://github.com/SaltedFish-ZZJ/story-wiki/actions/workflows/ci.yml/badge.svg)](https://github.com/SaltedFish-ZZJ/story-wiki/actions/workflows/ci.yml)

## 它解决什么问题

把一本 80 万字的长篇小说交给 AI，它会忘掉前面的角色。分块处理时上下文被切断，前后块里的同一个人被当成两个人，关系网越读越乱。

Story Wiki 把长文本拆解成可查询、可续写的结构化知识库。

## 怎么解决

长文本必须分块（超出模型上下文窗口），但简单分块会切断跨块的实体关联。本项目的做法：

- **重叠窗口分块** —— 相邻块共享 200 字符的重叠区，保持上下文连续性
- **前文摘要传递** —— 每块分析前，把上一块已识别的人物/设定摘要（上限 500 字）注入为上下文，实现跨块实体对齐

两者叠加，人物关系在整本书范围内不丢。核心代码在 `src/splitter.py` 与 `src/pipeline.py`。

> 这两项长文本优化参考了 DeepSeek 的技术建议，由本项目实现、调试并验证。

## 功能

- **MCP 读侧服务**：9 个纯本地只读工具（书目/跨作品搜索/人物/事件/设定/时间线/关系图谱），FastMCP stdio 接入 Claude Desktop 等任意 MCP 客户端，查询全程零 LLM 调用
- **Agent Skill 工作流**：`--plan` 本地切章产 manifest → LLM Agent 按 SKILL.md 逐章提取卡片 → `--ingest` 宽松校验增量写库并自动刷新 Web，分析过程从黑盒 API 变成可编排的 Agent 任务
- **分析**：从小说/历史/传记中提取人物、关系、设定标签，生成 Obsidian 笔记
- **可视化**：Obsidian Graph View 查看人物关系网络（节点颜色区分角色）
- **Web 一体化**：浏览器上传 txt/md/epub/pdf/docx → 后台异步分析 → 进度条轮询，全程免命令行
- **时间线双视图**：「按章节」（弧线带 + 长书无限滚动）|「按情节」（因果链串情节弧：起因→发展→高潮→结局），前端纯读侧实现，无章节标记的书自动退化为分块/硬切分兜底
- **全文检索**：SQLite FTS5 跨作品检索人物/事件/设定，生成新书自动入库
- **权限控制**：环境变量单用户密码 + HMAC 签名会话（可选，不设置即开放）
- **角色成长曲线**：追踪人物状态变化，生成成长事件、阶段分析与趋势报告
- **创作**：基于知识库驱动 AI 续写新章节（情节生成 + 章节生成 + 日志记录）
- **增量分析**：跳过已处理章节，支持追加新内容，不必每次从头跑
- **多格式导出**：EPUB / TXT / 平台格式，支持批量转换

## 技术架构

```
输入(txt/md/epub/pdf/docx)
  → extractor 文本提取          src/extractor.py
  → splitter 重叠窗口分章       src/splitter.py（200字重叠 + 前文摘要传递）
  → pipeline 逐章 AI 分析       src/pipeline.py（跨块实体对齐 + 缓存）
  → generator 生成 md 卡片      src/generator.py（人物/事件/设定/索引/时间线）
  → indexer 自动入库            src/indexer.py → data/wiki.db (SQLite+FTS5)

Web 层（FastAPI）               web/app.py
  ├─ 只读 API：作品/人物/关系图/时间线（直接读 md 卡片）
  ├─ 检索 API：GET /api/search（FTS5）
  ├─ 写 API：上传/任务（POST，受 STORY_WIKI_PASSWORD 鉴权）
  └─ 后台任务：threading 单并发队列   web/tasks.py

Agent 生态
  ├─ MCP 读侧服务（FastMCP stdio）   web/mcp_server.py（9 个只读工具，零 LLM 调用）
  └─ Agent Skill 工作流             skills/story-wiki/SKILL.md
                                    + src/commands/agent.py（--plan / --ingest）
```

依赖极简：核心只用 `psutil` + `requests` + 标准库（sqlite3/hashlib/hmac/threading）；
可选 extra：`formats`（epub/pdf）、`office`（docx）、`web`（FastAPI）、`mcp`（MCP server）。

## 规模

| 项 | 数量 |
|---|---|
| Python 模块 | 40 个（含 6 个 CLI 子命令模块） |
| 代码行数 | 源码 12,800+ 行 + 测试 9,100+ 行 |
| 单元测试 | 678 个（pytest，全部通过，含 MCP stdio 协议层冒烟） |
| 实测文本 | 80 万字长篇小说（平凡的世界全三部，1,253 实体入库） |
| 模型接入 | 任意 OpenAI 兼容接口（默认小米 MiMo，可换 DeepSeek） |
| Web 界面 | FastAPI + 原生 JS，19 个 API 接口 |
| 元数据层 | SQLite + FTS5（document/entity/relation/event_time） |


## 快速开始

```powershell
# Windows 一键启动（自动建 venv / 装依赖 / 建索引 / 起服务）
.\start.bat
# 浏览器打开 http://127.0.0.1:8000，"上传分析"页拖入文档即可
```

```bash
# Linux / macOS
./start.sh

# 或 Docker Compose（服务器部署）
cp .env.example .env   # 填入 API Key
docker compose up -d --build
```

命令行方式（分析功能）：

```bash
# 1. 安装项目与常用格式支持
python -m pip install -e ".[formats,office]"

# 2. 配置 API（复制 .env.example 为 .env 并填入配置）
Copy-Item .env.example .env

# 3. 查看内存状态
python src/main.py --memory-status

# 4. 运行分析（长文本自动分章）
python src/main.py --input data/input/your_novel.txt --title "书名"

# 5. 交互式分析
python src/agent.py

# 6. 用 Obsidian 打开 vault 目录，查看 Graph View
```

### Agent 生态（MCP + Agent Skill）

不配置 API Key 也能用 Agent 驱动：本地 CLI 只负责切章、校验与写库，LLM 由外部 Agent（Claude Desktop 等 MCP 客户端）提供，两者解耦。

**MCP 读侧服务**（把已有知识库接入 MCP 客户端查询）：

```bash
python -m pip install -e ".[mcp]"
```

在 MCP 客户端（如 Claude Desktop）中注册：

```json
{ "mcpServers": { "story-wiki": { "command": "python", "args": ["<项目路径>/web/mcp_server.py"] } } }
```

注册后可直接问：「帮我查《平凡的世界》里孙少安参与了哪些事件」「跨作品搜一下所有跟水库有关的设定」——9 个工具覆盖书目/搜索/人物/事件/设定/时间线/关系图谱，全程本地读取、零 API 消耗。

**Agent Skill 工作流**（分析新书，LLM 只做提取）：

```bash
# 1. 纯本地切章，产出 manifest.json + 章节原文（data/agent_runs/书名/）
python src/main.py --plan data/input/书名.txt --title "书名"

# 2. 把 chapters/*.txt 按 skills/story-wiki/SKILL.md 的 JSON 规范交给 LLM Agent 逐章提取

# 3. 宽松校验 + 增量写库 + 自动通知 Web 刷新
python src/main.py --ingest result.json --book-title "书名"
```

### 可选安装

```bash
# Web UI（上传/检索/鉴权）
python -m pip install -e ".[web]"

# docx 支持
python -m pip install -e ".[office]"

# 开发与测试（包含全部可选能力）
python -m pip install -e ".[formats,office,web,mcp,test]"
```

安装完成后可用 `story-wiki --help` 或 `python src/main.py --help` 检查 CLI。

完整部署（Nginx/环境变量/运维 FAQ）见 [docs/07_部署/部署指南.md](docs/07_部署/部署指南.md)。

## 高级功能

### 关系图谱颜色配置（v0.7.0）

支持为不同类型的节点设置不同颜色：

```bash
# 1. 确认 CSS 文件存在
ls -la "D:\Obsidian_Work\story_wiki\.obsidian\snippets\graph-colors.css"

# 2. 在 Obsidian 中启用
# 设置 → 外观 → CSS 代码片段 → 启用 graph-colors

# 3. 重新生成卡片
python src/main.py --input story/红楼梦.txt --title "红楼梦" --no-cache
```

**颜色配置：**
- 人物节点：🔵 蓝色
- 事件节点：🟠 橙色
- 设定节点：🟢 绿色

详见 [docs/12_用户手册/GRAPH_COLORS_SETUP.md](docs/12_用户手册/GRAPH_COLORS_SETUP.md)

### 小说 Agent（v0.7.0）

基于知识库驱动 AI 创作新小说：

```python
from src.vault_manager import VaultManager
from src.plot_generator import PlotGenerator
from src.chapter_generator import ChapterGenerator
from src.novel_logger import NovelLogger

# 1. 读取知识库
vault_manager = VaultManager({"vault_path": "..."})
knowledge_base = vault_manager.load_all_cards()

# 2. 生成情节大纲
plot_generator = PlotGenerator({"api_key": "..."})
outline = plot_generator.generate_outline("红楼梦续集", knowledge_base)

# 3. 生成章节内容
chapter_generator = ChapterGenerator({"api_key": "..."})
chapter = chapter_generator.generate_chapter(1, outline, context)

# 4. 保存日志
novel_logger = NovelLogger({"log_path": "..."})
novel_logger.save_chapter(1, chapter)
```

详见 [docs/02_功能设计/PARALLEL_DEV_SUMMARY.md](docs/02_功能设计/PARALLEL_DEV_SUMMARY.md)

### 长文本优化（v0.6.0）

基于 DeepSeek 专业建议，对长文本处理进行了全面优化：

```bash
# 查看内存状态
python src/main.py --memory-status

# 分析大型古典小说（自动应用优化）
python src/main.py --input story/红楼梦.txt --title "红楼梦"
python src/main.py --input story/水浒传.txt --title "水浒传"
python src/main.py --input story/西游记.txt --title "西游记"
python src/main.py --input story/三国演义.txt --title "三国演义"
```

**核心优化：**
- ✅ 重叠窗口分块算法（200 字重叠）
- ✅ 句子边界断点（句号、问号、叹号）
- ✅ 元数据携带机制（chunk_index, total_chunks）
- ✅ 前文摘要传递机制（context_before_summary）
- ✅ HTML 标签清理（支持网页复制内容）
- ✅ 非正文内容识别（移除版权、序言等）

**性能提升：**
- 读取速度：100-200 倍（2.4MB 文件仅需 0.01 秒）
- 内存占用：降低 30-50%（从 80-120MB 降至 20-40MB）

详见 [docs/02_功能设计/FINAL_SUMMARY.md](docs/02_功能设计/FINAL_SUMMARY.md)

### 增量分析
```bash
# 首次分析
python src/main.py --input data/input/红楼梦.txt --title "红楼梦"

# 增量追加新章节
python src/main.py --input data/input/红楼梦_后50章.txt --title "红楼梦" --incremental

# 指定章节范围
python src/main.py --input data/input/红楼梦.txt --title "红楼梦" --incremental --start-chapter 51 --end-chapter 100
```

### 缓存管理
```bash
# 正常分析（自动使用缓存）
python src/main.py --input data/input/西游记.txt --title "西游记"

# 禁用缓存（强制重新分析）
python src/main.py --input data/input/西游记.txt --title "西游记" --no-cache

# 清除所有缓存
python src/main.py --clear-cache
```

### 交互式 Agent 命令
```
/help    — 显示帮助
/list    — 列出已分析的作品
/vault   — 打开 vault 目录
/cache   — 清除分析缓存
/growth  — 分析角色成长曲线
/export  — 导出小说为各种格式
/quit    — 退出
```

### 角色成长曲线（v0.8.0）

追踪人物在故事中的状态变化，生成成长分析报告：

```bash
# 分析指定角色的成长曲线
python src/main.py --growth-analysis "林黛玉" --title "红楼梦"

# 分析所有主要角色
python src/main.py --growth-analysis --title "红楼梦"

# 查看角色成长事件列表
python src/main.py --growth-curve "贾宝玉" --title "红楼梦"

# 生成图表数据（JSON）
python src/main.py --growth-chart "薛宝钗" --title "红楼梦"

# 从分析结果中提取成长事件
python src/main.py --extract-growth --input analysis.json --title "红楼梦"
```

**交互式命令：**
```
/growth [作品名] [人物名]  — 分析角色成长曲线
```

### 多格式导出（v0.8.0）

将已生成的小说导出为多种格式：

```bash
# 导出为 TXT 格式
python src/main.py --export-txt --title "红楼梦"

# 导出为 EPUB 格式
python src/main.py --export-epub --title "红楼梦"

# 批量导出所有格式（EPUB/TXT/平台格式）
python src/main.py --batch-export --title "红楼梦"
```

**交互式命令：**
```
/export [作品名] [格式]  — 导出小说
  格式选项: epub, txt, md, all (默认 all)
```

## 项目结构

```
story_wiki/
├── src/           ← 源代码（分析管线 + db.py 元数据层 + indexer.py 索引器）
├── web/           ← FastAPI 后端 + 前端（app.py / tasks.py / auth.py / templates）
├── data/          ← 输入文本和中间数据
│   ├── input/     ← 待分析文本放这里（Web 上传也落在这里）
│   ├── output/    ← 分析产物：人物/事件/设定 md 卡片（Obsidian 可直接打开当 Vault）
│   ├── wiki.db    ← SQLite 元数据库（FTS5 全文索引）
│   └── state/     ← 分析状态和缓存
│       └── cache/ ← 分析结果缓存
├── story/         ← 原始文本文件（红楼梦、水浒传等）
├── Dockerfile / docker-compose.yml / start.bat / start.sh
└── docs/          ← 项目文档
```

## 文档

- [docs/02_功能设计/FINAL_SUMMARY.md](docs/02_功能设计/FINAL_SUMMARY.md) — 最终总结（推荐阅读）
- [docs/02_功能设计/GETTING_STARTED.md](docs/02_功能设计/GETTING_STARTED.md) — 快速上手指南
- [docs/02_功能设计/PARALLEL_DEV_SUMMARY.md](docs/02_功能设计/PARALLEL_DEV_SUMMARY.md) — 并行开发总结
- [docs/plans/PROJECT_MASTER_PLAN.md](docs/plans/PROJECT_MASTER_PLAN.md) — 项目总体规划
- [docs/12_用户手册/GRAPH_COLORS_SETUP.md](docs/12_用户手册/GRAPH_COLORS_SETUP.md) — 关系图谱颜色快速设置
- [docs/12_用户手册/GRAPH_COLORS_GUIDE.md](docs/12_用户手册/GRAPH_COLORS_GUIDE.md) — 关系图谱颜色使用指南
- [docs/12_用户手册/DEEPSEEK_IMPLEMENTATION.md](docs/12_用户手册/DEEPSEEK_IMPLEMENTATION.md) — DeepSeek 建议实施总结
- [docs/12_用户手册/OPTIMIZATION_SUMMARY.md](docs/12_用户手册/OPTIMIZATION_SUMMARY.md) — 基础优化总结
- [docs/12_用户手册/README_OPTIMIZATION.md](docs/12_用户手册/README_OPTIMIZATION.md) — 完整使用说明

## 详细文档

见 [docs/索引.md](docs/索引.md)
