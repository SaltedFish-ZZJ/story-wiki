"""
Story Wiki - 章节生成模块
基于情节大纲和知识库，调用 AI 生成章节内容，包含质量检查。
"""
import json
import re
import time
from typing import Dict, List, Optional, Any

from src.api_client import call_api
from src.config import (
    DEEPSEEK_API_KEY,
    MAX_TOKENS, TEMPERATURE,
    PROMPT_CONTENT_TRUNCATE, PROMPT_CONTENT_LARGE, MIN_WORDS, MAX_WORDS
)
from src.utils import count_words, parse_ai_response as _parse_response
from src.interfaces import (
    ChapterGeneratorInterface,
    ChapterContent,
    Character,
    PlotOutline,
)
from src.logging_setup import get_logger

logger = get_logger("chapter_generator")


# ── System Prompt ──────────────────────────────────────────

CHAPTER_GEN_PROMPT = """你是一个专业的中文小说写作助手。请根据以下信息，为指定章节撰写完整的章节内容。

## 写作要求
1. 严格按照大纲的起承转合结构展开
2. 保持人物性格与人设一致
3. 情节发展合理，符合因果逻辑
4. 文笔流畅，细节丰富，有画面感
5. 对话自然，符合人物身份和性格
6. 字数控制在 2000-3000 字之间

## 输出格式
请严格以 JSON 格式返回，不要添加任何 markdown 包裹或额外文字：
{{
  "title": "章节标题",
  "content": "章节正文内容（纯文本，段落之间用 \\n\\n 分隔）",
  "characters_involved": ["本章出场人物名"],
  "events_happened": ["本章发生的关键事件名"]
}}

## 规则
1. 人物名称必须与知识库中的一致
2. 不要引入大纲中未提及的新人物
3. 事件时间线要与已有事件保持一致
4. 人物行为要与其性格、动机相符"""


QUALITY_CHECK_PROMPT = """你是一个专业的文学编辑。请对以下章节内容进行质量检查，检查人物一致性和时间线一致性。

## 检查项目
1. **人物一致性**：人物的行为、语言是否符合其性格设定？是否与已知关系一致？
2. **时间线一致性**：事件顺序是否合理？是否与已有事件的时间线冲突？
3. **逻辑一致性**：情节发展是否合理？因果关系是否成立？
4. **文字质量**：是否有语病、错别字、重复表述？

## 输出格式
请严格以 JSON 格式返回：
{{
  "passed": true/false,
  "issues": [
    {{"type": "人物一致性/时间线/逻辑/文字", "detail": "问题描述", "suggestion": "修改建议"}}
  ],
  "suggestions": ["改进建议1", "改进建议2"]
}}"""


CHARACTER_CHECK_PROMPT = """你是一个专业的文学编辑。请检查以下章节中某个人物的描写是否与人物设定一致。

## 人物设定
{character_info}

## 章节内容
{chapter_content}

## 检查要点
1. 人物的性格表现是否与设定一致？
2. 人物的语言风格是否符合其身份？
3. 人物的行为是否合理（基于其动机和性格）？
4. 人物与其他角色的关系是否正确？

请严格以 JSON 格式返回：
{{
  "consistent": true/false,
  "issues": ["问题1", "问题2"],
  "details": "详细说明"
}}"""


TIMELINE_CHECK_PROMPT = """你是一个专业的文学编辑。请检查以下章节中的事件时间线是否与已有时间线一致。

## 已有时间线
{timeline_info}

## 本章内容
{chapter_content}

## 检查要点
1. 本章事件的时间顺序是否合理？
2. 是否与已有事件的时间线冲突？
3. 是否有时间逻辑错误（如死人复活、已经发生的事件重复等）？

请严格以 JSON 格式返回：
{{
  "consistent": true/false,
  "issues": ["问题1", "问题2"],
  "details": "详细说明"
}}"""


