# AI 分析模块

## 职责

调用 DeepSeek API，从纯文本中提取人物、设定、事件、关系等结构化数据。

## 接口

```python
def analyze_text(text: str) -> dict:
    """
    输入纯文本，返回结构化分析结果。
    
    返回格式：
    {
        "title": "作品名",
        "characters": [...],
        "settings": [...],
        "events": [...],
        "summary": "一句话摘要"
    }
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

## Token 限制策略（Demo 阶段）

- 文本 ≤ 8000 字：直接发送全文
- 文本 > 8000 字：截取前 8000 字（Demo 限制，后续做分章处理）
