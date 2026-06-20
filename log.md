# Story Wiki 项目日志

记录项目的重要变更和里程碑。

---

## 2026-06-20 — v0.1.1 配置优化 + 交互式 Agent

### 变更
- ✅ 上下文限制提升：8000字 → 40万字（适配 DeepSeek 1M 上下文）
- ✅ 输出 token 提升：4096 → 8192
- ✅ 新增交互式分析 Agent（src/agent.py）
- ✅ 支持文件路径输入和直接文本粘贴
- ✅ 内置 /help /list /vault /quit 命令

### 交互式 Agent 功能
```bash
python src/agent.py
# 启动后：
#   输入文件路径 → 自动读取并分析
#   直接粘贴长文本 → 自动分析
#   /list → 列出已分析作品
#   /quit → 退出
```

---

## 2026-06-20 — v0.1.0 Phase 1 最小 Demo 完成

### 里程碑
- ✅ 项目文档骨架搭建完成（AGENTS.md、README.md、docs/）
- ✅ 核心代码实现：extractor → analyzer → generator
- ✅ 首次端到端测试通过（红楼梦片段）
- ✅ Obsidian Graph View 正确显示人物关系

### 生成结果
- 人物卡片：8 个（林黛玉、贾宝玉、薛宝钗、王熙凤、贾政、袭人、晴雯、贾母）
- 设定卡片：4 个（大观园、潇湘馆、蘅芜苑、怡红院）
- 作品索引：1 个

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
└── agent.py       ← 交互式分析 Agent（循环对话）
```

### 使用方式
```bash
# 单次分析
python src/main.py --input data/input/xxx.txt --title "作品名"

# 交互式 Agent
python src/agent.py
```
