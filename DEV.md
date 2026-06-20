# Story Wiki 开发日志

> 下次打开这个文件就知道：做到哪了、下一步干什么、怎么跑。

## 当前状态：v0.2.0（Phase 2 分章核心完成）

```
功能: txt 输入 → 自动分章 → 逐章AI分析（带上下文） → 合并去重 → Obsidian 笔记生成
新增: splitter.py（章节切分）+ pipeline.py（分章管线）+ analyzer.py 分章prompt
验证: 富爸爸穷爸爸(12.4万字) → 63人物 63设定 ✅
API: 小米 mimo-v2.5（token-plan API）
```

## 快速启动

```bash
cd D:\HermesAgent\Workspace\story_wiki

# 单次分析
python src/main.py --input data/input/xxx.txt --title "书名"

# 交互式
python src/agent.py

# 查看结果
# 用 Obsidian 打开 D:\Obsidian_Work\myself_wiki\story_wiki
```

## 项目结构

```
story_wiki/
├── src/
│   ├── config.py      ← 配置（API key、路径、参数）
│   ├── extractor.py   ← 文本读取（仅支持 .txt）
│   ├── splitter.py    ← 章节切分（按标题模式/按字数）
│   ├── analyzer.py    ← DeepSeek API 调用 + JSON 解析 + 分章prompt
│   ├── pipeline.py    ← 分章分析管线（切分→逐章分析→合并去重）
│   ├── generator.py   ← Obsidian .md 文件生成
│   ├── main.py        ← CLI 入口（自动判断分章）
│   └── agent.py       ← 交互式分析（支持分章）
├── data/input/        ← 待分析文本放这里
├── .env               ← API Key（git 不跟踪）
└── log.md             ← 项目变更日志
```

**Obsidian vault:** `D:\Obsidian_Work\myself_wiki\story_wiki\`

## 已知问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| ~~长文本分析内容偏少~~ | ~~AI 一次性处理 12 万字会"遗忘"中间内容~~ | ✅ Phase 2 分章处理已解决 |
| 只支持 .txt 格式 | Demo 阶段未实现 epub/pdf | Phase 2 加格式支持 |
| 输出 token 限制 8192 | 复杂作品人物多时列不全 | 可调大，但会增加成本 |
| httpx 不可用 | Python 3.13 兼容问题 | 已改用 requests |

## Phase 2 进度

**核心目标：分章处理长文本** ✅ 核心完成

```
输入 txt → 自动切分章节 → 逐章 AI 分析（带上下文） → 合并去重 → 生成完整笔记
```

具体任务：
- [x] 章节切分器（splitter.py — 按"第X章/第X回"等模式切分 + 按字数 fallback）
- [x] 逐章分析 + 上下文传递（pipeline.py + analyzer.py 分章 prompt）
- [x] 全局汇总去重（同名人物合并、关系去重）
- [x] main.py / agent.py 自动判断分章
- [x] 端到端验证（富爸爸穷爸爸 12.4万字 → 63人物 63设定）
- [ ] epub 格式支持（用 ebooklib）
- [ ] pdf 格式支持（用 pymupdf）
- [ ] 增量分析（新章节追加到已有笔记，不覆盖）

## 技术备忘

- **API:** 小米 mimo-v2.5（`https://token-plan-cn.xiaomimimo.com`），OpenAI 兼容格式
- **API Key:** `.env` 文件，变量名 `STORY_WIKI_API_KEY`（tp- 开头）
- **Base URL:** `.env` 文件，变量名 `STORY_WIKI_BASE_URL`
- **模型名:** `.env` 文件，变量名 `STORY_WIKI_MODEL`（默认 `mimo-v2.5`）
- **编码容错:** txt 读取按 utf-8 → gbk → gb2312 → latin-1 顺序尝试
- **JSON 解析:** 三层容错（直接解析 → 提取 ```json``` → 提取 `{}`）
- **wikilink:** 人物关系用 `[[人名]]` 写在人物卡里，Graph View 自动识别
- **分章阈值:** 文本 > 5000 字自动启用分章（`CHAPTER_THRESHOLD`）
