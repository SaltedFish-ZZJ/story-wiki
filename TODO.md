# Story Wiki 开发待办

> 基于 v0.4.0 测试结果和 Phase 2/3 规划，按优先级排列。
> 最后更新：2026-06-20

---

## P0 — 当前版本问题修复

### 章节排序混乱 ✅ 已修复 (2026-06-20)
- **问题**：splitter 按正则匹配位置排序，但 `第10章` 排在 `第1章` 前面（字符串排序）
- **方案**：提取章节标题中的数字，按数值排序而非字符串排序
- **影响**：上下文传递顺序不对，可能导致前几章分析不准确
- **文件**：`src/splitter.py` — `_extract_chapter_number()` + `_try_pattern()`

### API 限流/网络重试 ✅ 已修复 (2026-06-20)
- **问题**：分章分析时偶发 `ConnectionError`，当前直接跳过该章
- **方案**：增加重试机制（指数退避，最多 3 次），失败后等待 5 秒再试
- **影响**：减少因网络波动导致的章节丢失
- **文件**：`src/analyzer.py` — `_call_deepseek_with_prompt()`

### 空章节过滤 ✅ 已修复 (2026-06-20)
- **问题**：`第二部分`（2字）、`第三部分`（4字）等碎片章节被送去分析，浪费 API 调用
- **方案**：splitter 增加最小章节字数阈值（< 200 字视为碎片，跳过）
- **文件**：`src/splitter.py` — `MIN_CHAPTER_CHARS` + `_extract_chapter_at()`

---

## P1 — 功能增强

### epub 格式支持 ✅ 已完成 (2026-06-20)
- **依赖**：`pip install ebooklib`
- **方案**：`extractor.py` 新增 `_read_epub()` 函数，用 ebooklib 提取纯文本
- **注意**：epub 章节天然有结构，可直接按章节分析，不需要 splitter
- **文件**：`src/extractor.py`

### pdf 格式支持 ✅ 已完成 (2026-06-20)
- **依赖**：`pip install pymupdf`
- **方案**：`extractor.py` 新增 `_read_pdf()` 函数，用 pymupdf 逐页提取文本
- **注意**：PDF 排版复杂（表格、图片、脚注），需要基础清理
- **文件**：`src/extractor.py`

### 增量分析 ✅ 已完成 (2026-06-20)
- **需求**：新章节追加到已有笔记，不覆盖旧结果
- **方案**：
  1. `pipeline.py` — 新增 `detect_existing_analysis()` 检测已有分析结果
  2. `pipeline.py` — 新增 `analyze_chaptered_incremental()` 增量分析主函数
  3. `generator.py` — 新增 `generate_vault_incremental()` 增量写入逻辑
  4. `main.py` — 新增 `--incremental` CLI 参数
- **使用场景**：
  - 长篇小说分批分析：第 1 次分析 1-20 章，第 2 次分析 21-40 章，追加而非覆盖
  - 断点续传：分析中断后可从断点继续
  - 避免重复：已分析章节自动跳过
- **文件**：`src/pipeline.py`, `src/generator.py`, `src/main.py`, `src/config.py`
- **需求**：新章节追加到已有笔记，不覆盖旧结果
- **方案**：
  1. 分析前读取 vault 中已有的人物/设定列表作为初始上下文
  2. 分析后合并到已有文件（更新而非覆盖）
- **文件**：`src/pipeline.py`, `src/generator.py`

### 输出 token 动态调整
- **需求**：简单作品用低 token，复杂作品（人物多）自动提高
- **方案**：根据已知人物数量动态设置 `max_tokens`（如 人物>20 则 max_tokens=16384）
- **文件**：`src/config.py`, `src/analyzer.py`

---

## P2 — 体验优化

### 分析进度条
- **需求**：长文本分章分析时显示进度（当前只打印章节号）
- **方案**：用 `tqdm` 或简单百分比显示，如 `[3/15] 20% — 第2章 (23365字)`
- **文件**：`src/pipeline.py`

### 分析结果缓存
- **需求**：避免重复分析同一文本（网络失败后重试很慢）
- **方案**：对每章文本做 md5 哈希，缓存到 `data/state/cache/`，命中则直接读取
- **文件**：`src/analyzer.py`

### 人物去重优化
- **问题**：当前只按 name 精确匹配去重，`富爸爸` 和 `富爸爸（罗伯特·清崎的父亲）` 会被当作两个人
- **方案**：增加别名匹配 + AI 辅助判断是否同一人
- **文件**：`src/pipeline.py`

