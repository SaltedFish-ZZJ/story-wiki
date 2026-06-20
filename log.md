# Story Wiki 项目日志

记录项目的重要变更和里程碑。

---

## 2026-06-20 — v0.3.0 增量分析功能

### 新增功能
- ✅ 增量分析核心逻辑 — pipeline.py
  - `detect_existing_analysis()` 检测已有分析结果
  - `_load_incremental_state()`/_save_incremental_state()` 状态管理
  - `_read_existing_cards()` 从 vault 读取已有卡片
  - `build_initial_context_for_incremental()` 构建初始上下文
  - `analyze_chaptered_incremental()` 增量分析主函数
  - `_filter_chapters()` 章节筛选（支持 start_chapter/end_chapter）

### 使用场景
- 长篇小说分批分析：第 1 次分析 1-20 章，第 2 次分析 21-40 章，追加而非覆盖
- 断点续传：分析中断后可从断点继续
- 避免重复：已分析章节自动跳过

### CLI 参数
- `--incremental` — 启用增量分析模式
- `--start-chapter N` — 从第 N 章开始分析
- `--end-chapter N` — 分析到第 N 章结束

### 使用示例
```bash
# 首次分析（全量）
python src/main.py --input data/input/红楼梦.txt --title "红楼梦"

# 增量追加新章节
python src/main.py --input data/input/红楼梦_后50章.txt --title "红楼梦" --incremental

# 指定章节范围
python src/main.py --input data/input/红楼梦.txt --title "红楼梦" --incremental --start-chapter 51 --end-chapter 100
```

### 新增文件
- `docs/plans/incremental_analysis_plan.md` — 增量分析实现计划文档
- `tests/test_incremental.py` — 单元测试（8 个测试全部通过）

### 修改文件
- `src/pipeline.py` — 增量分析核心逻辑
- `src/main.py` — 添加 --incremental CLI 参数
- `src/generator.py` — 增量写入功能
- `src/config.py` — 添加增量分析配置
- `TODO.md` — 标记增量分析为已完成

---

## 2026-06-20 — v0.2.1 P0 Bug 修复 + epub/pdf 支持

### P0 Bug 修复
- ✅ 章节排序修复 — `_extract_chapter_number()` 提取标题中的数字按数值排序，解决 "第10章" 排在 "第1章" 前面的问题（支持中文数字和阿拉伯数字）
- ✅ 空章节过滤 — `MIN_CHAPTER_CHARS = 200`，碎片章节（如"第二部分"4字）自动跳过，节省 API 调用
- ✅ API 重试 — `_call_deepseek_with_prompt()` 增加指数退避重试（最多 3 次），处理 ConnectionError 和 429/5xx 错误

### P1 格式支持
- ✅ epub 支持 — `extractor.py` 新增 `_read_epub()`，用 ebooklib 按 spine 顺序提取纯文本（需 `pip install ebooklib`）
- ✅ pdf 支持 — `extractor.py` 新增 `_read_pdf()`，用 pymupdf 逐页提取文本（需 `pip install pymupdf`）
- ✅ 优雅降级 — 未安装依赖时给出明确安装提示，不崩溃

### 代码质量
- 重构 splitter.py — 拆分 `_try_pattern()`、`_extract_chapter_at()`、`_parse_chinese_number()`、`_should_flush()`、`_flush_block()`、`_append_para()` 等辅助函数，降低认知复杂度

### 新增/修改文件
- `src/splitter.py` — 章节排序 + 空章节过滤 + 函数拆分
- `src/analyzer.py` — API 重试机制
- `src/extractor.py` — epub/pdf 格式支持

---

## 2026-06-20 — v0.2.0 Phase 2 分章分析核心完成

### 里程碑
- ✅ 章节切分器（splitter.py）— 支持"第X章/第X回"等多种模式，无标记时按字数 fallback
- ✅ 分章分析管线（pipeline.py）— 切分→逐章分析（带上下文）→合并去重
- ✅ analyzer.py 新增分章 prompt + `analyze_chapter()` 函数
- ✅ main.py / agent.py 自动判断长文本走分章流程
- ✅ 新增 `--no-split` / `--chunk-size` CLI 参数

### 测试结果（《富爸爸穷爸爸》12.4万字）

| 指标 | Phase 1 单次分析 | Phase 2 分章分析 | 提升 |
|------|-----------------|-----------------|------|
| 人物 | 6 | 63 | 10.5x |
| 设定 | 3 | 63 | 21x |
| 生成文件 | ~15 | 125 | — |

分 15 章逐章分析，每章携带已知人物/设定上下文，合并去重后生成完整笔记。

### 技术方案
- **分章策略**：按章节标题正则匹配（第X章/第X回/Chapter X 等），无标记时按 5000 字分块
- **上下文传递**：每章分析时，在 prompt 中附加已知人物/设定摘要，AI 只提取新内容
- **合并去重**：同名人物合并（取更长字段、合并关系），同名设定取更长描述
- **自动阈值**：文本 > 5000 字自动启用分章，可通过 `--no-split` 禁用

### API 配置变更
- 切换到小米 mimo API（`https://token-plan-cn.xiaomimimo.com`），模型 `mimo-v2.5`
- `.env` 新增 `STORY_WIKI_BASE_URL` 和 `STORY_WIKI_MODEL` 配置项

