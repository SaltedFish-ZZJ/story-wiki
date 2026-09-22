# Changelog

## v0.12.1 (2026-06-25)

### 实战验证 — 平凡的世界全量分析

**平凡的世界分析结果：**
- 输入：823,216 字 / 107 章（路遥，全三部）
- API：小米 mimo-v2.5（token-plan-cn.xiaomimimo.com）
- 输出：1,251 个 Obsidian 笔记文件
  - 人物：182 人（主要 13 / 次要 111 / 其他 58）
  - 事件：633 个（重大 366 / 一般 267）
  - 设定：434 个（地点 313 / 组织 93 / 概念 28）
- 5 章解析失败（第 4/42/90/106/109/161 章）被跳过，不影响整体结果

**Bug 修复 — generator.py `_setting_link` TypeError：**
- 问题：AI 返回 `location` 为 `list` 类型时，`_setting_link()` 对 `list` 做 `dict.get()` 抛出 `TypeError: unhashable type: 'list'`
- 修复：`_setting_link()` 增加 `isinstance(name, list)` 防御，递归展开为多个 wikilink

**配置更新：**
- 创建 `.env` 文件，配置小米 API（key + base_url + model）
- `pyproject.toml` 中 `pyproject.toml` 版本号未更新（保持 0.8.0，后续统一）

**测试结果：** 587 passed, 0 failed

## v0.12.0 (2026-06-24)

### 功能 — Graph View 分色 + 子文件夹结构重构

