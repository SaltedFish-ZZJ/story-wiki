# Changelog

## v0.13.8 (2026-10-19)

### 功能 — 打印 / 导出 PDF 报告（输出端最小闭环）

- 动机：知识库已有四种消费方式（Web 浏览 / Obsidian 卡片 / MCP 查询 / 创作导出），唯一缺口是「带走与分享」——无法给没装项目的人一份可读产物。选择最小方案：打印样式，而非新建导出模块
- 顶栏新增 🖨️ 按钮：进入作品页点击 → 打印前自动全量展开增量渲染内容（时间线滚动加载哨兵清空、折叠的人物/设定卡全部展开，约 20 行 JS），再唤起浏览器打印；Ctrl+P 同样生效（beforeprint 事件兜底）
- `@media print` 样式块：强制浅色主题（暗色下打印变量重置）、隐藏全部界面元素（顶栏/搜索/导航/状态条/光斑背景/按钮）、卡片与时间线行 `break-inside:avoid` 分页防截断
- 实测《平凡的世界》：print 媒体下界面元素全部隐藏、内容完整；574 张折叠卡全量展开；A4 PDF 生成 12.9MB（含图谱位图），零 console/page 错误
- 打印修复（用户实测反馈）：浏览器打印默认丢弃 CSS 背景，「章节事件密度」柱是纯 CSS 背景（color-mix 半透明）无边框无内容，背景一丢整根柱隐形——图谱（canvas 位图）与时间线（SVG fill）不走 CSS background 所以幸存。修复：打印块全局 `print-color-adjust:exact` 强制打印信息性背景，密度柱实色化（普通 #EDF3F3 / 峰值 #2B5D68，不依赖透明度合成）；验证时曾被柱体 150ms 的 background 过渡误导（emulate print 后立即读 computed 拿到过渡起点旧值），等待过渡后确认 54 柱全部实色可见

**测试结果：** 680 passed, 0 failed

## v0.13.7 (2026-10-19)

### 加固 — 因果链提取规则：从「可选」到「核心价值」（零 API 消耗验证）

- 动机：「按情节」视图的弧覆盖率取决于事件卡因果链，但内置分析 prompt 把 cause/effect 标注为「（可选）」，LLM 自然倾向不填——《平凡的世界》635 事件仅 11% 成弧
- 三处 prompt 对齐修复：整书/逐章 SYSTEM_PROMPT 的 cause/effect schema 描述与规则条目重写（「因果链是知识库的核心价值」，cause 填前置事件名、effect 填直接引发的事件名而非后果描述文字，开头性/孤立事件才填 []）；SKILL.md 同步对齐防止两边漂移
- 逐章模式明确跨章回填机制：本章 effect 引用的事件若发生在后续章节，由那一章的 cause 回填（上下文已注入前章已知事件名，原料本就齐全，纯 prompt 动力问题）
- 新增 4 个 prompt 质量测试：两套 SYSTEM_PROMPT 的因果链措辞断言、跨章已知事件注入断言、SKILL.md 与内置 prompt 措辞一致性断言
- **零 API 验证**：`--plan` 切章后由 Agent（本会话）按 SKILL.md 规则手工提取《以日为鉴》第 1-2 章 15 张事件卡（含跨章因果引用），`--ingest` 入库，15 张卡全部带因果字段且连通，串出 8 步主弧「泡沫巅峰疯狂 → 失落一代定型」（全书前两章主线）
- 认知修正：整书分析模式的旧卡并非「不填因果链」（实际 cause 20/23 非空），而是**引用名与卡名不一致导致断链**（如引用「科学立国战略」但卡名为「科学立国战略失败」）——「一字不差」规则同时解决填与准两个问题；存量断链卡不回改

**测试结果：** 675 passed, 0 failed

## v0.13.6 (2026-10-18)

### 功能 — 时间线「按情节」视图（最小 demo）

