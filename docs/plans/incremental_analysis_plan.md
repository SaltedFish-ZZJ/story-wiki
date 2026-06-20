# 增量分析功能实现计划

> 版本：v1.0
> 创建时间：2026-06-20
> 状态：待审阅

---

## 一、需求概述

### 1.1 问题背景

当前 Story Wiki 的分析流程是**全量覆盖**模式：

```
第 1 次运行：分析 1-20 章 → 生成完整笔记
第 2 次运行：分析 1-40 章 → 覆盖之前的笔记（1-20 章的分析结果丢失）
```

**痛点：**
- 长篇小说（100+ 章）无法一次性分析完，需要分批处理
- 每次分析都要从头开始，浪费 API 调用和时间
- 之前的分析结果无法保留

### 1.2 目标功能

**增量分析模式：**

```
第 1 次运行：分析 1-20 章 → 生成笔记（characters/、settings/、events/）
第 2 次运行：分析 21-40 章 → 追加笔记，保留 1-20 章的结果
第 3 次运行：分析 41-60 章 → 追加笔记，保留 1-40 章的结果
```

### 1.3 核心价值

| 价值点 | 说明 |
|--------|------|
| 节省成本 | 只分析新章节，不重复分析已处理内容 |
| 保留历史 | 之前的分析结果不会丢失 |
| 断点续传 | 分析中断后，可以从断点继续 |
| 渐进完善 | 可以分多次分析，每次补充新内容 |

---

## 二、技术方案

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    增量分析流程                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐                                       │
│  │  1. 检测阶段  │  扫描 vault 目录，读取已有笔记        │
│  └──────┬───────┘                                       │
│         │                                               │
│         ▼                                               │
│  ┌──────────────┐                                       │
│  │  2. 加载阶段  │  解析已有数据，构建初始上下文          │
│  └──────┬───────┘                                       │
│         │                                               │
│         ▼                                               │
│  ┌──────────────┐                                       │
│  │  3. 分析阶段  │  逐章分析，携带已知上下文              │
│  └──────┬───────┘                                       │
│         │                                               │
│         ▼                                               │
│  ┌──────────────┐                                       │
│  │  4. 合并阶段  │  新旧数据智能合并，避免重复            │
│  └──────┬───────┘                                       │
│         │                                               │
│         ▼                                               │
│  ┌──────────────┐                                       │
│  │  5. 写入阶段  │  更新/创建笔记文件                    │
│  └──────────────┘                                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2.2 详细设计

#### 阶段 1：检测已有笔记

**目标：** 检查 vault 中是否已有该书的笔记，确定哪些章节已分析。

**实现方案：**

```python
# src/pipeline.py 新增函数
def detect_existing_analysis(title: str) -> dict:
    """
    检测已有分析结果

    Returns:
        {
            "exists": True/False,
            "chapters_analyzed": ["第1章", "第2章", ...],  # 已分析的章节列表
            "characters": [...],  # 已有人物列表
            "settings": [...],    # 已有设定列表
            "events": [...]       # 已有事件列表
        }
    """
    book_dir = os.path.join(VAULT_DIR, title)

    if not os.path.exists(book_dir):
        return {"exists": False, "chapters_analyzed": [], ...}

    # 扫描已分析的章节（从 _index.md 或 chapters/ 目录获取）
    chapters = scan_analyzed_chapters(book_dir)

    # 读取已有人物/设定/事件
    characters = read_existing_characters(book_dir)
    settings = read_existing_settings(book_dir)
    events = read_existing_events(book_dir)

    return {
        "exists": True,
        "chapters_analyzed": chapters,
        "characters": characters,
        "settings": settings,
        "events": events
    }
```

**扫描已分析章节的方法：**

方案 A：从 `_index.md` 解析（推荐）
```python
def scan_analyzed_chapters(book_dir: str) -> list:
    """从 _index.md 中提取已分析的章节列表"""
    index_path = os.path.join(book_dir, "_index.md")
    if not os.path.exists(index_path):
        return []

    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取章节链接，如 [[第1章_xxx]]
    chapters = re.findall(r'\[\[第(\d+)章.*?\]\]', content)
    return [f"第{n}章" for n in chapters]
```

方案 B：扫描 `chapters/` 目录
```python
def scan_analyzed_chapters_v2(book_dir: str) -> list:
    """扫描 chapters/ 目录获取已分析章节"""
    chapters_dir = os.path.join(book_dir, "chapters")
    if not os.path.exists(chapters_dir):
        return []

    files = os.listdir(chapters_dir)
    chapters = [f.replace('.md', '') for f in files if f.endswith('.md')]
    return sorted(chapters)
```