**generator.py — Graph View 分色：**
- 新增 `_get_character_color()` / `_get_setting_color()` / `_get_event_color()` 分色函数
- 人物按 role_tags 分色：主角(红 #E74C3C) / 配角(蓝 #4A90E2) / 路人(灰 #999999)
- 事件按 importance 分色：重大(深橙 #E67E22) / 一般(橙 #F5A623) / 细节(浅橙 #F9CA24)
- 设定按 type 分色：地点(绿 #7ED321) / 组织(紫 #9B59B6) / 概念(青 #1ABC9C)
- 3 处 `color:` 硬编码改为条件函数调用

**generator.py — 子文件夹结构：**
- 新增 `_get_character_subfolder()` / `_get_setting_subfolder()` / `_get_event_subfolder()` 分类函数
- 新增 `_build_entity_maps()` 构建 name→子文件夹映射表
- 新增 `_char_link()` / `_setting_link()` / `_event_link()` wikilink 生成函数
- `generate_vault()` / `generate_vault_incremental()` 创建子文件夹并传入映射表
- ~20 处 wikilink 从 `[[characters/{name}]]` 改为 `[[characters/{子文件夹}/{name}]]`

**vault_manager.py — 递归搜索支持：**
- 新增 `_find_card()` 方法：先查根目录（兼容旧结构），再 rglob 递归搜索
- `load_character` / `load_setting` / `load_event` 改用 `_find_card()`
- `_load_cards_from_dir()` 改用 `rglob("*.md")` 支持子文件夹
- `list_books()` 统计文件数改用 `rglob()`
- `update_*` 方法改用 `_find_card()` 检查存在性

**CSS + Obsidian 配置：**
- `graph-colors.css` 从 3 条规则扩展为 12 条（含旧版兼容 + 悬停效果）
- `graph.json` 新增主要人物/次要人物路径颜色组

**子文件夹规则：**
```
characters/主要人物/   ← 主角/女主/男主/反派
characters/次要人物/   ← 配角/导师/伙伴/BOSS/隐藏角色
characters/其他人物/   ← 其余
settings/地点/         ← 地点/地名/城市/国家
settings/组织/         ← 组织/公司/势力/团体
settings/概念/         ← 其他
events/重大事件/       ← importance=高
events/一般事件/       ← importance=中或低
```

**新增测试：** `tests/test_graph_colors.py`（48 个测试）
- `TestCharacterColor`：14 个测试
- `TestSettingColor`：9 个测试
- `TestEventColor`：5 个测试
- `TestCharacterSubfolder` / `TestSettingSubfolder` / `TestEventSubfolder`：10 个测试
- `TestBuildEntityMaps`：2 个测试
- `TestWikilinkHelpers`：6 个测试

**富爸爸穷爸爸验证：** 从缓存重新生成成功，子文件夹结构正确（主要人物2人/次要人物32人/其他人物71人）

**测试结果：** 357 passed, 0 failed（含 48 个新增测试）

## v0.11.0 (2026-06-24)

### 功能 — 角色标签（role_tags）准确性改进

**analyzer.py — prompt 规则细化（2 处）：**
- 全文分析 prompt 和分章分析 prompt 中 role_tags 规则从 1 行扩展为 8 个标签的详细判断标准
- 新增判断依据：出场频率 × 叙事权重 × 与核心冲突的关系
- 强调"不要把所有人物都标为主角"，每人物只选 1-2 个最贴切的标签

**merger.py — role_tags 合并逻辑优化：**
- 新增 `_merge_role_tags()` 函数：合并时取权重最高的标签（最多 2 个），而非简单追加
- 新增 `_ROLE_TAG_WEIGHTS` 权重表：主角(10) > 反派(9) > BOSS(8) > 隐藏角色(7) > 导师(6) > 伙伴(5) > 配角(4) > 路人(1)
- `_merge_single_character` 调用 `_merge_role_tags`，避免"主角被后续章节的配角覆盖"问题

**generator.py — 人物概览分组显示：**
- 新增 `_build_character_list_grouped()` 函数，`_write_book_index` 中人物按角色分组：
  - 🔴 核心人物（主角/女主/男主/反派）
  - 🟡 重要配角（配角/导师/伙伴/BOSS/隐藏角色）
  - ⚪ 其他人物（无标签或路人）
- 每个人物行显示角色标签（代码格式）和身份描述

**新增测试：** `tests/test_role_tags.py`（23 个测试）
- `TestMergeRoleTags`：11 个测试（空值、权重排序、去重、混合标签）
- `TestMergeCharacterRoleTags`：5 个测试（分章合并场景）
- `TestBuildCharacterListGrouped`：7 个测试（分组逻辑、空值、标签显示）

**测试结果：** 539 passed, 0 failed

---

## v0.10.0 (2026-06-24)

### 优化 — 第三轮（异常处理 + 日志统一）

**异常处理细化（38 处）：**
- `except Exception` → 具体异常类型（`RuntimeError`/`ValueError`/`OSError`/`KeyError`/`TypeError` 等）
- 涉及文件：api_client.py、config.py、pipeline.py、converter.py、vault_manager.py、quality_checker.py、novel_logger.py、create.py、project_manager.py、chapter_generator.py、character_growth.py、agent.py、commands/analysis.py、commands/growth.py

**非 CLI 模块日志统一（31 处）：**
- quality_checker.py：1 处
- project_manager.py：3 处
- character_growth.py：5 处
- chapter_generator.py：2 处
- generator.py：3 处
- extractor.py：8 处
- splitter.py：9 处

**测试修复：**
- test_dedup_optimization.py：mock side_effect 从 `Exception` 改为 `RuntimeError` 适配新异常类型

**测试结果：** 516 passed, 0 failed

---

## v0.9.0 (2026-06-24)

### 优化 — 第一轮（架构重构）
- **API 调用层独立**：从 `analyzer.py` 抽离出 `api_client.py`，消除 4 个模块对 analyzer 私有函数的依赖
- **质量检查修复**：`create.py` 质量检查从"摆设"变为有实际行为，新增 `--strict-quality` 参数
- **日志统一**：`pipeline.py`、`vault_manager.py` 约 24 处 `print()` → `logger`
- **样板代码消除**：`quality_checker.py`、`converter.py`、`novel_logger.py`、`plot_generator.py` 的 if/elif 分发改为 ACTIONS 字典 + getattr 分发
- **main.py 拆分**：647 行 → 116 行，新建 `src/commands/` 目录（analysis/growth/project/export/create）
- **合并逻辑抽取**：`pipeline.py` 中 ~180 行合并函数抽取到 `merger.py`
- **plot_generator.py 简化**：60+ 行独立 HTTP 调用代码替换为委托 `call_api`
- **平台规则集中管理**：`PLATFORM_RULES` 和 `SUPPORTED_PLATFORMS` 从 converter.py 移入 config.py
- **测试修复**：修复所有 mock 路径（_call_deepseek_with_prompt → call_api），516 测试全部通过

### 优化 — 第二轮（日志统一）
- **converter.py**：18 处 `print()` → `logger.info()` / `logger.warning()`
- **novel_logger.py**：6 处 `print()` → `logger.info()` / `logger.warning()`
- **vault_manager.py**：4 处 `print()` → `logger.warning()`
- 测试验证：441 passed, 0 failed

### 清理
- 删除冗余文件：`NEXT_STEPS.md`（与 TODO.md 重复）、`log.md`（与 CHANGELOG.md 重复）
- 修复 DEV.md、CHANGELOG.md、PROJECT_MASTER_PLAN.md 中对已删文件的引用

### 新增文件
- `src/api_client.py` — API 调用层
- `src/merger.py` — 合并逻辑
- `src/commands/__init__.py`
- `src/commands/analysis.py` — 分析管线命令
- `src/commands/growth.py` — 成长曲线命令
- `src/commands/project.py` — 项目管理命令
- `src/commands/export.py` — 格式导出命令
- `src/commands/create.py` — 创作模式命令

## v0.8.2 (2026-06-23)

### 新增
- **角色成长曲线** (`character_growth.py`)：追踪人物状态随章节变化，支持 AI 分析、成长阶段划分、Mermaid 可视化
- **多格式导出增强**：converter 模块大幅扩展，支持 EPUB/TXT/Markdown/平台格式批量导出
- **导出集成测试** (`test_integration_export.py`)
- **成长曲线集成测试** (`test_integration_growth.py`)
- **converter 增强测试** (`test_converter_enhanced.py`)

### 改进
- agent 模块：新增 `/growth`、`/export` 交互式命令
- interfaces 模块：新增 `GrowthEvent`、`CharacterGrowthCurve` 数据接口
- vault_manager：支持成长曲线数据写入
- main.py：新增 `--growth-analysis`、`--export-txt`、`--export-epub`、`--batch-export` 命令行参数

### 文档
- 更新 README.md：新增角色成长曲线和多格式导出使用说明
- 更新 AGENTS.md、TODO.md

## v0.8.1 (2026-06-22)

### 新增
- 关系图谱增强：节点颜色区分（人物/事件/设定）
- Obsidian CSS snippets 支持

## v0.8.0 (2026-06-21)

### 新增
- 角色成长曲线分析功能
- 多格式导出（EPUB/TXT/平台格式）
- 批量导出支持

## v0.7.0 (2026-06-20)

### 新增
- 小说 Agent：基于知识库驱动 AI 创作新小说
- 情节大纲生成、章节内容生成、日志记录

## v0.6.0 (2026-06-19)

### 优化
- 长文本处理优化（基于 DeepSeek 建议）
- 重叠窗口分块算法、句子边界断点
- 内存占用降低 30-50%

## v0.4.0 (2026-06-18)

### 新增
- 卡片 RPG 风格优化

## v0.3.0 (2026-06-17)

### 新增
- 增量分析功能
- 分析结果缓存