- 时间线新增「按章节 | 按情节」视图切换：情节视图用事件卡因果链（前置事件→本事件→后续影响）把事件串成情节弧 —— 一条因果链就是一个完整的「事」（起因→发展→高潮→结局），回应「没有章节的书按事情起伏高潮来区分」的需求
- 弧构建（纯前端、零 API）：同名卡去重 → 无前置的根事件沿后续影响链走（环保护）→ ≥2 事件成弧，弧名「首事件 → 尾事件」；不成弧的收进「其他事件（未成弧 N）」垫底组
- 弧线带复用：每弧一柱按事件数着色，峰值胶囊标注最长弧；「其他事件」组画灰色弱化柱、不参与峰值；弧内事件卡带 ①②③ 步骤徽标与「第N步」序号；点柱跳弧、点事件名开抽屉、人物圆点直达人物卡全链路复用
- 实测《平凡的世界》：「全部」筛选下 635 事件串出 27 条弧（如「少安尝试改革 → 福堂向上汇报 → 县革委紧急会议 → 改革尝试失败」），564 事件未成弧（因果链覆盖率约 11%，属上游分析质量问题）；章节视图 60 组零回归
- 已知边界：整书分析模式（如《以日为鉴》）因果链字段基本为空，情节视图下几乎全部进「其他事件」—— 提升覆盖率需写侧加固（分析 prompt 强化因果链要求）

**测试结果：** 650 passed, 0 failed

## v0.13.5 (2026-10-18)

### 修复 — 时间线章节分组：无号章标题误归「未标章」

- 根因：《以日为鉴》23 个事件全部有 chapter 值（DeepSeek 并未漏填），但整书分析模式下 AI 填写格式不统一 —— 部分事件只填章标题主体「日本硕博扩招一代」（丢了「第六章」前缀），而前端按「第X章」数字模式归组，解析不出章号的 12 个事件被误归「未标章」，时间线只显示 3 个组且信息失真
- 前端分组模型重构：数字章号归组 → 章节原串归组（key=AI 填写的 chapter 原文），排序规则 = 有号章在前按章号 → 无号章标题按首次出现序 → 「未标章」垫底；组显示名有号显示「第N章」、无号截断显示原标题
- 「本章/本回/同章」等相对引用无定位信息，归并到「未标章」（《平凡的世界》51 个「本章」事件正确归位）
- 弧线带同步重构：按组索引均分定位（不再按章号数值定位，空柱/占位柱消失），刻度只标有号章，峰值胶囊/选中态/跳组滚动全部按组工作；超长书段模式同步适配
- 实测三本书：《以日为鉴》3 组（第3章 10 / 第5章 1 / 日本硕博扩招一代 12，峰值胶囊正确）；《平凡的世界》60 组零回归；《以日为鉴Agent验证》单组正常；跳组展开、筛选联动零报错
- 遗留（后续数据质量加固）：整书分析 prompt 未定义 chapter 字段规范（AI 凭自觉填），源头治理需在 analyzer 注入章节清单或整书改逐章分析

**测试结果：** 650 passed, 0 failed

## v0.13.4 (2026-10-18)

### 功能 — Agent Skill：Agent 驱动分析模式（零 API key）

- 新增 `--plan` / `--ingest` CLI 模式（[src/commands/agent.py](src/commands/agent.py)）：把「LLM 分析」环节交给外部 Agent（WorkBuddy / Claude / Trae 等），项目退化为分章器 + 知识库 + 校验器，全程零 API 调用
- `--plan <file> --title X`：纯本地提取文本（txt/md/epub/pdf/docx）并切章，产出 `data/agent_runs/<书名>/manifest.json` + 逐章原文，作为 Agent 的任务清单
- `--ingest cards.json [--chapter 第N章] [--book-title X]`：接收 Agent 生成的卡片 JSON，宽松校验 + 兼容归一化（participants/related_*/cause/effect 兼容 {name} 对象与字符串两种形态、缺 name 实体跳过并警告），增量写入知识库（复用 `generate_vault_incremental`，同名卡更新、索引自动重建）
- 新增 `skills/story-wiki/SKILL.md`：Agent 操作说明书 —— 四步工作流、完整卡片 JSON Schema、提取规则（实体名一致性、跨章因果链格式）、常见问题
- 端到端验证：plan 切章 → 模拟 Agent 卡片 → ingest 写入 → Web API 可读（overview/timeline）→ 清理测试数据重建索引
- .gitignore 增加 `data/agent_runs/`（章节原文含版权内容）

