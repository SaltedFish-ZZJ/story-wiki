# AI 分析模块

## 职责

调用 DeepSeek API，从纯文本中提取人物、设定、事件、关系等结构化数据。
支持分章分析长文本，带进度显示和结果缓存。

## 接口

```python
def analyze_text(text: str, title: str = None) -> dict:
    """
    分析文本，提取人物、设定、关系。
    
    Args:
        text: 纯文本内容
        title: 可选的作品名（覆盖 AI 推断）
    
    Returns:
        结构化分析结果 dict
    """
```

```python
def analyze_chapter(text: str, known_characters: list = None,
                    known_settings: list = None, known_events: list = None,
                    chapter_title: str = None) -> dict:
    """
    分析单个章节，携带已知人物/设定/事件上下文。
    
    Args:
        text: 章节文本
        known_characters: 已知人物列表（之前章节提取的）
        known_settings: 已知设定列表
        known_events: 已知事件列表
        chapter_title: 当前章节标题
    
    Returns:
        本章的分析结果 dict
    """
```

## Prompt 设计要点

1. **角色设定**：你是一个专业的文学分析助手
2. **输出要求**：严格返回 JSON，不要 markdown 包裹
3. **提取维度**：
   - 人物：姓名、别名、身份、性格、性别、所属势力
   - 关系：每对人物之间的关系类型
   - 设定：地点/组织/体系的名称和描述
   - 事件：关键事件（转折点、重要情节、冲突等）
     - name：事件名（4-8字概括）
     - time：时间（从文本推断）
     - participants：参与人物名
     - location：发生地点（引用设定名）
     - description：一句话描述
     - cause：前置事件名（因果关系）
     - chapter：章节名（分章分析时自动填充）
4. **容错**：文本中没有明确信息的字段用 null

## API 调用

```python
import requests

def call_deepseek(prompt: str, text: str) -> str:
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.3,  # 低温度，输出更稳定
        "max_tokens": 4096
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()["choices"][0]["message"]["content"]
```

## JSON 解析容错

AI 可能返回带 markdown 包裹的 JSON，需要处理：

```python
import json
import re

def parse_ai_response(raw: str) -> dict:
    # 尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 ```json ... ``` 中的内容
    match = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    
    # 尝试提取第一个 { ... } 块
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    
    raise ValueError("AI 返回内容无法解析为 JSON")
```

## Token 限制策略

- 文本 ≤ 400000 字：直接发送全文（DeepSeek 1M 上下文）
- 文本 > 400000 字：截取前 400000 字

## 分章分析

长文本（> 5000 字）自动启用分章分析：

1. **章节切分**：按标题模式（第X章/第X回/Chapter X）切分，无标记时按字数 fallback
2. **逐章分析**：每章携带已知人物/设定/事件上下文，AI 只提取新内容
3. **合并去重**：同名人物合并（取更长字段、合并关系），同名设定取更长描述
4. **进度显示**：`[进度] 20% (3/15) — 分析: 第2章 (23365字)`

## 分析结果缓存

为避免重复分析同一文本，支持结果缓存：

- **缓存键**：每章文本的 MD5 哈希 + 作品名哈希
- **缓存位置**：`data/state/cache/analysis/`
- **缓存有效期**：7 天（过期自动失效）
- **使用方式**：
  - 默认启用缓存
  - `--no-cache` 禁用缓存（强制重新分析）
  - `--clear-cache` 清除所有缓存
  - Agent 中使用 `/cache` 命令清除缓存

```python
# 缓存读写
def _get_cached_result(text: str, title: str = None) -> dict | None:
    """从缓存读取分析结果，未命中返回 None"""

def _save_cached_result(text: str, title: str, result: dict):
    """保存分析结果到缓存"""
```
