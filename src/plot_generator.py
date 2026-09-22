"""
Story Wiki - 情节生成模块
基于知识库生成情节大纲，支持起承转合结构、情节空白识别、大纲验证和扩展。

实现 PlotGeneratorInterface 接口。
"""
import json
from typing import Dict, List, Optional, Any

from src.api_client import call_api
from src.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    MAX_TOKENS,
    TEMPERATURE,
)
from src.interfaces import PlotGeneratorInterface, PlotOutline
from src.utils import parse_ai_response
from src.logging_setup import get_logger

logger = get_logger("plot_generator")


# ── System Prompts ──

OUTLINE_SYSTEM_PROMPT = """你是一个专业的小说情节架构师。请根据提供的知识库信息（人物、设定、事件），为作品生成一个完整的情节大纲。

作品标题：{book_title}

知识库摘要：
{knowledge_base_summary}

请严格按照以下 JSON 格式返回，不要添加任何 markdown 包裹、代码块标记或额外文字：

{{
  "title": "作品标题",
  "theme": "核心主题（一句话概括作品要表达的主旨）",
  "conflict": "核心冲突（推动故事发展的主要矛盾）",
  "structure": {{
    "起": {{
      "title": "起始阶段标题",
      "summary": "起始阶段概要（2-3句话）",
      "key_events": ["关键事件1", "关键事件2"]
    }},
    "承": {{
      "title": "发展阶段标题",
      "summary": "发展阶段概要（2-3句话）",
      "key_events": ["关键事件1", "关键事件2"]
    }},
    "转": {{
      "title": "转折阶段标题",
      "summary": "转折阶段概要（2-3句话）",
      "key_events": ["关键事件1", "关键事件2"]
    }},
    "合": {{
      "title": "结局阶段标题",
      "summary": "结局阶段概要（2-3句话）",
      "key_events": ["关键事件1", "关键事件2"]
    }}
  }},
  "key_points": ["情节点1", "情节点2", "情节点3"],
  "ending_direction": "结局走向描述（故事将如何收束）"
}}

规则：
1. 大纲必须基于知识库中的已有元素（人物、设定、事件）
2. 起承转合结构必须完整，逻辑连贯
3. 核心冲突要能贯穿全文，推动情节发展
4. 情节点要具体、可执行，能指导后续章节写作
5. 结局走向要与主题呼应，给读者留下深刻印象
6. 整个响应必须是一个合法的 JSON 对象"""


GAP_ANALYSIS_SYSTEM_PROMPT = """你是一个专业的小说情节分析师。请分析给定的事件时间线，识别其中的情节空白和逻辑断裂。

知识库信息：
{knowledge_base_summary}

当前事件时间线：
{timeline_summary}

请严格按照以下 JSON 格式返回，不要添加任何 markdown 包裹、代码块标记或额外文字：

{{
  "gaps": [
    {{
      "type": "gap_type",
      "description": "空白描述",
      "position": "建议插入位置",
      "importance": "high/medium/low",
      "suggested_events": ["建议的事件1", "建议的事件2"]
    }}
  ]
}}

gap_type 类型说明：
- "missing_cause": 缺少前置事件（某事件缺少必要的前置条件）
- "missing_consequence": 缺少后续影响（某事件的后果未展开）
- "time_gap": 时间空白（两个事件之间时间跨度太大）
- "character_missing": 人物缺席（重要人物在某段时间没有活动）
- "relationship_gap": 关系发展空白（人物关系缺少过渡事件）
- "plot_hole": 情节漏洞（逻辑不连贯或矛盾）

规则：
1. 仔细分析事件之间的因果关系
2. 识别重要人物在时间线中的活动空白
3. 检查时间跨度是否合理
4. 评估每个空白的重要性
5. 提供具体的建议事件来填补空白
6. 整个响应必须是一个合法的 JSON 对象"""