### 新增/修改文件
- `src/splitter.py` — 章节切分模块（新建）
- `src/pipeline.py` — 分章分析管线（新建）
- `src/analyzer.py` — 新增分章分析函数
- `src/config.py` — 新增分章参数
- `src/main.py` — 集成分章流程 + CLI 参数
- `src/agent.py` — 交互式支持分章

---

## 2026-06-20 — 长文本实战测试

### 测试内容
- 书名：富爸爸穷爸爸（12.4 万字）
- 来源：txt 文件，内容完整（有 CIP 数据、结束语）
- 类型：非虚构类（财务教育）

### 测试结果
- ✅ 12.4 万字一次性处理成功，未超限
- ✅ 提取 6 个人物（罗伯特·清崎、富爸爸、穷爸爸、迈克、莎伦·莱希特、马丁夫人）
- ✅ 提取 3 个设定（老鼠赛跑、快车道、现金流游戏）
- ✅ 人物关系正确（师徒、父子等）
- ✅ 摘要准确概括全书核心思想

### 发现的问题
- ⚠️ 内容偏少 — 12 万字只提取 6 人物 3 设定
- 原因：AI 一次性处理长文本时"注意力衰减"，中间内容容易遗漏
- 原因：输出 token 限制（8192），空间不够列出所有细节
- 原因：非虚构类核心人物确实不多，但财务概念应提取更多

### 结论
Phase 1 "跑通"目标达成。长文本处理需要 Phase 2 分章方案。

---

## 2026-06-20 — vault 路径迁移

### 变更
- `D:\Obsidian_Work\myself wiki` → `D:\Obsidian_Work\myself_wiki`（改用下划线）
- story_wiki vault 移入：`D:\Obsidian_Work\myself_wiki\story_wiki\`
- 更新了 config.py / .env.example / docs 中的所有路径引用

### 目录结构
```
D:\Obsidian_Work\myself_wiki\
├── personal\          ← 个人 wiki
└── story_wiki\        ← 小说 wiki vault
    ├── 红楼梦片段\    ← 测试数据
    └── 富爸爸穷爸爸\  ← 长文本测试
```

---

## 2026-06-20 — v0.1.1 配置优化 + 交互式 Agent

### 变更
- ✅ 上下文限制提升：8000字 → 40万字（适配 DeepSeek 1M 上下文）
- ✅ 输出 token 提升：4096 → 8192
- ✅ 新增交互式分析 Agent（src/agent.py）
- ✅ 支持文件路径输入和直接文本粘贴
- ✅ 内置 /help /list /vault /quit 命令

### 使用方式
```bash
# 单次分析
python src/main.py --input data/input/xxx.txt --title "作品名"

# 交互式 Agent
python src/agent.py
```

---

## 2026-06-20 — v0.1.0 Phase 1 最小 Demo 完成

### 里程碑
- ✅ 项目文档骨架搭建完成（AGENTS.md、README.md、docs/）
- ✅ 核心代码实现：extractor → analyzer → generator
- ✅ 首次端到端测试通过（红楼梦片段 8人物4设定）
- ✅ Obsidian Graph View 正确显示人物关系

### 技术决策
- HTTP 库：requests（httpx 与 Python 3.13 有兼容问题）
- AI 模型：DeepSeek API（deepseek-chat）
- API 配置：.env 文件 + 环境变量 fallback

### 文件结构
```
src/
├── config.py      ← 配置管理、.env 加载
├── extractor.py   ← 文本读取（txt）
├── analyzer.py    ← DeepSeek API 调用 + JSON 解析
├── generator.py   ← Obsidian Markdown 生成
├── main.py        ← CLI 入口（单次分析）
└── agent.py       ← 交互式分析 Agent
```