**测试结果：** 650 passed, 0 failed

## v0.13.3 (2026-10-18)

### 功能 — MCP 读侧 Server

- 新增 `web/mcp_server.py`：把小说知识库以 MCP（Model Context Protocol）工具形式暴露给任意 MCP 客户端（Trae / Claude Desktop / WorkBuddy 等），stdio 传输，`python -m web.mcp_server` 启动
- 9 个只读工具，零 LLM 调用：`list_books`（书目+统计）、`get_overview`（摘要+核心人物）、`search`（FTS5 跨作品搜索含中文子串兜底）、`list_characters`（分组名单）、`get_character` / `get_event` / `get_setting`（卡片详情）、`get_timeline`（按章节分组时间线，支持重要度/人物过滤）、`get_graph`（关系图谱 nodes+edges）
- 复用 `web.app` 解析层（含内存缓存）与 `src.db` 搜索；错误路径（书/人物不存在、索引缺失）返回可读 JSON 而非抛异常
- 依赖声明：pyproject 新增 `mcp` 可选分组（`pip install -e .[mcp]`）
- 客户端接入：MCP 配置指向 `command: python, args: ["-m", "web.mcp_server"], cwd: <项目根>`；smoke test 实测 9 工具握手、搜索命中、图谱 154 节点/384 边

### 修复

- 前端新增 `chapterLabel()`：epub 章节标题混入大段正文时（如《以日为鉴》第五章），「第X章」开头的字段只显示章号，其余超 24 字截断；事件卡 meta 不再透出超长原文
- .gitignore 增加 `data/input/`（上传原文含版权内容，禁止入库）

**测试结果：** 650 passed, 0 failed

## v0.13.2 (2026-10-17)

### 界面 — Web 前端 v7 全面改版（杂志式设计）