VALIDATE_SYSTEM_PROMPT = """你是一个专业的小说情节审核员。请验证给定的情节大纲是否与知识库信息一致，逻辑是否自洽。

知识库信息：
{knowledge_base_summary}

待验证的大纲：
{outline_json}

请严格按照以下 JSON 格式返回，不要添加任何 markdown 包裹、代码块标记或额外文字：

{{
  "is_valid": true/false,
  "issues": [
    {{
      "type": "issue_type",
      "description": "问题描述",
      "severity": "critical/warning/info",
      "suggestion": "修改建议"
    }}
  ],
  "overall_assessment": "整体评估（一句话）"
}}

issue_type 类型说明：
- "character_inconsistency": 人物信息不一致（性格、身份等与知识库矛盾）
- "setting_conflict": 设定冲突（地点、组织等与知识库矛盾）
- "timeline_error": 时间线错误（事件顺序或时间不合理）
- "logic_gap": 逻辑漏洞（因果关系不成立）
- "missing_element": 缺少必要元素（知识库中的重要人物/设定未出现）
- "redundancy": 冗余重复

规则：
1. 对比大纲与知识库中的人物、设定、事件信息
2. 检查人物性格、身份是否一致
3. 检查设定是否与知识库矛盾
4. 验证事件时间线的合理性
5. 评估逻辑链条的完整性
6. 整个响应必须是一个合法的 JSON 对象"""


EXPAND_SYSTEM_PROMPT = """你是一个专业的小说情节架构师。请根据给定的情节空白，扩展原始大纲，填充该空白。

原始大纲：
{outline_json}

需要填补的情节空白：
{gap_json}

请严格按照以下 JSON 格式返回扩展后的大纲，不要添加任何 markdown 包裹、代码块标记或额外文字：

{{
  "title": "作品标题",
  "theme": "核心主题",
  "conflict": "核心冲突",
  "structure": {{
    "起": {{
      "title": "起始阶段标题",
      "summary": "起始阶段概要",
      "key_events": ["关键事件列表"]
    }},
    "承": {{
      "title": "发展阶段标题",
      "summary": "发展阶段概要",
      "key_events": ["关键事件列表"]
    }},
    "转": {{
      "title": "转折阶段标题",
      "summary": "转折阶段概要",
      "key_events": ["关键事件列表"]
    }},
    "合": {{
      "title": "结局阶段标题",
      "summary": "结局阶段概要",
      "key_events": ["关键事件列表"]
    }}
  }},
  "key_points": ["情节点列表"],
  "ending_direction": "结局走向描述"
}}

规则：
1. 保持原有大纲的核心结构和主题不变
2. 在指定位置插入新事件，填补情节空白
3. 确保新事件与原有事件逻辑连贯
4. 新增情节点要具体、可执行
5. 不要删除或改变原有重要情节
6. 整个响应必须是一个合法的 JSON 对象"""


