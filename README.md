# Story Wiki

AI 驱动的故事知识库系统。

## 功能

- **分析**：输入任意文字材料（小说/历史事件/传记），AI 自动提取人物、设定、关系，生成 Obsidian 笔记
- **可视化**：利用 Obsidian Graph View 查看人物关系网络（支持节点颜色区分）
- **创作**：基于知识库驱动 AI 创作新小说（情节生成 + 章节生成 + 日志记录）
- **体验优化**：分析进度条、结果缓存、增量分析
- **长文本优化**：基于 DeepSeek 建议，支持《西游记》等超长文本（80万字+）的完整处理

## 快速开始

```bash
# 1. 安装依赖
pip install requests psutil

# 2. 配置 API（复制 .env.example 为 .env 并填入配置）
cp .env.example .env

# 3. 查看内存状态
python src/main.py --memory-status

# 4. 运行分析（长文本自动分章）
python src/main.py --input data/input/your_novel.txt --title "书名"

# 5. 交互式分析
python src/agent.py

# 6. 用 Obsidian 打开 vault 目录，查看 Graph View
```

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
/quit    — 退出
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
