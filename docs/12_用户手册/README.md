# 用户手册

## 快速上手

### 1. 准备文本

把你想分析的小说/文章保存为 `.txt` 文件，放入 `data/input/` 目录。

### 2. 运行分析

```bash
python src/analyzer.py --input data/input/你的文件.txt
```

### 3. 查看结果

用 Obsidian 打开 `D:\Obsidian_Work\story_wiki\` 目录。

### 4. 查看关系图

在 Obsidian 中按 `Ctrl+G` 打开 Graph View，可以看到人物关系网络。

如需只看某一部作品的关系，在 Graph View 的过滤器中输入 `path:作品名`。

## 常见问题

**Q: AI 分析的结果不准确怎么办？**
A: 可以手动编辑 vault 中的 .md 文件，Obsidian 就是普通的 Markdown，直接改就行。

**Q: 支持什么格式的文件？**
A: 目前只支持 .txt，后续会支持 .epub 和 .pdf。

**Q: 一次能分析多长的文本？**
A: Demo 阶段建议 8000 字以内，后续会支持分章处理长文本。