class PlotGenerator(PlotGeneratorInterface):
    """
    情节生成器实现类

    基于 DeepSeek API，根据知识库信息生成情节大纲。
    """

    def __init__(self, config: dict = None):
        """
        初始化情节生成器

        Args:
            config: 配置字典，可覆盖默认配置
        """
        self.config = config or {}
        self._validate_api_config()

    def _validate_api_config(self):
        """验证 API 配置"""
        api_key = self.config.get("api_key", DEEPSEEK_API_KEY)
        if not api_key:
            raise ValueError(
                "未配置 API Key！请设置环境变量 STORY_WIKI_API_KEY 或在 .env 文件中配置"
            )

    # ── action 分发注册表 ──
    ACTIONS = {
        "generate": "_handle_generate",
        "identify_gaps": "_handle_identify_gaps",
        "validate": "_handle_validate",
        "expand": "_handle_expand",
    }

    def run(self, input_data: dict) -> dict:
        """
        运行情节生成模块

        Args:
            input_data: 输入数据
                - book_title: 作品标题（必需）
                - knowledge_base: 知识库内容（必需）
                - action: 操作类型（generate/identify_gaps/validate/expand）
                - outline: 情节大纲（validate/expand 操作需要）
                - gap: 情节空白（expand 操作需要）

        Returns:
            操作结果 dict
        """
        action = input_data.get("action", "generate")
        handler_name = self.ACTIONS.get(action)
        if not handler_name:
            raise ValueError(f"不支持的操作类型: {action}")
        return getattr(self, handler_name)(input_data)

    def _handle_generate(self, input_data: dict) -> dict:
        outline = self.generate_outline(
            input_data.get("book_title", ""), input_data.get("knowledge_base", {})
        )
        return {"outline": outline, "success": True}

    def _handle_identify_gaps(self, input_data: dict) -> dict:
        gaps = self.identify_gaps(
            input_data.get("timeline", []), input_data.get("knowledge_base", {})
        )
        return {"gaps": gaps, "success": True}

    def _handle_validate(self, input_data: dict) -> dict:
        outline = input_data.get("outline")
        if not outline:
            raise ValueError("validate 操作需要提供 outline 参数")
        is_valid = self.validate_outline(outline, input_data.get("knowledge_base", {}))
        return {"is_valid": is_valid, "success": True}

    def _handle_expand(self, input_data: dict) -> dict:
        outline = input_data.get("outline")
        gap = input_data.get("gap")
        if not outline or not gap:
            raise ValueError("expand 操作需要提供 outline 和 gap 参数")
        expanded = self.expand_outline(outline, gap)
        return {"outline": expanded, "success": True}

    def validate(self, output_data: dict) -> bool:
        """
        验证输出数据

        Args:
            output_data: 输出数据

        Returns:
            是否有效
        """
        if not isinstance(output_data, dict):
            return False

        outline = output_data.get("outline")
        if outline is None:
            return False

        if isinstance(outline, PlotOutline):
            return bool(outline.title and outline.theme and outline.structure)
        elif isinstance(outline, dict):
            return bool(
                outline.get("title")
                and outline.get("theme")
                and outline.get("structure")
            )
        return False

    def generate_outline(self, book_title: str, knowledge_base: dict) -> PlotOutline:
        """
        生成情节大纲

        Args:
            book_title: 作品标题
            knowledge_base: 知识库内容（包含 characters, settings, events）

        Returns:
            情节大纲对象
        """
        if not book_title:
            raise ValueError("作品标题不能为空")

        if not knowledge_base:
            raise ValueError("知识库内容不能为空")

        # 构建知识库摘要
        kb_summary = self._build_knowledge_base_summary(knowledge_base)

        # 构建 prompt
        system_prompt = OUTLINE_SYSTEM_PROMPT.format(
            book_title=book_title,
            knowledge_base_summary=kb_summary,
        )

        # 调用 API
        raw_response = self._call_api(system_prompt, f"请为《{book_title}》生成情节大纲")

        # 解析响应
        try:
            result = parse_ai_response(raw_response)
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"AI 返回内容无法解析为 JSON: {e}")

        # 构建 PlotOutline 对象
        structure = result.get("structure", {})
        outline = PlotOutline(
            title=result.get("title") or book_title,
            theme=result.get("theme", ""),
            conflict=result.get("conflict", ""),
            structure=structure,
            key_points=result.get("key_points", []),
            ending_direction=result.get("ending_direction", ""),
        )

        return outline

    def identify_gaps(self, timeline: List[dict], knowledge_base: dict) -> List[dict]:
        """
        识别情节空白

        Args:
            timeline: 事件时间线
            knowledge_base: 知识库内容

        Returns:
            情节空白列表
        """
        if not timeline:
            raise ValueError("事件时间线不能为空")

        if not knowledge_base:
            raise ValueError("知识库内容不能为空")

        # 构建摘要
        kb_summary = self._build_knowledge_base_summary(knowledge_base)
        timeline_summary = self._build_timeline_summary(timeline)

        # 构建 prompt
        system_prompt = GAP_ANALYSIS_SYSTEM_PROMPT.format(
            knowledge_base_summary=kb_summary,
            timeline_summary=timeline_summary,
        )

        # 调用 API
        raw_response = self._call_api(
            system_prompt, "请分析以下事件时间线，识别情节空白"
        )

        # 解析响应
        try:
            result = parse_ai_response(raw_response)
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"AI 返回内容无法解析为 JSON: {e}")

        gaps = result.get("gaps", [])
        return gaps

    def validate_outline(self, outline: PlotOutline, knowledge_base: dict) -> bool:
        """
        验证大纲逻辑一致性

        Args:
            outline: 情节大纲
            knowledge_base: 知识库内容

        Returns:
            是否有效
        """
        if not outline:
            raise ValueError("大纲不能为空")

        if not knowledge_base:
            raise ValueError("知识库内容不能为空")

        # 构建摘要
        kb_summary = self._build_knowledge_base_summary(knowledge_base)
        outline_json = json.dumps(
            {
                "title": outline.title,
                "theme": outline.theme,
                "conflict": outline.conflict,
                "structure": outline.structure,
                "key_points": outline.key_points,
                "ending_direction": outline.ending_direction,
            },
            ensure_ascii=False,
            indent=2,
        )

        # 构建 prompt
        system_prompt = VALIDATE_SYSTEM_PROMPT.format(
            knowledge_base_summary=kb_summary,
            outline_json=outline_json,
        )

        # 调用 API
        raw_response = self._call_api(
            system_prompt, "请验证以下情节大纲的逻辑一致性"
        )

        # 解析响应
        try:
            result = parse_ai_response(raw_response)
        except (ValueError, json.JSONDecodeError) as e:
            # 解析失败时返回 False
            return False

        is_valid = result.get("is_valid", False)
        return is_valid

    def expand_outline(self, outline: PlotOutline, gap: dict) -> PlotOutline:
        """
        扩展大纲（填充情节空白）

        Args:
            outline: 原始大纲
            gap: 情节空白

        Returns:
            扩展后的大纲
        """
        if not outline:
            raise ValueError("大纲不能为空")

        if not gap:
            raise ValueError("情节空白不能为空")

        # 构建 JSON
        outline_json = json.dumps(
            {
                "title": outline.title,
                "theme": outline.theme,
                "conflict": outline.conflict,
                "structure": outline.structure,
                "key_points": outline.key_points,
                "ending_direction": outline.ending_direction,
            },
            ensure_ascii=False,
            indent=2,
        )
        gap_json = json.dumps(gap, ensure_ascii=False, indent=2)

        # 构建 prompt
        system_prompt = EXPAND_SYSTEM_PROMPT.format(
            outline_json=outline_json,
            gap_json=gap_json,
        )

        # 调用 API
        raw_response = self._call_api(
            system_prompt, "请根据情节空白扩展大纲"
        )

        # 解析响应
        try:
            result = parse_ai_response(raw_response)
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"AI 返回内容无法解析为 JSON: {e}")

        # 构建扩展后的大纲
        structure = result.get("structure", {})
        expanded = PlotOutline(
            title=result.get("title") or outline.title,
            theme=result.get("theme") or outline.theme,
            conflict=result.get("conflict") or outline.conflict,
            structure=structure if structure else outline.structure,
            key_points=result.get("key_points", outline.key_points),
            ending_direction=result.get("ending_direction") or outline.ending_direction,
        )

        return expanded

    # ── 辅助方法 ──────────────────────────────────────────────────

    def _build_knowledge_base_summary(self, knowledge_base: dict) -> str:
        """
        构建知识库摘要文本

        Args:
            knowledge_base: 知识库内容

        Returns:
            摘要文本
        """
        parts = []

        characters = knowledge_base.get("characters", [])
        if characters:
            char_names = [c.get("name", "?") for c in characters[:20]]
            parts.append(f"已知人物（{len(characters)}人）：{'、'.join(char_names)}")

            # 主要人物详细信息
            main_chars = [
                c for c in characters
                if "主角" in (c.get("role_tags") or [])
                or "女主" in (c.get("role_tags") or [])
                or "男主" in (c.get("role_tags") or [])
            ][:5]
            if main_chars:
                for c in main_chars:
                    identity = c.get("identity") or "未知"
                    personality = c.get("personality") or ""
                    parts.append(
                        f"  - {c['name']}：{identity}"
                        + (f"，{personality}" if personality else "")
                    )

        settings = knowledge_base.get("settings", [])
        if settings:
            setting_names = [s.get("name", "?") for s in settings[:15]]
            parts.append(f"已知设定（{len(settings)}个）：{'、'.join(setting_names)}")

        events = knowledge_base.get("events", [])
        if events:
            event_names = [e.get("name", "?") for e in events[:20]]
            parts.append(f"已知事件（{len(events)}个）：{'、'.join(event_names)}")

            # 事件因果链
            event_causes = []
            for e in events[:10]:
                cause = e.get("cause") or []
                if cause:
                    event_causes.append(f"{e.get('name', '?')} <- {', '.join(cause)}")
            if event_causes:
                parts.append(f"事件因果链：{'；'.join(event_causes[:5])}")

        return "\n".join(parts) if parts else "（暂无知识库信息）"

    def _build_timeline_summary(self, timeline: List[dict]) -> str:
        """
        构建时间线摘要文本

        Args:
            timeline: 事件时间线

        Returns:
            摘要文本
        """
        parts = []

        for i, event in enumerate(timeline, 1):
            name = event.get("name", f"事件{i}")
            time = event.get("time") or "未知时间"
            participants = event.get("participants") or []
            location = event.get("location") or ""
            description = event.get("description") or ""

            line = f"{i}. {name}（{time}）"
            if participants:
                line += f" - 参与者：{'、'.join(participants)}"
            if location:
                line += f" - 地点：{location}"
            if description:
                line += f" - {description[:50]}"

            parts.append(line)

        return "\n".join(parts) if parts else "（时间线为空）"

    def _call_api(self, system_prompt: str, user_message: str) -> str:
        """
        调用 AI API（委托给 api_client.call_api，支持 config 覆盖）。

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息

        Returns:
            API 响应文本
        """
        return call_api(
            system_prompt,
            user_message,
            api_key=self.config.get("api_key", DEEPSEEK_API_KEY),
            base_url=self.config.get("base_url", DEEPSEEK_BASE_URL),
            model=self.config.get("model", DEEPSEEK_MODEL),
        )


# ── 工具函数 ──────────────────────────────────────────────────

def create_plot_generator(config: dict = None) -> PlotGenerator:
    """
    创建情节生成器实例的工厂函数

    Args:
        config: 配置字典

    Returns:
        PlotGenerator 实例
    """
    return PlotGenerator(config)


def analyze_timeline_for_gaps(
    timeline: List[dict],
    knowledge_base: dict,
    config: dict = None,
) -> List[dict]:
    """
    分析时间线并识别情节空白的便捷函数

    Args:
        timeline: 事件时间线
        knowledge_base: 知识库内容
        config: 配置字典

    Returns:
        情节空白列表
    """
    generator = create_plot_generator(config)
    return generator.identify_gaps(timeline, knowledge_base)


def generate_plot_outline(
    book_title: str,
    knowledge_base: dict,
    config: dict = None,
) -> PlotOutline:
    """
    生成情节大纲的便捷函数

    Args:
        book_title: 作品标题
        knowledge_base: 知识库内容
        config: 配置字典

    Returns:
        情节大纲对象
    """
    generator = create_plot_generator(config)
    return generator.generate_outline(book_title, knowledge_base)
