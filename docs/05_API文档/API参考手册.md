# Story Wiki API 参考手册

> 最后更新：2026-06-22
> 版本：v0.12.1

---

## 目录

1. [配置管理模块 (config.py)](#1-配置管理模块-configpy)
2. [文本提取模块 (extractor.py)](#2-文本提取模块-extractorpy)
3. [章节切分模块 (splitter.py)](#3-章节切分模块-splitterpy)
4. [AI分析模块 (analyzer.py)](#4-ai分析模块-analyzerpy)
5. [分析管线模块 (pipeline.py)](#5-分析管线模块-pipelinepy)
6. [笔记生成模块 (generator.py)](#6-笔记生成模块-generatorpy)
7. [CLI入口模块 (main.py)](#7-cli入口模块-mainpy)
8. [交互式分析模块 (agent.py)](#8-交互式分析模块-agentpy)
9. [接口规范模块 (interfaces.py)](#9-接口规范模块-interfacespy)
10. [公共工具模块 (utils.py)](#10-公共工具模块-utilspy)
11. [创作管线模块 (create.py)](#11-创作管线模块-createpy)
12. [章节生成模块 (chapter_generator.py)](#12-章节生成模块-chapter_generatorpy)
13. [情节生成模块 (plot_generator.py)](#13-情节生成模块-plot_generatorpy)
14. [知识库管理模块 (vault_manager.py)](#14-知识库管理模块-vault_managerpy)
15. [小说日志模块 (novel_logger.py)](#15-小说日志模块-novel_loggerpy)

---

## 1. 配置管理模块 (config.py)

### 常量配置

```python
# API配置
DEEPSEEK_API_KEY: str  # DeepSeek API密钥

# 路径配置
VAULT_DIR: Path  # Obsidian Vault根目录路径
DATA_DIR: Path  # 数据目录
INPUT_DIR: Path  # 输入文件目录
STATE_DIR: Path  # 状态目录

# 分析参数
MAX_TEXT_LENGTH: int  # 最大文本长度限制
TEMPERATURE: float  # AI生成温度参数 (0.0-1.0)
MAX_TOKENS: int  # AI生成最大token数
CHAPTER_THRESHOLD: int  # 章节切分阈值

# 内存配置
LARGE_FILE_THRESHOLD: int  # 大文件阈值 (1MB)
CHUNK_READ_SIZE: int  # 分块读取大小 (64KB)
REQUEST_SIZE_WARNING: int  # 请求大小警告 (10MB)
REQUEST_SIZE_LIMIT: int  # 请求大小限制 (50MB)
MAX_MATCHES: int  # 最大匹配数 (1000)
```

### 主要函数

#### `get_system_memory() -> dict`
获取系统内存信息。

**返回值：**
```python
{
    "total": float,      # 总内存 (GB)
    "available": float,  # 可用内存 (GB)
    "percent": float     # 使用百分比
}
```

#### `get_process_memory() -> dict`
获取当前进程内存信息。

**返回值：**
```python
{
    "rss": float,  # 实际使用的物理内存 (MB)
    "vms": float   # 虚拟内存大小 (MB)
}
```

#### `print_memory_status()`
打印系统和进程内存使用状态。

#### `ensure_dirs()`
确保所有必要的目录存在。

---

## 2. 文本提取模块 (extractor.py)

### 主要函数

#### `extract_text(file_path: str, use_streaming: bool = None) -> str`
读取文件并返回清理后的文本，自动检测格式和编码。

**参数：**
- `file_path` (str): 文件路径
- `use_streaming` (bool, optional): 是否使用流式读取，None为自动检测

**返回值：**
- `str`: 清理后的文本内容

**支持格式：**
- `.txt` - 纯文本文件
- `.epub` - 电子书文件
- `.pdf` - PDF文件

**异常：**
- `FileNotFoundError`: 文件不存在
- `ValueError`: 不支持的文件格式
- `UnicodeDecodeError`: 编码错误

**示例：**
```python
from src.extractor import extract_text

# 读取TXT文件
text = extract_text("story/红楼梦.txt")

# 强制使用流式读取
text = extract_text("story/红楼梦.txt", use_streaming=True)
```

### 内部函数

#### `_read_txt(file_path: str) -> str`
读取TXT文件，支持自动编码检测和流式读取。

#### `_read_epub(file_path: str) -> str`
读取EPUB文件，提取纯文本内容。

#### `_read_pdf(file_path: str) -> str`
读取PDF文件，逐页提取文本。

#### `_clean_text(text: str) -> str`
清理文本内容，移除HTML标签、特殊字符等。

---

## 3. 章节切分模块 (splitter.py)

### 数据结构

```python
@dataclass
class Chapter:
    """章节数据结构"""
    index: int              # 章节序号
    title: str              # 章节标题
    text: str               # 章节内容
    char_count: int         # 字符数
    
    # 元数据字段
    book_title: str = None  # 书名
    chapter_title: str = None  # 完整章节标题
    chunk_index: int = 0    # 当前块在章节中的索引
    total_chunks_in_chapter: int = 1  # 章节总块数
    context_before_summary: str = None  # 前文摘要
    book_index: int = 0     # 书在系列中的索引
```

### 主要函数

#### `split_chapters(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[Chapter]`
按章节模式或块大小切分文本。

**参数：**
- `text` (str): 要切分的文本
- `chunk_size` (int, optional): 分块大小，默认5000字

**返回值：**
- `list[Chapter]`: 章节列表

**切分策略：**
1. 优先按"第X回/章"模式切分
2. 如果没有匹配，按固定字数切分
3. 支持重叠窗口（200字重叠）
4. 句子边界断点

**示例：**
```python
from src.splitter import split_chapters

# 按默认设置切分
chapters = split_chapters(text)

# 自定义分块大小
chapters = split_chapters(text, chunk_size=3000)
```

---

## 4. AI分析模块 (analyzer.py)

### 主要函数

#### `analyze_text(text: str, title: str = None) -> dict`
分析完整文本，返回结构化结果。

**参数：**
- `text` (str): 要分析的文本
- `title` (str, optional): 作品标题

**返回值：**
```python
{
    "title": str,           # 作品标题
    "characters": list,     # 人物列表
    "settings": list,       # 设定列表
    "events": list,         # 事件列表
    "summary": str,         # 内容摘要
    "chapters": list        # 章节信息
}
```

#### `analyze_chapter(text: str, known_characters: list = None,
                   known_settings: list = None,
                   known_events: list = None,
                   chapter_title: str = None,
                   context_before_summary: str = None) -> dict`
分析单章，带上下文信息。

**参数：**
- `text` (str): 章节文本
- `known_characters` (list, optional): 已知人物列表
- `known_settings` (list, optional): 已知设定列表
- `known_events` (list, optional): 已知事件列表
- `chapter_title` (str, optional): 章节标题
- `context_before_summary` (str, optional): 前文摘要

**返回值：**
与`analyze_text`相同格式

#### `generate_context_summary(analysis_result: dict, max_length: int = 200) -> str`
生成跨章上下文摘要。

**参数：**
- `analysis_result` (dict): 分析结果
- `max_length` (int, optional): 摘要最大长度

**返回值：**
- `str`: 上下文摘要

### 内部函数

#### `_call_deepseek_with_prompt(prompt: str, max_retries: int = 3) -> str`
调用DeepSeek API，带重试机制。

#### `_postprocess_result(result: dict) -> dict`
后处理分析结果，清理和标准化数据。

#### `_merge_similar_characters(characters: list) -> list`
合并相似人物（模糊匹配）。

---

## 5. 分析管线模块 (pipeline.py)

### 主要函数

#### `analyze_chaptered(text: str, title: str = None,
                     chunk_size: int = 5000,
                     on_chapter_start=None,
                     on_chapter_done=None,
                     use_cache: bool = True) -> dict`
完整分章分析管线。

**参数：**
- `text` (str): 完整文本
- `title` (str, optional): 作品标题
- `chunk_size` (int, optional): 分块大小
- `on_chapter_start` (callable, optional): 章节开始回调
- `on_chapter_done` (callable, optional): 章节完成回调
- `use_cache` (bool, optional): 是否使用缓存

**返回值：**
与`analyze_text`相同格式

#### `analyze_chaptered_incremental(text: str, title: str = None,
                                 chunk_size: int = 5000,
                                 start_chapter: int = None,
                                 end_chapter: int = None,
                                 on_chapter_start=None,
                                 on_chapter_done=None,
                                 use_cache: bool = True) -> dict`
增量分析（追加到现有笔记）。

**参数：**
- `start_chapter` (int, optional): 起始章节
- `end_chapter` (int, optional): 结束章节

#### `merge_characters(existing: list, new_items: list) -> list`
合并人物列表，支持模糊匹配。

#### `merge_settings(existing: list, new_items: list) -> list`
合并设定列表。

#### `merge_events(existing: list, new_items: list) -> list`
合并事件列表。

#### `detect_existing_analysis(title: str) -> dict`
检测现有分析结果。

#### `clear_cache(title: str = None)`
清理缓存。

---

## 6. 笔记生成模块 (generator.py)

### 主要函数

#### `generate_vault(analysis: dict, output_dir: Path = None) -> list[str]`
从分析结果生成Obsidian vault文件。

**参数：**
- `analysis` (dict): 分析结果
- `output_dir` (Path, optional): 输出目录

**返回值：**
- `list[str]`: 生成的文件路径列表

#### `generate_vault_incremental(analysis: dict, output_dir: Path = None) -> list[str]`
增量vault生成（更新现有文件）。

#### `generate_timeline_page(title: str, events: list, book_dir: Path) -> Path`
生成独立的时间线页面。

### 内部函数

#### `_write_character_card(character: dict, book_dir: Path) -> Path`
生成人物卡片。

#### `_write_setting_card(setting: dict, book_dir: Path) -> Path`
生成设定卡片。

#### `_write_event_card(event: dict, book_dir: Path) -> Path`
生成事件卡片。

#### `_write_book_index(analysis: dict, book_dir: Path) -> Path`
生成作品索引。

---

## 7. CLI入口模块 (main.py)

### 主要参数

```bash
python src/main.py [OPTIONS]

OPTIONS:
  --input FILE          输入文件路径
  --title TEXT          作品标题
  --output DIR          输出目录
  --incremental         增量模式
  --chunk-size INT      分块大小 (默认: 5000)
  --create              创作模式
  --chapters INT        章节数 (创作模式)
  --resume              断点续写
  --outline-only        只生成大纲
  --no-cache            禁用缓存
  --clear-cache         清除缓存
  --memory-status       显示内存状态
  --no-split            禁用分章分析
  --no-streaming        禁用流式读取
```

### 使用示例

```bash
# 基本分析
python src/main.py --input story/红楼梦.txt --title "红楼梦"

# 增量分析
python src/main.py --input story/红楼梦.txt --title "红楼梦" --incremental --start-chapter 1 --end-chapter 50

# 创作模式
python src/main.py --create --title "我的小说" --chapters 10

# 查看内存状态
python src/main.py --memory-status
```

---

## 8. 交互式分析模块 (agent.py)

### 主要函数

#### `analyze_and_generate(text: str, title: str = None)`
交互式分析，支持用户提示。

### 交互命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/list` | 列出已分析作品 |
| `/vault` | 查看vault目录 |
| `/cache` | 缓存管理 |
| `/quit` | 退出程序 |

### 使用示例

```python
from src.agent import analyze_and_generate

# 启动交互式分析
analyze_and_generate(text, "红楼梦")
```

---

## 9. 接口规范模块 (interfaces.py)

### 数据结构

#### Character (人物)
```python
@dataclass
class Character:
    name: str                    # 姓名
    identity: str                # 身份
    personality: str             # 性格
    gender: str                  # 性别
    faction: str                 # 势力
    aliases: List[str]           # 别名列表
    role_tags: List[str]         # 角色标签
    status: str                  # 状态
    relationships: List[dict]    # 人际关系
    related_settings: List[str]  # 相关设定
    quotes: List[str]            # 经典语录
    motivation: str              # 动机
    current_state: str           # 当前状态
```

#### Setting (设定)
```python
@dataclass
class Setting:
    name: str                    # 名称
    type: str                    # 类型 (地点|组织|体系)
    description: str             # 描述
    related_characters: List[str]  # 相关人物
    related_settings: List[str]  # 相关设定
```

#### Event (事件)
```python
@dataclass
class Event:
    name: str                    # 事件名
    time: str                    # 时间
    participants: List[str]      # 参与人物
    location: str                # 地点
    description: str             # 描述
    cause: List[str]             # 前置事件
    effect: List[str]            # 后续事件
    chapter: str                 # 章节
    importance: str              # 重要性
```

#### PlotOutline (情节大纲)
```python
@dataclass
class PlotOutline:
    title: str                   # 标题
    theme: str                   # 主题
    conflict: str                # 冲突
    structure: dict              # 结构
    key_points: List[str]        # 关键点
    ending_direction: str        # 结局方向
```

#### ChapterContent (章节内容)
```python
@dataclass
class ChapterContent:
    chapter_num: int             # 章节号
    title: str                   # 标题
    content: str                 # 内容
    word_count: int              # 字数
    characters_involved: List[str]  # 涉及人物
    events_happened: List[str]   # 发生事件
```

### 接口类

#### BaseModule (基础模块)
```python
class BaseModule(ABC):
    @abstractmethod
    def initialize(self, config: dict) -> None: ...
    
    @abstractmethod
    def validate_config(self) -> bool: ...
```

#### VaultManagerInterface (知识库管理接口)
```python
class VaultManagerInterface(BaseModule):
    @abstractmethod
    def load_all_cards(self) -> Dict[str, List[dict]]: ...
    
    @abstractmethod
    def load_character(self, name: str) -> Optional[Character]: ...
    
    @abstractmethod
    def update_character(self, name: str, updates: dict): ...
```

#### PlotGeneratorInterface (情节生成接口)
```python
class PlotGeneratorInterface(BaseModule):
    @abstractmethod
    def generate_outline(self, book_title: str, knowledge_base: dict) -> PlotOutline: ...
    
    @abstractmethod
    def identify_gaps(self, timeline: List[dict], knowledge_base: dict) -> List[dict]: ...
```

#### ChapterGeneratorInterface (章节生成接口)
```python
class ChapterGeneratorInterface(BaseModule):
    @abstractmethod
    def generate_chapter(self, chapter_num: int, outline: PlotOutline, context: dict) -> ChapterContent: ...
    
    @abstractmethod
    def quality_check(self, content: ChapterContent, characters: List[Character]) -> Dict[str, Any]: ...
```

#### NovelLoggerInterface (日志记录接口)
```python
class NovelLoggerInterface(BaseModule):
    @abstractmethod
    def save_chapter(self, chapter_num: int, content: ChapterContent): ...
    
    @abstractmethod
    def merge_novel(self, book_title: str) -> str: ...
```

---

## 10. 公共工具模块 (utils.py)

### 主要函数

#### `safe_filename(name: str) -> str`
将名称转为安全的文件名。

**参数：**
- `name` (str): 原始名称

**返回值：**
- `str`: 安全的文件名

**示例：**
```python
from src.utils import safe_filename

safe_name = safe_filename("红楼梦（第一卷）")  # 返回: "红楼梦_第一卷"
```

#### `normalize_name(name: str) -> str`
去除括号内容和空格，用于模糊匹配。

**参数：**
- `name` (str): 原始名称

**返回值：**
- `str`: 标准化后的名称

**示例：**
```python
from src.utils import normalize_name

normalized = normalize_name("富爸爸（罗伯特·清崎的父亲）")  # 返回: "富爸爸"
```

#### `today_str() -> str`
返回今天的日期字符串（YYYY-MM-DD）。

#### `frontmatter(fields: list) -> list[str]`
构建Obsidian frontmatter块。

**参数：**
- `fields` (list): 字段列表

**返回值：**
- `list[str]`: frontmatter行列表

#### `parse_ai_response(raw: str) -> dict`
解析AI返回的JSON，带多种容错策略。

**参数：**
- `raw` (str): AI返回的原始文本

**返回值：**
- `dict`: 解析后的字典

---

## 11. 创作管线模块 (create.py)

### 主要函数

#### `create_novel(book_title: str,
                num_chapters: int = CREATE_DEFAULT_CHAPTERS,
                incremental: bool = True,
                outline_only: bool = False,
                seed: str = None,
                chapter_range: Tuple[int, int] = None,
                outline_only_output: bool = False) -> dict`
核心创作管线：从知识库生成完整小说。

**参数：**
- `book_title` (str): 书名
- `num_chapters` (int, optional): 章节数
- `incremental` (bool, optional): 是否增量
- `outline_only` (bool, optional): 是否只生成大纲
- `seed` (str, optional): 种子文本
- `chapter_range` (Tuple[int, int], optional): 章节范围

**返回值：**
```python
{
    "success": bool,
    "message": str,
    "output_path": str,
    "chapters_generated": int
}
```

#### `quick_create(book_title: str, chapters: int = 3) -> dict`
快速创作：从知识库生成指定章节数的小说。

#### `resume_create(book_title: str, chapters: int = 5) -> dict`
断点续写：从中断处继续生成。

#### `preview_outline(book_title: str) -> dict`
只生成大纲，不写章节。

---

## 12. 章节生成模块 (chapter_generator.py)

### 主要类

#### ChapterGenerator
```python
class ChapterGenerator(ChapterGeneratorInterface):
    def __init__(self, config: dict = None):
        """初始化章节生成器"""
    
    def generate_chapter(self, chapter_num: int, outline: PlotOutline,
                        context: dict) -> ChapterContent:
        """生成章节内容"""
    
    def quality_check(self, content: ChapterContent,
                     characters: List[Character]) -> Dict[str, Any]:
        """质量检查"""
    
    def check_character_consistency(self, content: ChapterContent,
                                   character: Character) -> bool:
        """人物一致性检查"""
    
    def check_timeline_consistency(self, content: ChapterContent,
                                  timeline: List[dict]) -> bool:
        """时间线一致性检查"""
```

---

## 13. 情节生成模块 (plot_generator.py)

### 主要类

#### PlotGenerator
```python
class PlotGenerator(PlotGeneratorInterface):
    def __init__(self, config: dict = None):
        """初始化情节生成器"""
    
    def generate_outline(self, book_title: str,
                        knowledge_base: dict) -> PlotOutline:
        """生成情节大纲"""
    
    def identify_gaps(self, timeline: List[dict],
                     knowledge_base: dict) -> List[dict]:
        """识别情节空白"""
    
    def validate_outline(self, outline: PlotOutline,
                        knowledge_base: dict) -> bool:
        """验证大纲逻辑一致性"""
    
    def expand_outline(self, outline: PlotOutline,
                      gap: dict) -> PlotOutline:
        """扩展大纲（填充情节空白）"""
```

### 便捷函数

```python
def create_plot_generator(config: dict = None) -> PlotGenerator:
    """创建情节生成器实例"""

def analyze_timeline_for_gaps(timeline: List[dict],
                             knowledge_base: dict,
                             config: dict = None) -> List[dict]:
    """分析时间线识别情节空白"""

def generate_plot_outline(book_title: str,
                         knowledge_base: dict,
                         config: dict = None) -> PlotOutline:
    """生成情节大纲"""
```

---

## 14. 知识库管理模块 (vault_manager.py)

### 主要类

#### VaultManager
```python
class VaultManager(VaultManagerInterface):
    def __init__(self, config: dict):
        """初始化模块"""
    
    def load_all_cards(self) -> Dict[str, List[dict]]:
        """加载所有卡片"""
    
    def load_character(self, name: str) -> Optional[Character]:
        """加载人物卡片"""
    
    def load_setting(self, name: str) -> Optional[Setting]:
        """加载设定卡片"""
    
    def load_event(self, name: str) -> Optional[Event]:
        """加载事件卡片"""
    
    def update_character(self, name: str, updates: dict):
        """更新人物卡片"""
    
    def update_setting(self, name: str, updates: dict):
        """更新设定卡片"""
    
    def update_event(self, name: str, updates: dict):
        """更新事件卡片"""
    
    def add_event(self, event: Event):
        """添加事件卡片"""
    
    def add_character(self, character: Character):
        """添加人物卡片"""
    
    def add_setting(self, setting: Setting):
        """添加设定卡片"""
    
    def search_cards(self, keyword: str) -> Dict[str, List[dict]]:
        """搜索卡片"""
    
    def get_timeline(self) -> List[dict]:
        """获取事件时间线"""
```

---

## 15. 小说日志模块 (novel_logger.py)

### 主要类

#### NovelLogger
```python
class NovelLogger(NovelLoggerInterface):
    def __init__(self, config: dict):
        """初始化日志记录器"""
    
    def save_chapter(self, chapter_num: int, content: ChapterContent):
        """保存章节"""
    
    def update_knowledge_log(self, changes: dict):
        """更新知识库日志"""
    
    def merge_novel(self, book_title: str) -> str:
        """合并为完整小说文本"""
    
    def get_progress(self, book_title: str) -> dict:
        """获取写作进度"""
    
    def resume_writing(self, book_title: str) -> int:
        """恢复写作（断点续写）"""
    
    def list_novels(self) -> List[str]:
        """列出所有已记录的小说"""
    
    def delete_novel(self, book_title: str) -> bool:
        """删除小说日志"""
    
    def get_chapter(self, book_title: str, chapter_num: int) -> Optional[ChapterContent]:
        """获取指定章节"""
    
    def get_knowledge_log(self, book_title: str) -> List[dict]:
        """获取知识库日志"""
```

---

## 模块依赖关系

```
config.py
    ↑
utils.py
    ↑
interfaces.py
    ↑
extractor.py
    ↑
splitter.py
    ↑
analyzer.py
    ↑
pipeline.py
    ↑
generator.py
    ↑
vault_manager.py
    ↑
plot_generator.py
    ↑
chapter_generator.py
    ↑
novel_logger.py
    ↑
create.py
    ↑
main.py/agent.py
```

## 核心数据流

### 1. 分析流程
```
extractor.py → splitter.py → analyzer.py → pipeline.py → generator.py
```

### 2. 创作流程
```
vault_manager.py → plot_generator.py → chapter_generator.py → novel_logger.py → create.py
```

### 3. 交互流程
```
main.py/agent.py → 调用分析或创作流程
```

---

## 错误处理

所有模块都遵循统一的错误处理原则：

1. **API调用失败**：自动重试（指数退避）
2. **文件读取错误**：提供清晰的错误信息
3. **数据格式错误**：带容错策略的解析
4. **内存不足**：流式处理和内存监控

## 缓存机制

分析结果支持缓存，避免重复调用API：

- 缓存位置：`data/state/cache/analysis/`
- 缓存策略：基于文本哈希
- 过期时间：7天
- 管理命令：`--clear-cache`, `--no-cache`

---

## 16. Web API 接口（v0.13.0）

FastAPI 应用：`web/app.py`，启动 `uvicorn web.app:app --port 8000`。
交互式文档：`http://127.0.0.1:8000/docs`。

### 只读接口（公开）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/books` | 作品列表 |
| GET | `/api/books/{title}/overview` | 作品概览（统计+核心人物+简介） |
| GET | `/api/books/{title}/characters` | 人物分组列表（支持 `?q=` 搜索） |
| GET | `/api/books/{title}/characters/{name}` | 人物详情（关系/事件/语录） |
| GET | `/api/books/{title}/graph` | 关系图谱数据（`?center=` 中心人物） |
| GET | `/api/books/{title}/timeline` | 事件时间线（`?importance=` `?character=`） |
| GET | `/api/search` | **跨作品全文检索**：`?q=关键词&kind=character|event|setting&limit=20`，走 SQLite FTS5 |

### 写接口（需登录，见下方鉴权）

| 方法 | 路径 | 请求体 | 说明 |
|------|------|--------|------|
| POST | `/api/documents` | multipart：`file`（txt/md/epub/pdf/docx，≤100MB）+ 可选 `title` | 上传文档到 `data/input/`，返回 `{filename, size, title, path}`；同名自动加时间戳 |
| POST | `/api/analyze` | JSON：`{"filename", "title?", "incremental?"}` | 启动后台分析，立即返回 `{task_id, status}` |
| GET | `/api/tasks/{task_id}` | — | 查询任务：`{status: pending/running/done/failed, progress: 0-100, message, error}` |
| GET | `/api/settings` | — | 读取 LLM 连接配置（Key 打码为 `sk-***xxxx`） |
| POST | `/api/settings` | JSON：`{"api_key?", "base_url?", "model?"}` | 保存配置并写回 .env，热生效无需重启；`api_key` 留空沿用原值 |
| POST | `/api/settings/test` | JSON：`{"api_key?", "base_url?", "model?"}` | 用（可未保存的）配置发一次 `max_tokens=1` 的最小补全，验证连通性，返回 `{ok, message, latency_ms}` |

### 鉴权接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/login` | 登录页（未设密码时 307 跳首页） |
| POST | `/login` | 表单 `password` → 303 跳首页并种 `sw_session` cookie |
| POST | `/logout` | 清除会话 |

**鉴权规则**：环境变量 `STORY_WIKI_PASSWORD` 设置后启用；未设置时全部开放（本机模式）。
会话为 HMAC-SHA256 签名 cookie（httpOnly、7 天），只保护 POST 写接口，GET 保持公开。

### Web API 示例

```bash
# 上传并分析一本书（curl）
curl -F "file=@book.docx" http://127.0.0.1:8000/api/documents
# → {"filename":"book.docx","title":"book",...}

curl -X POST http://127.0.0.1:8000/api/analyze \
     -H "Content-Type: application/json" \
     -d '{"filename":"book.docx","title":"我的书"}'
# → {"task_id":"a1b2c3d4e5f6","status":"pending"}

# 轮询进度
curl http://127.0.0.1:8000/api/tasks/a1b2c3d4e5f6
# → {"status":"running","progress":45,"message":"分析第 12 章：...","error":null}

# 全文检索
curl "http://127.0.0.1:8000/api/search?q=孙少安&kind=character"

# 测试 LLM 连接（先测再存；字段留空回退到已保存配置）
curl -X POST http://127.0.0.1:8000/api/settings/test \
     -H "Content-Type: application/json" \
     -d '{"base_url":"https://api.deepseek.com","api_key":"sk-xxx","model":"deepseek-chat"}'
# → {"ok":true,"message":"连接成功（deepseek-chat）","latency_ms":812}
```

---

**注意**：本文档基于v0.7.0版本（16 节 Web API 基于 v0.13.0），后续版本可能会有更新。