---

#### 阶段 2：构建初始上下文

**目标：** 将已有数据转换为 AI 可理解的上下文字符串。

**实现方案：**

```python
# src/pipeline.py 新增函数
def build_initial_context(existing_data: dict) -> str:
    """
    构建初始上下文字符串，传给 AI 作为已知信息

    Returns:
        多行字符串，格式如下：
        ---
        已知人物：
        - 罗伯特·清崎：富爸爸的儿子的朋友，后来成为作家
        - 穷爸爸：罗伯特的父亲，教育家
        ...
        已知设定：
        - 老鼠赛跑：描述工薪阶层陷入的财务困境
        ...
        已知事件：
        - 1994年：47岁退休
        ...
        ---
    """
    lines = ["已知信息："]

    # 人物
    if existing_data.get("characters"):
        lines.append("\n已知人物：")
        for char in existing_data["characters"]:
            desc = char.get("description", "")
            relations = ", ".join(char.get("relations", []))
            lines.append(f"- {char['name']}：{desc}（关系：{relations}）")

    # 设定
    if existing_data.get("settings"):
        lines.append("\n已知设定：")
        for setting in existing_data["settings"]:
            lines.append(f"- {setting['name']}：{setting.get('description', '')}")

    # 事件
    if existing_data.get("events"):
        lines.append("\n已知事件：")
        for event in existing_data["events"]:
            lines.append(f"- {event['name']}：{event.get('description', '')}")

    lines.append("\n---")
    lines.append("请只提取新内容，已知信息请勿重复提取。")

    return "\n".join(lines)
```

---

#### 阶段 3：分析新章节

**目标：** 逐章分析，携带已有上下文，只提取新内容。

**修改 analyzer.py 的分章 prompt：**

```python
# src/analyzer.py 修改 CHAPTER_SYSTEM_PROMPT
CHAPTER_SYSTEM_PROMPT = """
你是一个文学/文本分析专家。分析这一章节，提取新人物、新设定、新事件。

## 已知信息（之前章节已提取）
{initial_context}

## 分析要求
1. **只提取新内容**：已知信息中已有的人物/设定/事件请勿重复
2. **更新已有信息**：如果新章节补充了已知人物的背景，更新其描述
3. **识别关系变化**：如果人物关系发生变化，请在事件中体现

## 输出格式
保持原有 JSON 格式，但只包含新发现的内容：
{
    "chapter_summary": "本章摘要",
    "characters": [...],  // 只包含新人物
    "settings": [...],    // 只包含新设定
    "events": [...]       // 只包含新事件
}
"""
```

**修改 analyze_chapter() 函数：**

```python
# src/analyzer.py 修改
def analyze_chapter(chapter_text: str, chapter_title: str, known_context: str = "") -> dict:
    """
    分析单个章节，携带已知上下文

    Args:
        chapter_text: 章节文本
        chapter_title: 章节标题
        known_context: 已知信息上下文字符串

    Returns:
        分析结果字典
    """
    # 构建 prompt
    system_prompt = CHAPTER_SYSTEM_PROMPT.format(initial_context=known_context)
    user_prompt = f"请分析以下章节：\n\n【{chapter_title}】\n\n{chapter_text}"

    # 调用 API
    result = call_api(system_prompt, user_prompt)

    # 添加章节元数据
    result["chapter"] = chapter_title

    return result
```

---

#### 阶段 4：智能合并

**目标：** 将新分析结果与已有数据合并，避免重复。

**实现方案：**

