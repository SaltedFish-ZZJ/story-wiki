# Story Wiki 项目日志

记录项目的重要变更和里程碑。

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
