---
name: story-wiki
description: 用你自己的模型分析小说并构建知识库（人物/事件/设定卡片 + 时间线 + 关系图谱 + 全文搜索），全程无需配置任何 LLM API key。适用于用户要求"分析这本小说"、"生成人物卡片"、"构建故事知识库"等任务。
---

# Story Wiki — Agent 驱动模式

把小说变成可查询的知识库。你（Agent）负责「读小说、提取实体」这一环，
项目负责切章、写卡片文件、建 FTS 索引。**全程零 API 调用、零费用。**

所有命令在项目根目录执行（下称 `<root>`，即本 SKILL.md 所在项目的根目录）：

```
cd <root>
python -m src.main --plan <小说文件> --title <书名>
```

## 工作流总览

```
1. --plan 切章        → 得到 manifest.json（章节清单）+ 每章原文 .txt
2. 你逐章阅读并提取   → 按「卡片 JSON Schema」写出 cards-NNN.json
3. --ingest 写入库    → 生成 Obsidian 卡片 + 自动建索引（增量，可分批）
4. 完成               → Web 界面 / MCP 工具即可查询
```

## 第 1 步：切章

```bash
python -m src.main --plan "data/input/书名.epub" --title "书名"
```

- 支持 `.txt .md .epub .pdf .docx`，纯本地处理
- 输出打印 `任务清单: <root>/data/agent_runs/<书名>/manifest.json`
- 读 manifest：`chapters[]` 每项含 `num`（章号）、`title`、`file`（章节原文绝对路径）、`chars`（字数）

## 第 2 步：逐章提取实体（这是你的核心工作）

逐个读章节原文文件，按下面的 Schema 产出卡片 JSON。
**建议每 3-5 章攒一个批次文件**（如 `cards-001-005.json`），减少 ingest 次数。

### 卡片 JSON Schema（单批次文件）

```json
{
  "title": "书名（与 --plan 的 --title 一致）",
  "summary": "一句话概括本批次覆盖的剧情",
  "characters": [
    {
      "name": "人名（必填，用文中最常用的称呼，别名放 aliases）",
      "aliases": ["别名", "昵称"],
      "gender": "男/女/未知",
      "identity": "一句话身份（如'双水村贫苦青年农民'）",
      "status": "活跃/死亡/离场 等",
      "importance": "主角/重要配角/配角/龙套",
      "description": "2-3 句：性格 + 处境 + 目标",
      "quotes": ["原文中的代表性语录，最多 3 条，没有就 []"],
      "relationships": [
        {"target": "对方人名（字符串，不是对象）", "type": "父子/恋人/敌对/朋友/主仆 等简洁词"}
      ],
      "related_settings": ["关联设定名（字符串数组，如所属组织、居住地）"]
    }
  ],
  "settings": [
    {
      "name": "设定名（必填，地点/组织/概念/体系）",
      "type": "地点/组织/概念/体系",
      "importance": "核心/重要/普通",
      "description": "2-3 句说明",
      "related_characters": ["相关人名（字符串数组）"],
      "related_settings": ["相关其他设定名（字符串数组）"]
    }
  ],
  "events": [
    {
      "name": "事件名（必填，4-8 字概括，如'宝黛初见'）",
      "time": "时间（从文本推断：'某年春天'/'第X章'，不要 null）",
      "chapter": "章节归属（如'第3章'；若调用 ingest 时传了 --chapter 可省略）",
      "participants": ["参与人物名（字符串数组，必须是人物卡或后续会出现的人物）"],
      "location": "发生地点（引用设定名）",
      "description": "一句话概括事件核心与结果（必填）",
      "cause": ["前置事件名（跨章因果链，字符串数组，没有就 []）"],
      "effect": ["导致的后果（字符串数组，没有就 []）"],
      "importance": "高（关键转折）/中（普通情节）/低（细节）"
    }
  ]
}
```

### 提取规则（严格遵守）

1. **只提取文本明确提到的信息，不推测、不脑补**
2. 实体名跨章保持一致：同一人用同一名字（别名进 `aliases`，不要建两张卡）
3. 因果链是核心价值：本章事件若由前章事件导致，`cause` 里填那个事件的 `name`（一字不差）
4. 没有内容的数组字段一律填 `[]`，字符串字段可填 `null`
5. 每章一般产出：1-5 人物（新出场才建卡，旧人物不重复建）、0-3 设定、2-8 事件
6. 把批次 JSON 存到 `<root>/data/agent_runs/<书名>/cards-NNN-MMM.json`

## 第 3 步：写入知识库

```bash
python -m src.main --ingest data/agent_runs/<书名>/cards-001-005.json --chapter "第3章"
```

- `--chapter`：可选，给这批事件统一注入章节归属（卡片里没写 chapter 时）
- `--book-title`：可选，卡片 JSON 缺 title 时的兜底
- 增量模式：同名卡片自动更新，重复 ingest 安全；索引自动重建
- 输出确认：`写入: 人物 X / 设定 Y / 事件 Z，生成/更新 N 个文件`

全部批次完成后，验证一次：

```bash
python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/books')))"
```

（Web 服务未启动时先运行 `python -m uvicorn web.app:app --port 8000`）

## 完成后的查询方式

- **Web 界面**：`http://127.0.0.1:8000` —— 图谱、时间线、人物/设定卡、全局搜索
- **MCP 工具**：客户端配置 story-wiki MCP server（`python -m web.mcp_server`）后可用
  `list_books / get_overview / search / list_characters / get_character / get_event /
  get_setting / get_timeline / get_graph` 九个工具查询

## 常见问题

- **plan 出来只有 1 个超长"章"**：原书没有可识别的章节标题，会用 5000 字分块兜底，属正常
- **ingest 报「缺少书名」**：卡片 JSON 顶层没 title 且没传 --book-title
- **想重来**：删 `<root>/data/output/<书名>/` 目录后执行 `python -m src.indexer` 重建索引
- **不要修改 generator 的输出格式**：卡片文件是 Web/MCP 的数据源，字段约定见上