```python
# src/pipeline.py 新增函数
def merge_analysis_results(existing_data: dict, new_results: list) -> dict:
    """
    合并新旧分析结果

    合并规则：
    1. 人物：同名合并（取更长描述、合并关系列表、合并别名）
    2. 设定：同名合并（取更长描述）
    3. 事件：同名合并（合并参与者、合并因果链）
    4. 章节摘要：追加到列表
    """
    merged = {
        "characters": existing_data.get("characters", []).copy(),
        "settings": existing_data.get("settings", []).copy(),
        "events": existing_data.get("events", []).copy(),
        "chapters": existing_data.get("chapters", []).copy()
    }

    for result in new_results:
        # 合并人物
        for new_char in result.get("characters", []):
            merged["characters"] = merge_character(
                merged["characters"], new_char
            )

        # 合并设定
        for new_setting in result.get("settings", []):
            merged["settings"] = merge_setting(
                merged["settings"], new_setting
            )

        # 合并事件
        for new_event in result.get("events", []):
            merged["events"] = merge_event(
                merged["events"], new_event
            )

        # 追加章节摘要
        merged["chapters"].append({
            "title": result["chapter"],
            "summary": result.get("chapter_summary", "")
        })

    return merged


def merge_character(existing_list: list, new_char: dict) -> list:
    """合并人物：同名合并，取更长描述"""
    for i, char in enumerate(existing_list):
        if char["name"] == new_char["name"]:
            # 同名 → 合并
            existing_list[i] = {
                "name": char["name"],
                "description": max(char.get("description", ""), new_char.get("description", ""), key=len),
                "relations": list(set(char.get("relations", []) + new_char.get("relations", []))),
                "aliases": list(set(char.get("aliases", []) + new_char.get("aliases", [])))
            }
            return existing_list

    # 新人物 → 追加
    existing_list.append(new_char)
    return existing_list


def merge_setting(existing_list: list, new_setting: dict) -> list:
    """合并设定：同名合并，取更长描述"""
    for i, setting in enumerate(existing_list):
        if setting["name"] == new_setting["name"]:
            existing_list[i] = {
                "name": setting["name"],
                "description": max(setting.get("description", ""), new_setting.get("description", ""), key=len)
            }
            return existing_list

    existing_list.append(new_setting)
    return existing_list


def merge_event(existing_list: list, new_event: dict) -> list:
    """合并事件：同名合并，合并参与者和因果链"""
    for i, event in enumerate(existing_list):
        if event["name"] == new_event["name"]:
            existing_list[i] = {
                "name": event["name"],
                "time": event.get("time") or new_event.get("time"),
                "participants": list(set(event.get("participants", []) + new_event.get("participants", []))),
                "location": event.get("location") or new_event.get("location"),
                "description": max(event.get("description", ""), new_event.get("description", ""), key=len),
                "cause": list(set(event.get("cause", []) + new_event.get("cause", [])))
            }
            return existing_list

    existing_list.append(new_event)
    return existing_list
```

---

#### 阶段 5：更新写入

**目标：** 将合并后的数据写入 vault，更新已有文件。

**修改 generator.py：**

```python
# src/generator.py 修改
def generate_book_notes(analysis_result: dict, title: str, is_incremental: bool = False):
    """
    生成书籍笔记

    Args:
        analysis_result: 分析结果
        title: 书名
        is_incremental: 是否为增量模式
    """
    book_dir = os.path.join(VAULT_DIR, title)

    if is_incremental:
        # 增量模式：只更新/追加，不覆盖
        update_existing_notes(analysis_result, book_dir)
    else:
        # 全量模式：生成所有文件
        generate_all_notes(analysis_result, book_dir)


def update_existing_notes(analysis_result: dict, book_dir: str):
    """增量更新已有笔记"""
    # 1. 更新人物卡片（只更新变化的）
    for char in analysis_result.get("characters", []):
        update_character_card(char, book_dir)

    # 2. 更新设定卡片
    for setting in analysis_result.get("settings", []):
        update_setting_card(setting, book_dir)

    # 3. 更新事件卡片
    for event in analysis_result.get("events", []):
        update_event_card(event, book_dir)

    # 4. 更新章节摘要
    update_chapter_summaries(analysis_result.get("chapters", []), book_dir)

    # 5. 更新索引文件
    update_book_index(analysis_result, book_dir)


def update_character_card(character: dict, book_dir: str):
    """更新人物卡片（如果已存在则合并，不存在则创建）"""
    filepath = os.path.join(book_dir, "characters", f"{character['name']}.md")

    if os.path.exists(filepath):
        # 已存在 → 读取并合并
        existing = read_character_from_file(filepath)
        merged = merge_character_data(existing, character)
        write_character_card(merged, book_dir)
    else:
        # 不存在 → 创建新文件
        write_character_card(character, book_dir)
```

---

## 三、实现步骤

### 步骤 1：修改 pipeline.py（核心逻辑）

| 任务 | 文件 | 说明 |
|------|------|------|
| 1.1 新增 `detect_existing_analysis()` | pipeline.py | 检测已有笔记 |
| 1.2 新增 `build_initial_context()` | pipeline.py | 构建初始上下文 |
| 1.3 新增 `merge_analysis_results()` | pipeline.py | 合并新旧结果 |
| 1.4 新增合并辅助函数 | pipeline.py | merge_character/setting/event |
| 1.5 修改 `analyze_book()` | pipeline.py | 集成增量逻辑 |

