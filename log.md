# Story Wiki 项目日志

记录项目的重要变更和里程碑。

---

## 2026-06-20 — Phase 1 最小 Demo 完成

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
└── main.py        ← CLI 入口
```

### 使用方式
```bash
python src/main.py --input data/input/xxx.txt --title "作品名"
```
