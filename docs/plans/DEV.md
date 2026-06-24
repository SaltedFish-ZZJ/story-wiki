# Story Wiki 开发日志

> 记录开发过程中的决策、问题和解决方案

---

## 2026-06-23

### 多本书管理架构决策

**需求：** 支持管理多个作品的知识库（红楼梦、西游记、富爸爸穷爸爸等）

**方案对比：**

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. 扩展 VaultManager | 改动小 | 职责混乱，单作品核心逻辑被稀释 |
| B. 新建 ProjectManager（选定） | 单一职责，可独立扩展 | 多一个模块 |
| C. 改为多 Vault 实例 | 简单 | 无法跨作品搜索 |

**最终决策：** 采用方案 B
- VaultManager 只添加轻量 `list_books()` 方法（扫描目录）
- 跨作品操作全部委托给新的 ProjectManager
- CLI 命令在 main.py 中独立处理

### 人物匹配策略设计

**需求：** 跨作品查找相似人物（如红楼梦的林黛玉 vs 西游记的林黛玉）

**4级匹配策略：**
1. **精确匹配**（confidence: high）— 归一化后名称完全相同
2. **别名匹配**（confidence: high）— 名称在对方别名列表中
3. **子串匹配**（confidence: medium）— 归一化后名称互为子串（≥2字符）
4. **属性匹配**（confidence: low）— 同 faction + 同 identity

**归一化函数 `normalize_name()`：**
- 去除括号内容：`"贾宝玉（主角）"` → `"贾宝玉"`
- 去除空格：`"林 黛 玉"` → `"林黛玉"`

---

## 2026-06-22

### 创作管线架构设计

**核心流程：**
```
VaultManager → PlotGenerator → ChapterGenerator → NovelLogger
```

**BaseModule 接口规范：**
所有模块继承 BaseModule，实现：
- `run(input_data: dict) -> dict` — 统一入口
- `validate(output: dict) -> bool` — 输出验证

### 质量检查双模式

- **AI 模式**：调用大模型检查逻辑一致性、人物性格一致性
- **规则模式**：字数统计、重复检测、敏感词匹配

---

## 2026-06-21

### 长文本处理优化

**问题：** 80万字小说单次分析超出 token 限制

**解决方案：**
- 章节切分（按标题模式 / 按字数）
- 重叠窗口（前后章节重叠 500 字）
- 句子边界（不在句中断开）
- 元数据携带（章节号、书名传递给后续分析）

---

## 2026-06-20

### 项目初始化

**技术选型：**
- Python 3.13
- 小米 mimo-v2.5（通过 token-plan API，OpenAI 兼容格式）
- Obsidian Markdown 输出（frontmatter + wikilink）

**目录结构设计：**
```
story_wiki/
├── src/          ← 源代码
├── tests/        ← 测试
├── data/         ← 数据文件
├── story/        ← 原始文本
└── docs/         ← 项目文档
```

---

## 开发规范记录

1. **增量开发：** 每次只改一个模块，改完测试再继续
2. **测试优先：** 修改代码后运行 `python -m pytest tests/ -v` 确保通过
3. **错误处理：** AI 返回非 JSON 时有 fallback，不崩溃
4. **配置管理：** API key 存 `.env` 文件，不硬编码
5. **中文注释：** 代码注释用中文，函数/变量名用英文 snake_case