### 步骤 2：修改 analyzer.py（prompt 优化）

| 任务 | 文件 | 说明 |
|------|------|------|
| 2.1 修改 `CHAPTER_SYSTEM_PROMPT` | analyzer.py | 增加增量分析指令 |
| 2.2 修改 `analyze_chapter()` | analyzer.py | 接收并使用已知上下文 |

### 步骤 3：修改 generator.py（更新写入）

| 任务 | 文件 | 说明 |
|------|------|------|
| 3.1 新增 `update_existing_notes()` | generator.py | 增量更新逻辑 |
| 3.2 新增 `update_*_card()` 系列函数 | generator.py | 各类型卡片更新 |
| 3.3 修改 `generate_book_notes()` | generator.py | 支持增量模式 |

### 步骤 4：修改 main.py / agent.py（CLI 支持）

| 任务 | 文件 | 说明 |
|------|------|------|
| 4.1 新增 `--incremental` 参数 | main.py | 启用增量模式 |
| 4.2 修改 agent.py | agent.py | 交互式支持增量 |

### 步骤 5：测试验证

| 任务 | 说明 |
|------|------|
| 5.1 单元测试 | 测试合并逻辑 |
| 5.2 集成测试 | 端到端增量分析 |
| 5.3 文档更新 | 更新 DEV.md、README.md |

---

## 四、测试计划

### 4.1 测试场景

#### 场景 1：首次分析（无已有笔记）
```
输入：《红楼梦》前 50 章
预期：生成完整笔记，无报错
```

#### 场景 2：增量追加（有已有笔记）
```
输入：《红楼梦》后 50 章（已有前 50 章笔记）
预期：
- 保留前 50 章的人物/设定/事件
- 追加新发现的人物/设定/事件
- 更新已有信息（如有补充）
```

#### 场景 3：重复分析（相同章节）
```
输入：《红楼梦》前 50 章（已分析过）
预期：跳过或更新，不产生重复数据
```

#### 场景 4：断点续传
```
输入：分析到第 30 章中断，重新运行
预期：从第 31 章继续，保留前 30 章结果
```

### 4.2 测试用例

```python
# tests/test_incremental.py

def test_detect_existing_analysis():
    """测试检测已有笔记"""
    # 准备：创建模拟的 vault 目录
    # 执行：调用 detect_existing_analysis()
    # 验证：返回正确的已分析章节列表

def test_build_initial_context():
    """测试构建初始上下文"""
    # 准备：构造已有数据
    # 执行：调用 build_initial_context()
    # 验证：生成正确的上下文字符串

def test_merge_characters():
    """测试人物合并"""
    # 准备：已有人物列表 + 新人物
    # 执行：调用 merge_character()
    # 验证：同名合并，取更长描述，合并关系

def test_merge_settings():
    """测试设定合并"""
    # 准备：已有设定列表 + 新设定
    # 执行：调用 merge_setting()
    # 验证：同名合并，取更长描述

def test_merge_events():
    """测试事件合并"""
    # 准备：已有事件列表 + 新事件
    # 执行：调用 merge_event()
    # 验证：同名合并，合并参与者和因果链

def test_incremental_analysis():
    """测试增量分析端到端"""
    # 准备：创建模拟的输入文件和已有笔记
    # 执行：调用 analyze_book(is_incremental=True)
    # 验证：新旧数据正确合并
```

---

## 五、CLI 接口设计

### 5.1 命令行参数

```bash
# 全量分析（默认，覆盖旧结果）
python src/main.py --input data/input/红楼梦.txt --title "红楼梦"

# 增量分析（追加到已有笔记）
python src/main.py --input data/input/红楼梦_后50章.txt --title "红楼梦" --incremental

# 指定起始章节
python src/main.py --input data/input/红楼梦.txt --title "红楼梦" --incremental --start-chapter 51

# 指定结束章节
python src/main.py --input data/input/红楼梦.txt --title "红楼梦" --incremental --end-chapter 100
```

### 5.2 交互式 Agent

```python
# agent.py 新增命令
/incremental <文件路径>  # 增量分析指定文件
/status                 # 查看当前分析进度
/resume                 # 从上次断点继续
```

---

## 六、数据结构

### 6.1 分析结果格式

