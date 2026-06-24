# Changelog

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
- 更新 AGENTS.md、NEXT_STEPS.md

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