- 前端整体重写为 prototypes/story-wiki-v7 定稿设计：米白/深色双主题（CSS 变量 + 🌙 切换记忆）、细网格背景、双光斑漂移动画、衬线标题的杂志式排版
- 首页重构：大标题 CTA + 拖拽上传框（txt/md/epub/pdf/docx）+ 作品墙卡片（每部作品显示人物/事件/设定统计与实体总数）
- 书内页改为单页长滚动四章：01 简介与速览（简介 + 高频关系 TOP5 + 核心人物 + 章节事件密度柱状图 + 设定分布）、02 全宽关系图谱（ECharts 力导向，v7 主题配色）、03 人物 × 时间线双栏（大事记 + 人物分组卡片）、04 设定与地点卡片网格；右侧悬浮锚点目录随滚动高亮
- 任务视图：五阶段进度（读取/分章/AI 分析/生成卡片/入库索引）+ 实时日志 + 完成直达知识库
- 顶栏全局搜索（FTS5 跨作品，`/` 快捷键，ESC 关闭）；卡片抽屉支持人物/事件/设定三类实体互相跳转
- 新增 `GET /api/books/{title}/settings` 设定列表接口；设置页与上传轮询逻辑完整保留（v0.13.1 全套功能不回归）
- 修复：设定卡名称误解析为 "---"（改用 `_extract_name` 处理 frontmatter 在前的卡片）；设定卡关联人物解析对齐真实节名「关联人物」；描述缺「描述」节时回退正文摘要
- 修复：FTS5 unicode61 分词器不按字切分中文，「少安」等子串查询零命中 —— `search_entities` FTS 零命中时回退 name LIKE 子串扫描（kind 过滤语义不变）
- 修复：关系图谱节点点击弹出空白 "undefined" 抽屉 —— 后端 graph 节点仅有 id 无 name，ECharts 连线正常但点击事件 params.name 为空串，请求 `/characters/` 被尾斜杠重定向到列表接口返回无人物字段的对象；前端节点补 `name: n.id` 并在 openEntity 加空名守卫
- 修复：点击时间线人物圆点遇「未建卡人物」只弹 toast（如《平凡的世界》的郝红梅 —— timeline 事件卡的参与人物引用了未生成人物卡的名字，人物接口 404）—— openEntity 人物分支增加聚合回退：从事件卡参与人物字段聚合该人物的全部出场事件，渲染「未建卡 · 事件聚合」降级抽屉（说明 + 参与事件 chips 可跳转事件卡），同一入口同时惠及图谱、搜索、设定卡关联人物的跳转；此修复对新书同样生效
- 03 章节时间线长书适配（无限滚动 + 弧线分段聚合）：章节组 ≤60 卷轴保持全量渲染不变；超长书（网文数百上千章）初始只渲染 50 组，滚动到底自动追加下一批（IntersectionObserver 哨兵 + host 级事件委托，追加行零重绑），点击弧线跳章时自动扩容渲染到目标章并居中；弧线超过 240 章时自动切换段聚合（每柱代表 N 章、恒定 ≤120 柱保证可点击，刻度/峰值胶囊/选中态同步按段显示），点击段柱跳到段内第一个有事件的章；短书与现有交互零回归（Playwright 以 mock 500 章/1472 事件验证：50→100→200 滚动追加、段柱跳章扩容 331 行、筛选切换自洽、零报错）
- 章节显示兜底：epub 章节标题可能混入大段正文（如《以日为鉴》第五章标题带 100+ 字推广文案）—— 新增 `chapterLabel()`：「第X章」开头的章节字段只显示章号，其余超 24 字截断加省略号；事件卡 meta 不再透出超长章节原文
- 新增测试 4 个（test_web_settings_list 3 / test_db_indexer 子串兜底 1）
- 布局与信息密度迭代：全屏下 01 简介区双栏改 `minmax(0,)` 修复左栏被密度柱挤扁；01 简介区改上下排版；03 改为横向章节时间线（横向轴 + 事件卡上下交替 + 参与人物首字圆点，重要性筛选）；人物/设定列表默认各显示 12 张（重要优先、设定按关联度排序），其余收进「展开全部」；图谱节点标签移至节点下方并加背景色描边，`hideOverlap` 防重叠；ECharts 改为本地内置（static/vendor）+ CDN 兜底，内网可用且 CDN 失败不再阻塞页面渲染
- 03 章节时间线二次迭代（横向轴 → 弧线带 + 竖向卷轴）：顶部全书事件弧线（SVG 柱状密度带，重要度筛选联动，峰值章胶囊标注，每 10/20 章刻度）点击柱子跳转并居中展开对应章节；下方竖向卷轴按章节列事件卡（最多 6 张，更多折叠计数），收起态显示前 2 个事件名预览，节点/柱子按事件密度四级着色，参与人物首字圆点点击直达人物卡；默认展开事件最多（优先有章节号）的章；Playwright 验证 54 柱/55 组、跳章、收起、筛选联动、事件/人物抽屉全链路零报错

**测试结果：** 650 passed, 0 failed

## v0.13.1 (2026-10-17)

### 功能 — Web 设置页：LLM 连接配置可视化