```json
{
    "title": "红楼梦",
    "chapters_analyzed": ["第1章", "第2章", ...],
    "characters": [
        {
            "name": "贾宝玉",
            "description": "...",
            "relations": ["林黛玉-恋人", "薛宝钗-妻子"],
            "aliases": ["宝二爷", "怡红公子"]
        }
    ],
    "settings": [...],
    "events": [...],
    "chapters": [
        {
            "title": "第1章",
            "summary": "..."
        }
    ],
    "metadata": {
        "last_analyzed": "2026-06-20T20:00:00",
        "total_chapters": 120,
        "analyzed_count": 50
    }
}
```

### 6.2 Vault 目录结构

```
D:\Obsidian_Work\myself_wiki\story_wiki\红楼梦\
├── _index.md                    # 书籍索引（更新）
├── characters/                  # 人物卡片（更新）
│   ├── 贾宝玉.md
│   ├── 林黛玉.md
│   └── ...
├── settings/                    # 设定卡片（更新）
│   ├── 大观园.md
│   └── ...
├── events/                      # 事件卡片（更新）
│   ├── 宝黛初见.md
│   └── ...
├── chapters/                    # 章节摘要（追加）
│   ├── 第1章.md
│   ├── 第2章.md
│   └── ...
└── .incremental_state.json      # 增量状态文件（新增）
```

### 6.3 增量状态文件

```json
{
    "version": "1.0",
    "last_analyzed": "2026-06-20T20:00:00",
    "chapters_analyzed": ["第1章", "第2章", ...],
    "total_chapters": 120,
    "analyzed_count": 50,
    "input_files": [
        {
            "path": "data/input/红楼梦.txt",
            "md5": "abc123...",
            "analyzed_at": "2026-06-20T18:00:00"
        }
    ]
}
```

---

## 七、风险与注意事项

### 7.1 潜在风险

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 并发写入冲突 | 多进程同时写入同一文件 | 文件锁机制 |
| 合并逻辑错误 | 人物/设定丢失或重复 | 单元测试覆盖 |
| 状态文件损坏 | 无法恢复分析进度 | 备份机制 |
| 大量小文件 I/O | 性能下降 | 批量写入 |

### 7.2 注意事项

1. **向后兼容**：增量模式不影响全量模式
2. **幂等性**：相同输入多次分析结果一致
3. **可恢复性**：中断后能从断点继续
4. **可追溯性**：记录分析历史，便于审计

---

## 八、工作量估算

| 阶段 | 工作量 | 优先级 |
|------|--------|--------|
| 步骤 1：pipeline.py 核心逻辑 | 4 小时 | P0 |
| 步骤 2：analyzer.py prompt 优化 | 2 小时 | P0 |
| 步骤 3：generator.py 更新写入 | 4 小时 | P0 |
| 步骤 4：CLI 支持 | 2 小时 | P1 |
| 步骤 5：测试验证 | 3 小时 | P1 |
| **总计** | **15 小时** | — |

---

## 九、验收标准

### 9.1 功能验收

- [ ] 首次分析生成完整笔记
- [ ] 增量分析追加新内容，保留旧结果
- [ ] 重复分析不产生重复数据
- [ ] 断点续传从上次断点继续
- [ ] CLI 支持 `--incremental` 参数
- [ ] 交互式 Agent 支持增量模式

### 9.2 测试验收

- [ ] 单元测试通过率 100%
- [ ] 集成测试端到端通过
- [ ] 性能测试：100 章分析时间 < 30 分钟

### 9.3 文档验收

- [ ] DEV.md 更新增量分析说明
- [ ] README.md 更新使用示例
- [ ] 代码注释完整

---

## 十、后续优化

### 10.1 短期优化（v1.0.1）
- 并行分析：多线程/异步 API 调用
- 进度显示：tqdm 进度条
- 结果缓存：避免重复调用 API

### 10.2 中期优化（v1.1）
- 多本书管理：跨作品人物关联
- 全局人物索引：vault 根目录维护
- Web 界面：图形化操作

### 10.3 长期优化（v2.0）
- 增量学习：AI 从用户反馈中学习
- 智能合并：AI 判断是否同一人物
- 版本控制：Git 集成，自动 commit

---

## 附录

### A. 参考资料

- [Obsidian Dataview 插件](https://blacksmithgu.github.io/obsidian-dataview/)
- [Mermaid 图表语法](https://mermaid.js.org/)
- [Python 文件锁](https://docs.python.org/3/library/fcntl.html)

### B. 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-20 | 初版计划 |

---

**计划状态：** 待审阅
**下一步：** 用户审阅后，开始执行步骤 1