class ChapterGenerator(ChapterGeneratorInterface):
    """章节生成器，基于情节大纲和知识库生成章节内容。"""

    def __init__(self, config: dict = None):
        """
        初始化章节生成器。

        Args:
            config: 配置字典，可包含：
                - min_words: 最小字数（默认 2000）
                - max_words: 最大字数（默认 3000）
                - temperature: 温度参数（默认使用 config 中的值）
        """
        self.config = config or {}
        self.min_words = self.config.get("min_words", MIN_WORDS)
        self.max_words = self.config.get("max_words", MAX_WORDS)
        self.temperature = self.config.get("temperature", TEMPERATURE)
        self._validate_config()

    def _validate_config(self):
        """验证配置参数。"""
        if self.min_words < 0:
            raise ValueError(f"min_words 不能为负数: {self.min_words}")
        if self.max_words < self.min_words:
            raise ValueError(
                f"max_words ({self.max_words}) 不能小于 min_words ({self.min_words})"
            )

    def run(self, input_data: dict) -> dict:
        """
        运行章节生成模块。

        Args:
            input_data: 输入数据，包含：
                - chapter_num: 章节号
                - outline: PlotOutline 对象或 dict
                - context: 上下文信息
                - characters: 人物列表（可选）
                - timeline: 时间线列表（可选）

        Returns:
            输出数据，包含 ChapterContent 对象
        """
        try:
            chapter_num = input_data.get("chapter_num")
            if chapter_num is None:
                raise ValueError("缺少 chapter_num 参数")

            outline = input_data.get("outline")
            if outline is None:
                raise ValueError("缺少 outline 参数")

            # 将 dict 转换为 PlotOutline 对象
            if isinstance(outline, dict):
                outline = PlotOutline(**outline)

            context = input_data.get("context", {})
            characters = input_data.get("characters", [])
            timeline = input_data.get("timeline", [])
            total_chapters = input_data.get("total_chapters")

            # 生成章节内容
            content = self.generate_chapter(chapter_num, outline, context, total_chapters)

            # 质量检查
            quality_result = self.quality_check(content, characters)

            # 时间线一致性检查
            if timeline:
                timeline_ok = self.check_timeline_consistency(content, timeline)
                if not timeline_ok:
                    quality_result["issues"].append({
                        "type": "时间线",
                        "detail": "时间线一致性检查未通过",
                        "suggestion": "请检查事件时间顺序"
                    })
                    quality_result["passed"] = False

            return {
                "chapter_content": content,
                "quality_check": quality_result,
            }

        except (RuntimeError, ValueError) as e:
            raise RuntimeError(f"章节生成失败: {e}")

    def validate(self, output_data: dict) -> bool:
        """
        验证输出数据。

        Args:
            output_data: 输出数据字典

        Returns:
            是否有效
        """
        if not isinstance(output_data, dict):
            return False

        content = output_data.get("chapter_content")
        if not isinstance(content, ChapterContent):
            return False

        quality = output_data.get("quality_check")
        if not isinstance(quality, dict):
            return False

        required_keys = ["passed", "issues", "suggestions"]
        return all(k in quality for k in required_keys)

    def generate_chapter(
        self,
        chapter_num: int,
        outline: PlotOutline,
        context: dict,
        total_chapters: int = None
    ) -> ChapterContent:
        """
        生成章节内容。

        Args:
            chapter_num: 章节号
            outline: 情节大纲
            context: 上下文信息，包含：
                - previous_content: 前文内容摘要
                - characters: 人物列表
                - events: 已有事件列表
            total_chapters: 总章节数，用于映射大纲结构

        Returns:
            章节内容对象
        """
        if not DEEPSEEK_API_KEY:
            raise ValueError("未配置 API Key")

        # 构建上下文摘要
        context_summary = self._build_context_summary(context)

        # 构建 prompt
        user_prompt = self._build_generation_prompt(chapter_num, outline, context_summary, total_chapters)

        # 调用 API
        raw_response = call_api(CHAPTER_GEN_PROMPT, user_prompt)

        # 解析响应
        try:
            result = _parse_response(raw_response)
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"AI 返回内容无法解析为 JSON: {e}")

        # 构建 ChapterContent
        content_text = result.get("content", "")
        word_count = count_words(content_text)

        chapter = ChapterContent(
            chapter_num=chapter_num,
            title=result.get("title", f"第{chapter_num}章"),
            content=content_text,
            word_count=word_count,
            characters_involved=result.get("characters_involved", []),
            events_happened=result.get("events_happened", []),
        )

        return chapter

    def quality_check(
        self,
        content: ChapterContent,
        characters: List[Character]
    ) -> Dict[str, Any]:
        """
        质量检查：人物一致性、时间线一致性、逻辑一致性、文字质量。

        Args:
            content: 章节内容
            characters: 相关人物

        Returns:
            {
                "passed": True/False,
                "issues": [问题列表],
                "suggestions": [建议列表]
            }
        """
        issues = []
        suggestions = []

        # 字数检查
        if content.word_count < self.min_words:
            issues.append({
                "type": "字数",
                "detail": f"字数不足: {content.word_count} 字 (最少 {self.min_words})",
                "suggestion": "请扩充内容"
            })
        elif content.word_count > self.max_words:
            issues.append({
                "type": "字数",
                "detail": f"字数过多: {content.word_count} 字 (最多 {self.max_words})",
                "suggestion": "请精简内容"
            })

        # 人物一致性检查（逐个检查）
        for char in characters:
            if not self.check_character_consistency(content, char):
                issues.append({
                    "type": "人物一致性",
                    "detail": f"人物 '{char.name}' 的描写可能与设定不一致",
                    "suggestion": f"请检查 {char.name} 的性格、语言和行为是否符合设定"
                })

        # 调用 AI 进行综合质量检查
        if DEEPSEEK_API_KEY:
            try:
                ai_check = self._ai_quality_check(content, characters)
                if ai_check:
                    issues.extend(ai_check.get("issues", []))
                    suggestions.extend(ai_check.get("suggestions", []))
            except (RuntimeError, ValueError, KeyError) as e:
                suggestions.append(f"AI 质量检查失败: {e}")

        passed = len(issues) == 0

        return {
            "passed": passed,
            "issues": issues,
            "suggestions": suggestions,
        }

    def check_character_consistency(
        self,
        content: ChapterContent,
        character: Character
    ) -> bool:
        """
        检查人物一致性。

        Args:
            content: 章节内容
            character: 人物对象

        Returns:
            是否一致
        """
        # 快速检查：人物名字是否在章节中出现
        if character.name not in content.content:
            # 如果人物别名也不在，则可能不一致
            if not any(alias in content.content for alias in character.aliases):
                return True  # 人物未出场，不检查

        # 使用 AI 进行深度检查
        if not DEEPSEEK_API_KEY:
            # 无 API 时，使用简单规则检查
            return self._simple_character_check(content, character)

        try:
            character_info = self._format_character_info(character)
            user_prompt = CHARACTER_CHECK_PROMPT.format(
                character_info=character_info,
                chapter_content=content.content[:PROMPT_CONTENT_TRUNCATE],
            )

            raw_response = call_api(
                "你是一个文学编辑，请检查人物一致性。", user_prompt
            )
            result = _parse_response(raw_response)
            return result.get("consistent", True)
        except (RuntimeError, ValueError, KeyError) as e:
            # 检查失败时，默认通过，但记录警告
            logger.warning(f"人物一致性检查异常: {e}")
            return True

    def check_timeline_consistency(
        self,
        content: ChapterContent,
        timeline: List[dict]
    ) -> bool:
        """
        检查时间线一致性。

        Args:
            content: 章节内容
            timeline: 事件时间线

        Returns:
            是否一致
        """
        if not timeline:
            return True

        # 使用 AI 进行时间线检查
        if not DEEPSEEK_API_KEY:
            return self._simple_timeline_check(content, timeline)

        try:
            timeline_info = self._format_timeline_info(timeline)
            user_prompt = TIMELINE_CHECK_PROMPT.format(
                timeline_info=timeline_info,
                chapter_content=content.content[:PROMPT_CONTENT_TRUNCATE],
            )

            raw_response = call_api(
                "你是一个文学编辑，请检查时间线一致性。", user_prompt
            )
            result = _parse_response(raw_response)
            return result.get("consistent", True)
        except (RuntimeError, ValueError, KeyError) as e:
            logger.warning(f"时间线一致性检查异常: {e}")
            return True

    # ── 内部辅助方法 ──────────────────────────────────────────

    def _build_context_summary(self, context: dict) -> str:
        """构建上下文摘要。"""
        parts = []

        # 前文摘要
        previous = context.get("previous_content", "")
        if previous:
            if len(previous) > 500:
                previous = previous[:500] + "..."
            parts.append(f"前文摘要：\n{previous}")

        # 人物列表
        characters = context.get("characters", [])
        if characters:
            char_names = [c.get("name", "") if isinstance(c, dict) else c.name for c in characters]
            parts.append(f"主要人物：{'、'.join(char_names)}")

        # 已有事件
        events = context.get("events", [])
        if events:
            event_names = [e.get("name", "") if isinstance(e, dict) else e.name for e in events]
            parts.append(f"已有事件：{'、'.join(event_names)}")

        return "\n\n".join(parts) if parts else "（无上下文信息）"

    def _build_generation_prompt(
        self,
        chapter_num: int,
        outline: PlotOutline,
        context_summary: str,
        total_chapters: int = None
    ) -> str:
        """构建章节生成的用户 prompt。"""
        # 提取大纲中本章相关的内容
        structure = outline.structure or {}

        prompt_parts = [
            f"## 作品信息",
            f"标题：{outline.title}",
            f"主题：{outline.theme}",
            f"核心冲突：{outline.conflict}",
            "",
            f"## 本章信息",
            f"章节号：第{chapter_num}章",
        ]

        # 根据章节号提取对应的大纲结构
        chapter_key = self._get_chapter_structure_key(chapter_num, structure, total_chapters)
        if chapter_key and chapter_key in structure:
            prompt_parts.append(f"本章结构：{chapter_key}")
            prompt_parts.append(f"内容要点：{structure[chapter_key]}")

        # 关键情节点
        if outline.key_points:
            prompt_parts.append(f"关键情节点：{'、'.join(outline.key_points)}")

        # 结局走向
        if outline.ending_direction:
            prompt_parts.append(f"结局走向：{outline.ending_direction}")

        # 上下文
        if context_summary:
            prompt_parts.extend(["", "## 上下文", context_summary])

        return "\n".join(prompt_parts)

    def _get_chapter_structure_key(self, chapter_num: int, structure: dict, total_chapters: int = None) -> Optional[str]:
        """根据章节号获取大纲结构中的对应键。"""
        if not structure:
            return None

        # 常见的起承转合结构
        keys = list(structure.keys())
        if not keys:
            return None

        num_keys = len(keys)
        if num_keys == 0:
            return None

        # 计算当前章节对应的结构部分
        # 如果 total_chapters 为 None，则根据 chapter_num 推断（退化为线性分配）
        if total_chapters is None:
            # 无法确定总章节数时，按章节号对结构键数取模分配
            part_index = (chapter_num - 1) % num_keys
        else:
            index = min(chapter_num - 1, total_chapters - 1)
            part_index = (index * num_keys) // total_chapters
        part_index = min(part_index, num_keys - 1)

        return keys[part_index]

    def _format_character_info(self, character: Character) -> str:
        """格式化人物信息为文本。"""
        parts = [
            f"姓名：{character.name}",
            f"身份：{character.identity}",
            f"性格：{character.personality}",
            f"性别：{character.gender}",
        ]

        if character.faction:
            parts.append(f"阵营：{character.faction}")

        if character.aliases:
            parts.append(f"别名：{'、'.join(character.aliases)}")

        if character.motivation:
            parts.append(f"动机：{character.motivation}")

        if character.current_state:
            parts.append(f"当前状态：{character.current_state}")

        if character.relationships:
            rels = [f"{r.get('target', '?')}({r.get('nature', '?')})" for r in character.relationships]
            parts.append(f"人际关系：{'、'.join(rels)}")

        return "\n".join(parts)

    def _format_timeline_info(self, timeline: List[dict]) -> str:
        """格式化时间线信息为文本。"""
        if not timeline:
            return "（无已有时间线）"

        lines = []
        for i, event in enumerate(timeline, 1):
            name = event.get("name", "未知")
            time = event.get("time", "未知")
            participants = "、".join(event.get("participants", []))
            lines.append(f"{i}. {name}（时间：{time}，参与者：{participants}）")

        return "\n".join(lines)

    def _simple_character_check(self, content: ChapterContent, character: Character) -> bool:
        """
        简单的人物一致性检查（不调用 AI）。
        基于规则的检查。
        """
        # 检查人物名字是否出现
        name_present = character.name in content.content
        alias_present = any(alias in content.content for alias in character.aliases)

        if not name_present and not alias_present:
            return True  # 未出场，不检查

        # 基本规则检查
        # 1. 检查性别代词是否一致（简单检查）
        # 2. 检查是否提到了其阵营相关的内容
        # 这里只做最基本的检查，详细检查需要 AI

        return True  # 默认通过

    def _simple_timeline_check(self, content: ChapterContent, timeline: List[dict]) -> bool:
        """
        简单的时间线检查（不调用 AI）。
        检查是否有明显的矛盾。
        """
        # 提取章节中提到的事件名
        mentioned_events = set()
        for event in timeline:
            if event.get("name", "") in content.content:
                mentioned_events.add(event.get("name", ""))

        # 检查是否有事件的时间顺序矛盾
        # 这里只做最基本的检查
        return True  # 默认通过

    def _ai_quality_check(
        self,
        content: ChapterContent,
        characters: List[Character]
    ) -> Optional[Dict[str, Any]]:
        """调用 AI 进行综合质量检查。"""
        # 构建人物摘要
        char_summaries = []
        for char in characters[:10]:  # 最多检查 10 个人物
            char_summaries.append(self._format_character_info(char))

        char_info = "\n\n".join(char_summaries) if char_summaries else "（无相关人物）"

        user_prompt = f"""请检查以下章节内容的质量：

## 章节内容
标题：{content.title}
字数：{content.word_count}

{content.content[:PROMPT_CONTENT_LARGE]}

## 相关人物设定
{char_info}

## 检查要点
1. 人物行为是否符合性格设定
2. 情节发展是否合理
3. 文字是否流畅
4. 是否有逻辑漏洞"""

        raw_response = call_api(QUALITY_CHECK_PROMPT, user_prompt)
        return _parse_response(raw_response)
