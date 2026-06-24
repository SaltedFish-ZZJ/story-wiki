# Story Wiki 项目变更日志

> 按时间顺序记录每次功能开发和重要变更
> 格式：日期 + 变更内容 + 影响范围

---

## 2026-06-23 — Phase 4 多本书管理（完成）

### 变更内容

**代码质量修复（4项）：**
1. 修复 `chapter_generator.py` 硬编码 `total_chapters=12` → 改为 `total_chapters: int = None`
2. 修复 `plot_generator.py` `.get() or default` 吞掉 falsy 值 → 改为 `.get(key, default) or default`
3. 处理 `create.py` 未使用的 `seed` 参数 → 已移除
4. 删除 `plot_generator.py` 重复的 `_parse_response` 方法

**多本书管理功能：**
1. `vault_manager.py` — 新增 `list_books()` 方法，扫描 Vault 下所有作品目录
2. `project_manager.py` — 新建跨作品管理模块，包含：
   - `list_books()` — 列出所有作品及统计
   - `search_cross_book(keyword)` — 跨作品关键词搜索
   - `find_similar_characters()` — 跨作品人物相似度匹配（4级策略：精确→别名→子串→属性）
   - `get_book_summary(book_title)` — 单本书详细摘要
   - `get_cross_book_timeline()` — 跨作品时间线合并
3. `main.py` — 新增4个CLI命令：
   - `--list-books` — 列出所有作品
   - `--book-info <作品名>` — 显示单本书摘要
   - `--cross-search <关键词>` — 跨作品搜索
   - `--similar-characters` — 查找相似人物
4. `tests/test_project_manager.py` — 新增25个测试

### 测试结果
- 测试总数：219 → 244（+25）
- 全部通过：244/244

### 影响范围
- 新增文件：`src/project_manager.py`, `tests/test_project_manager.py`
- 修改文件：`src/vault_manager.py`, `src/main.py`, `AGENTS.md`

---

## 2026-06-22 — Phase 3 创作管线 + 商业化模块

### 变更内容
- 接口规范定义（interfaces.py）
- 知识库管理（vault_manager.py）
- 情节大纲生成（plot_generator.py）
- 章节生成 + 质量检查（chapter_generator.py）
- 章节保存、断点续写、小说合并（novel_logger.py）
- 创作管线入口（create.py）
- 质量检测（quality_checker.py）
- 格式转换（converter.py）
- 商业化管理（commercial_manager.py）

### 测试结果
- 测试总数：219
- 全部通过

---

## 2026-06-22 — Phase 2 扩展功能

### 变更内容
- 章节切分器（splitter.py）
- 逐章分析 + 上下文传递（pipeline.py + analyzer.py）
- 全局合并去重
- epub/pdf 格式支持
- 事件卡片 + 时间线 + 关系图谱
- 增量分析
- 分析进度条 + 结果缓存
- 长文本处理优化

---

## 2026-06-20 — Phase 1 最小 Demo

### 变更内容
- 项目文档骨架、Vault 结构搭建
- 文本读取模块（txt/epub/pdf）
- AI 分析 prompt + API 调用
- Obsidian 笔记生成 + Graph View 验证

---

## 变更统计

| 日期 | 阶段 | 新增文件 | 修改文件 | 测试数 |
|------|------|----------|----------|--------|
| 2026-06-23 | Phase 4 多本书管理 | 2 | 3 | 244 |
| 2026-06-22 | Phase 3 创作管线 | 9 | - | 219 |
| 2026-06-22 | Phase 2 扩展功能 | 6 | 2 | 219 |
| 2026-06-20 | Phase 1 最小 Demo | 5 | - | - |
