# Story Wiki 开发日志

> 下次打开这个文件就知道：做到哪了、下一步干什么、怎么跑。

## 当前状态：v0.1.1（Phase 1 完成）

```
Git: f9e4fb1
功能: txt 输入 → DeepSeek 分析 → Obsidian 笔记生成
验证: 红楼梦片段(8人物) ✅ | 富爸爸穷爸爸12万字 ✅
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
│   ├── analyzer.py    ← DeepSeek API 调用 + JSON 解析
│   ├── generator.py   ← Obsidian .md 文件生成
│   ├── main.py        ← CLI 单次分析入口
│   └── agent.py       ← 交互式分析（无 TUI）
├── data/input/        ← 待分析文本放这里
├── .env               ← API Key（git 不跟踪）
└── log.md             ← 项目变更日志
```

**Obsidian vault:** `D:\Obsidian_Work\myself_wiki\story_wiki\`

## 已知问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 长文本分析内容偏少 | AI 一次性处理 12 万字会"遗忘"中间内容 | Phase 2 分章处理 |
| 只支持 .txt 格式 | Demo 阶段未实现 epub/pdf | Phase 2 加格式支持 |
| 输出 token 限制 8192 | 复杂作品人物多时列不全 | 可调大，但会增加成本 |
| httpx 不可用 | Python 3.13 兼容问题 | 已改用 requests |

## Phase 2 待开发

**核心目标：分章处理长文本**

```
输入 txt → 自动切分章节 → 逐章 AI 分析 → 合并去重 → 生成完整笔记
```

具体任务：
- [ ] 章节切分器（按"第X章/第X回"等模式切分）
- [ ] 逐章分析 + 状态追踪（维护已知人物/设定的 JSON）
- [ ] 全局汇总去重（同名人物合并、关系去重）
- [ ] epub 格式支持（用 ebooklib）
- [ ] pdf 格式支持（用 pymupdf）
- [ ] 增量分析（新章节追加到已有笔记，不覆盖）

## 技术备忘

- **API:** DeepSeek `deepseek-chat`，1M 上下文，当前设 40 万字上限
- **API Key:** `.env` 文件，变量名 `STORY_WIKI_API_KEY`
- **编码容错:** txt 读取按 utf-8 → gbk → gb2312 → latin-1 顺序尝试
- **JSON 解析:** 三层容错（直接解析 → 提取 ```json``` → 提取 `{}`）
- **wikilink:** 人物关系用 `[[人名]]` 写在人物卡里，Graph View 自动识别