### 章节摘要合并
- **问题**：当前 summary 拼接各章摘要，太长且有重复
- **方案**：最后一章分析完后，用一次 API 调用生成全书摘要
- **文件**：`src/pipeline.py`

---

## P3 — 新功能

### 事件卡片 + 时间线
- **需求**：从文本中提取关键事件，生成事件卡片和时间线视图
- **数据模型**：
  ```yaml
  type: event
  date: 1994年
  characters: [罗伯特·清崎, 莎伦·莱希特]
  description: 47岁退休
  ```
- **Obsidian 集成**：用 Dataview 插件做时间线查询
- **文件**：新建 `src/event_extractor.py`, 修改 `src/generator.py`

### 多本书管理
- **需求**：跨作品人物关联（如"罗伯特·清崎"出现在多本书中）
- **方案**：vault 根目录维护全局人物索引，同名人物自动关联
- **文件**：`src/generator.py`

### 事件提取 + 关系图谱 ✅ 已完成 (2026-06-20)
- **需求**：从文本中提取关键事件，建立 人物↔事件、事件↔事件、事件↔人物 的关联，并导出关系图谱
- **数据模型**：
  ```yaml
  type: event
  name: 事件名（如"宝黛初见"）
  time: 时间描述（如"1994年"、null）
  participants: [人物名1, 人物名2]
  location: 地点名（可选）
  description: 一句话描述
  cause: [前置事件名1]
  chapter: 章节名（自动填充）
  ```
- **实施步骤**：
  1. `src/analyzer.py` — SYSTEM_PROMPT + CHAPTER_SYSTEM_PROMPT 增加 events 数组
  2. `src/pipeline.py` — 新增 `merge_events()`，修改 `_build_chapter_context()` 传递已知事件
  3. `src/generator.py` — 新增 `_write_event_card()`，生成 `events/` 目录
  4. `src/generator.py` — `_write_book_index()` 中嵌入 Mermaid 关系图谱
  5. `src/generator.py` — `_write_book_index()` 中嵌入时间线（Dataview + Mermaid timeline 降级）
  6. `src/config.py` — 新增 `EVENT_DIR` 路径常量
  7. 更新文档：`数据模型.md`、`AI分析模块.md`
- **Obsidian 集成**：事件卡片支持 Dataview 时间线查询，_index.md 嵌入 Mermaid graph
- **文件**：`src/analyzer.py`, `src/pipeline.py`, `src/generator.py`, `src/config.py`

---

## P4 — 远期（Phase 3 创作方向）

- [ ] 种子输入 → AI 提问协作 → 世界观构建
- [ ] 人物卡 + 设定 → AI 驱动人物推演
- [ ] 推演结果 → 章节化小说输出

---

## v0.5.0 规划方向

### 体验优化（优先）
- **分析进度条** — 长文本分章分析时显示进度百分比
- **分析结果缓存** — 避免重复分析同一文本，网络失败后重试更快
- **人物去重增强** — 增加别名匹配 + AI 辅助判断是否同一人
- **章节摘要合并** — 最后一章分析完后用一次 API 调用生成全书摘要

### 功能增强
- **语录增强** — 支持手动编辑语录，AI 提取更多金句
- **时间线可视化** — 事件卡片添加 Mermaid timeline
- **角色成长曲线** — 追踪人物状态变化（如孙悟空：石猴→美猴王→齐天大圣→斗战胜佛）
- **批量导出** — 支持导出为 PDF/EPUB

### 多本书管理
- **全局人物索引** — vault 根目录维护全局人物索引
- **跨作品人物关联** — 同名人物自动关联（如"罗伯特·清崎"出现在多本书中）
- **作品对比分析** — 对比不同作品的人物/设定差异

---

## 推荐开发顺序

```
✅ 已完成:
  P0 章节排序修复 → P0 空章节过滤 → P0 API 重试
  P1 epub/pdf 支持 → P1 增量分析
  P3 事件卡片 + 关系图谱
  v0.4.0 卡片优化（RPG 风格）— 状态栏/高光时刻/语录/关系子图
  ↓
下一步（v0.5.0 建议优先做）:
  P2 进度条 → P2 缓存 → P2 去重优化
  ↓
新功能:
  P3 多本书管理 → P3 语录增强 → P3 角色成长曲线
```