- 新增设置页（导航"设置"）：服务商预设下拉（小米 MiMo / DeepSeek / 自定义）自动填充地址与模型名，Key 输入框留空表示沿用已保存值
- 新增 `GET/POST /api/settings`（受鉴权保护）：读取（Key 打码）/ 保存（写回 .env 保留注释与其他键）配置，保存后热生效无需重启——同步更新 os.environ、config 模块常量及 analyzer/api_client/plot_generator/chapter_generator 等已加载模块的 `from config import` 绑定
- 新增 `POST /api/settings/test` 连接测试：以 `max_tokens=1` 最小补全验证连通性（与 `api_client.py` 一致拼 `/v1/chat/completions`），支持"先测再存"
- 设计约束：`set_llm_config` 持久化必须显式传 `env_path`，仅 Web 设置层落盘项目 `.env`；其他调用方（含测试）不传即只改运行时
- 新增测试 13 个（test_web_settings.py）：Key 打码、.env 写回/注释保留、消费模块热更新、鉴权 401→登录→200、连接测试（mock 网络）

**测试结果：** 646 passed, 0 failed

## v0.13.0 (2026-10-17)

### 功能 — SQLite 元数据层 + Web 上传分析 + 最小鉴权 + 部署产物

**P0 — SQLite 元数据层与全文检索：**
- 新增 `src/db.py`：document / entity / relation / event_time 四表 + FTS5 外部内容表（unicode61 分词），触发器同步，标准库 sqlite3 实现，WAL 模式
- 新增 `src/indexer.py`：扫描 vault md 卡片幂等入库（md_path 唯一键），两遍法解析人物关系 wikilink，事件按 章号*1000+序号 排序；CLI 支持 `--rebuild` / `--stats`
- 新增 `GET /api/search`：跨作品全文检索（人物/事件/设定过滤），中文短语查询防拆字误召回
- `generator.py`：`generate_vault` / `generate_vault_incremental` 生成结束后自动增量入库（失败仅告警，不影响生成）
- 实测：《平凡的世界》1,253 实体 + 关系/事件时间全部入库；重复执行幂等

**P0.5 — 可选依赖测试修正：**
- 17 个 EPUB 相关测试改用 `pytest.importorskip("ebooklib")`（原先裸装环境 fail，现 skip）
- 裸装 `.[test]` 环境：589 passed / 18 skipped / 0 failed

**P1 — Web 上传与后台分析：**
- 新增 `POST /api/documents`：上传 txt/md/epub/pdf/docx（100MB 上限，同名不覆盖），docx 用 python-docx 解析段落+表格（新增 `office` extra）
- 新增 `POST /api/analyze` + `GET /api/tasks/{id}`：threading 单并发后台任务，进度分档（提取 10% / 章节 15-85% / 生成 90%），失败回滚不留半成品
- `extractor.py`：新增 `.md` / `.docx` 格式支持
- 前端新增"上传分析"页：拖拽上传 + 进度条轮询 + 完成自动刷新

**P2 — 最小权限：**
- 新增 `web/auth.py`：STORY_WIKI_PASSWORD 环境变量单用户密码，HMAC-SHA256 签名 session cookie（httpOnly，7 天），未设密码则鉴权关闭
- `POST /api/documents`、`POST /api/analyze` 挂鉴权依赖；GET 接口保持公开；新增 `/login` / `/logout` 登录页

**P3 — 部署产物：**
- 新增 `Dockerfile`（python:3.13-slim，非 root，HEALTHCHECK）+ `.dockerignore` + `docker-compose.yml`（data/vault 挂载卷持久化）
- 新增 `start.bat` / `start.sh` 一键启动脚本
- 新增 `docs/07_部署/部署指南.md`（脚本/Compose/手动三种方式 + Nginx 示例 + 运维 FAQ）

**P4 — 文档：**
- README 补充 Web 功能说明、技术架构、部署入口
- API 参考手册新增 Web API 章节（全部 12 个接口）

**新增测试：** 44 个（test_db_indexer 18 / test_web_upload 14 / test_web_auth 12）

**测试结果：** 633 passed, 0 failed

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
