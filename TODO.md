# Story Wiki 代码优化 TODO

> 更新日期：2026-06-25
> 当前版本：v0.12.1

---

## 📋 已完成优化

✅ 第一轮优化 — 架构重构（api_client / merger / commands 拆分 / 样板消除）
✅ 第二轮优化 — 日志统一（converter / vault_manager / novel_logger）
✅ 第三轮优化 — 异常处理细化 + 非CLI模块日志统一 + 文档同步
✅ 角色标签改进 — prompt 规则细化 + 合并逻辑优化 + 人物概览分组显示
✅ Graph View 分色 + 子文件夹重构（v0.12.0）
✅ 平凡的世界全量分析实战验证（v0.12.1）— 82万字 → 1251个笔记
✅ Bug 修复：`_setting_link()` list 类型防御（v0.12.1）
✅ 输出模块优化 — 关系去重/top限制、wikilink路径修复、tags清洗、list防御、_index.md分组显示
- 测试：587 passed, 0 failed

---

## 📌 后续待开发（按优先级）

### P1 — Web UI 最小 Demo
- **框架**: FastAPI + 原生 HTML/CSS/JS + ECharts (CDN)
- **数据源**: 直接读 Obsidian .md 文件（解析 frontmatter + wikilinks），不新建数据库
- **美术风格**: 极简学术风 + 苹果设计哲学（白底、SF Pro、圆角卡片、毛玻璃导航、0.2s动效）
- **MVP 范围**（4 个页面，只读浏览）:
  1. **概览页** — 作品统计（人物/事件/设定数量）+ 核心人物卡片
  2. **人物列表页** — 搜索 + 分组显示 + 点击展开详情侧栏
  3. **关系图谱页** — ECharts force-directed graph，节点分色，点击高亮子图
  4. **时间线页** — 事件按时间/重要性排列，支持人物筛选
- **目录结构**: `web/app.py` + `web/parsers.py` + `web/static/style.css` + `web/templates/index.html`
- **接口**:
  - `GET /` — SPA 入口
  - `GET /api/books` — 作品列表
  - `GET /api/books/{title}/overview` — 概览数据
  - `GET /api/books/{title}/characters` — 人物列表
  - `GET /api/books/{title}/characters/{name}` — 人物详情
  - `GET /api/books/{title}/graph` — 关系图 nodes/edges
  - `GET /api/books/{title}/timeline` — 时间线数据
- **排除**: 不做登录、不做编辑、不做移动端、不做在线分析
- **工作量**: 中（2-3 天）

### P2 — 日志文件输出
- **文件**: `src/logging_setup.py`
- **改动**: logger 同时输出到控制台和文件（`data/logs/story_wiki.log`），按日期轮转
- **工作量**: 小（改 1 个文件）

### P2 — DOCX 格式支持
- **文件**: `src/extractor.py`
- **改动**: 新增 `.docx` 读取（`python-docx` 库），编码容错链增加 docx 分支
- **工作量**: 小（1 天）

### P2 — Graph View 性能优化
- **问题**: 平凡的世界 1251 个节点在 Obsidian Graph View 卡顿
- **方案**: 过滤低关联节点（边数 < 2 的不生成卡片）或分层索引（_index.md 只链接主要人物）
- **工作量**: 中（1-2 天）

### P3 — SQLite 索引层
- **文件**: `src/index_db.py`（新增）+ CLI 参数集成
- **接口**: `--sync-index`（同步）、`--search`（搜索）、`--stats`（统计）
- **工作量**: 中（5-6 天）

### P3 — Web UI
- **框架**: Flask / FastAPI
- **工作量**: 大（2-3 周）

### P3 — Obsidian 图谱插件
- **改动**: graph-colors 从 CSS snippets 升级为正式 Obsidian 插件
- **工作量**: 中（1 周）

---

## 📊 验证清单

- [x] 全量测试: 587 passed, 0 failed
- [x] 内部模块无 print 泄漏
- [x] 无 `except Exception` 宽泛捕获
- [x] role_tags 合并逻辑正确
- [x] 人物概览分组显示正确
- [x] Graph View 分色正确（主角红色/配角蓝色/路人灰色）
- [x] 子文件夹结构正确
- [x] 旧笔记删除 + 从缓存重新生成成功
- [x] 平凡的世界全量分析通过（82万字 → 1251 笔记）
- [x] `_setting_link` list 类型防御修复
