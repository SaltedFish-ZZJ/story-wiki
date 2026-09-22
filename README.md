# Story Wiki

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

- **分析**：从小说/历史/传记中提取人物、关系、设定标签，生成 Obsidian 笔记
- **可视化**：Obsidian Graph View 查看人物关系网络（节点颜色区分角色）
- **角色成长曲线**：追踪人物状态变化，生成成长事件、阶段分析与趋势报告
- **创作**：基于知识库驱动 AI 续写新章节（情节生成 + 章节生成 + 日志记录）
- **增量分析**：跳过已处理章节，支持追加新内容，不必每次从头跑
- **多格式导出**：EPUB / TXT / 平台格式，支持批量转换

## 规模

| 项 | 数量 |
|---|---|
| Python 模块 | 32 个（含 6 个 CLI 子命令模块） |
| 代码行数 | 源码 13,165 行 + 测试 10,541 行 |
| 单元测试 | 589 个（pytest，全部通过） |
| 实测文本 | 80 万字长篇小说（约 80 万非空白字符） |
| 模型接入 | 任意 OpenAI 兼容接口（默认小米 MiMo，可换 DeepSeek） |
| Web 界面 | Flask 前端，1,691 行 |


## 快速开始

```bash
# 1. 安装项目与常用格式支持
python -m pip install -e ".[formats]"

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

### 可选安装

```bash
# Web UI
python -m pip install -e ".[web]"

# 开发与测试（包含全部可选能力）
python -m pip install -e ".[formats,web,test]"
```

安装完成后可用 `story-wiki --help` 或 `python src/main.py --help` 检查 CLI。

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
├── src/           ← 源代码
├── vault/         ← Obsidian vault 输出
├── data/          ← 输入文本和中间数据
│   ├── input/     ← 待分析文本放这里
│   └── state/     ← 分析状态和缓存
│       └── cache/ ← 分析结果缓存
├── story/         ← 原始文本文件（红楼梦、水浒传等）
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
