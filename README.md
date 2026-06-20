# Story Wiki

AI 驱动的故事知识库系统。

## 功能

- **分析**：输入任意文字材料（小说/历史事件/传记），AI 自动提取人物、设定、关系，生成 Obsidian 笔记
- **可视化**：利用 Obsidian Graph View 查看人物关系网络
- **创作**（规划中）：用户提供想法/种子，AI 协作构建世界观，驱动人物推演生成小说

## 快速开始

```bash
# 1. 安装依赖
pip install requests

# 2. 配置 API（复制 .env.example 为 .env 并填入配置）
cp .env.example .env

# 3. 运行分析（长文本自动分章）
python src/main.py --input data/input/your_novel.txt --title "书名"

# 4. 交互式分析
python src/agent.py

# 5. 用 Obsidian 打开 vault 目录，查看 Graph View
```

## 项目结构

```
story_wiki/
├── src/           ← 源代码
├── vault/         ← Obsidian vault 输出
├── data/          ← 输入文本和中间数据
│   └── input/     ← 待分析文本放这里
└── docs/          ← 项目文档
```

## 详细文档

见 [docs/索引.md](docs/索引.md)
