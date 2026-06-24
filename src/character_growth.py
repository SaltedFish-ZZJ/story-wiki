"""
Story Wiki - 角色成长曲线模块
追踪人物状态随时间/章节的变化，记录关键成长事件，生成成长曲线数据。
支持AI分析、成长阶段划分、Mermaid可视化。
"""
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.interfaces import (
    Character,
    GrowthEvent,
    CharacterGrowthCurve,
    Event,
)
from src.config import VAULT_DIR
from src.utils import safe_filename as _safe_filename, today_str as _today
from src.vault_manager import VaultManager

# ── 成长事件类型定义 ──
GROWTH_TYPES = {
    "实力": "能力、武力、法力等实力提升",
    "地位": "社会地位、官职、声望变化",
    "情感": "情感状态、爱情、友情变化",
    "认知": "知识、智慧、认知水平提升",
    "关系": "人际关系网络变化",
    "性格": "性格特征、价值观变化",
    "命运": "命运转折、人生轨迹变化",
}


class CharacterGrowthTracker:
    """
    角色成长追踪器，负责：
    1. 从章节分析结果中提取成长事件
    2. 存储成长事件到知识库
    3. 生成成长曲线数据
    4. 可视化成长轨迹
    """

    def __init__(self, vault_dir: Path = None, book_title: str = ""):
        """
        初始化成长追踪器。

        Args:
            vault_dir: Vault 根目录
            book_title: 作品标题
        """
        self.vault_dir = vault_dir or VAULT_DIR
        self.book_title = book_title
        self.vault_manager = VaultManager({
            "vault_dir": str(self.vault_dir),
            "book_title": book_title
        })

    def extract_growth_events_from_analysis(
        self,
        analysis_result: dict,
        chapter: str = ""
    ) -> List[GrowthEvent]:
        """
        从章节分析结果中提取成长事件。

        Args:
            analysis_result: 分析结果字典
            chapter: 章节标识

        Returns:
            成长事件列表
        """
        growth_events = []

        # 提取人物信息
        characters = analysis_result.get("characters", [])

        for char_data in characters:
            char_name = char_data.get("name", "")
            if not char_name:
                continue

            # 检查是否有成长相关的变化
            # 1. 从 current_state 中提取
            current_state = char_data.get("current_state", "")
            if current_state:
                event = GrowthEvent(
                    chapter=chapter,
                    time=analysis_result.get("summary", ""),
                    event_name=f"{char_name}状态更新",
                    description=current_state,
                    state_before="",
                    state_after=current_state,
                    growth_type="状态",
                    significance="中"
                )
                growth_events.append(event)

            # 2. 从事件中提取成长事件
            events = analysis_result.get("events", [])
            for event_data in events:
                participants = event_data.get("participants", [])
                if char_name in participants:
                    # 检查事件重要性
                    importance = event_data.get("importance", "普通")
                    if importance in ["高", "重要"]:
                        event = GrowthEvent(
                            chapter=chapter,
                            time=event_data.get("time", ""),
                            event_name=event_data.get("name", ""),
                            description=event_data.get("description", ""),
                            state_before="",
                            state_after="",
                            growth_type=self._infer_growth_type(event_data),
                            significance="高" if importance == "高" else "中"
                        )
                        growth_events.append(event)

            # 3. 从关系变化中提取
            relationships = char_data.get("relationships", [])
            for rel in relationships:
                target = rel.get("target", "")
                nature = rel.get("nature", "")
                if target and nature:
                    event = GrowthEvent(
                        chapter=chapter,
                        time="",
                        event_name=f"{char_name}与{target}关系",
                        description=f"关系: {nature}",
                        state_before="",
                        state_after=f"与{target}: {nature}",
                        growth_type="关系",
                        significance="中"
                    )
                    growth_events.append(event)

        return growth_events

    def _infer_growth_type(self, event_data: dict) -> str:
        """从事件描述推断成长类型。"""
        name = event_data.get("name", "")
        description = event_data.get("description", "")
        combined = name + description

        # 关键词匹配（按优先级排序）
        keywords = {
            "认知": ["领悟", "明白", "理解", "悟道", "觉醒", "参透", "顿悟"],
            "情感": ["相恋", "表白", "分离", "重逢", "思念", "爱", "相思", "情"],
            "地位": ["封赏", "加冕", "登基", "升迁", "任命", "册封", "加官", "封王"],
            "关系": ["结盟", "背叛", "和解", "决裂", "合作", "断交", "和好"],
            "实力": ["修炼", "突破", "战胜", "击败", "升级", "晋升", "功力", "修为"],
        }

        for growth_type, kw_list in keywords.items():
            for kw in kw_list:
                if kw in combined:
                    return growth_type

        return "其他"

    def save_growth_events(
        self,
        character_name: str,
        growth_events: List[GrowthEvent]
    ):
        """
        保存成长事件到人物卡片。

        Args:
            character_name: 人物名称
            growth_events: 成长事件列表
        """
        if not growth_events:
            return

        # 加载现有人物
        character = self.vault_manager.load_character(character_name)
        if character is None:
            print(f"[警告] 人物不存在: {character_name}")
            return

        # 合并成长事件（避免重复）
        existing_events = character.growth_events or []
        existing_event_names = {e.event_name for e in existing_events}

        for event in growth_events:
            if event.event_name not in existing_event_names:
                existing_events.append(event)
                existing_event_names.add(event.event_name)

        # 按章节排序
        existing_events.sort(key=lambda e: e.chapter)

        # 更新人物
        updates = {
            "growth_events": [self._growth_event_to_dict(e) for e in existing_events]
        }
        self.vault_manager.update_character(character_name, updates)

    def _growth_event_to_dict(self, event: GrowthEvent) -> dict:
        """将 GrowthEvent 转为字典。"""
        return {
            "chapter": event.chapter,
            "time": event.time,
            "event_name": event.event_name,
            "description": event.description,
            "state_before": event.state_before,
            "state_after": event.state_after,
            "growth_type": event.growth_type,
            "significance": event.significance,
        }

    def _dict_to_growth_event(self, d: dict) -> GrowthEvent:
        """将字典转为 GrowthEvent。"""
        return GrowthEvent(
            chapter=d.get("chapter", ""),
            time=d.get("time", ""),
            event_name=d.get("event_name", ""),
            description=d.get("description", ""),
            state_before=d.get("state_before", ""),
            state_after=d.get("state_after", ""),
            growth_type=d.get("growth_type", ""),
            significance=d.get("significance", "中"),
        )

    def get_character_growth_curve(
        self,
        character_name: str
    ) -> Optional[CharacterGrowthCurve]:
        """
        获取角色成长曲线。

        Args:
            character_name: 人物名称

        Returns:
            成长曲线对象
        """
        # 加载人物
        character = self.vault_manager.load_character(character_name)
        if character is None:
            return None

        # 获取成长事件
        growth_events = character.growth_events or []
        if not growth_events:
            return CharacterGrowthCurve(
                character_name=character_name,
                growth_events=[],
                summary=f"{character_name}暂无成长记录",
                growth_phases=[],
                overall_trend="无数据"
            )

        # 分析成长阶段
        growth_phases = self._analyze_growth_phases(growth_events)

        # 生成趋势描述
        overall_trend = self._generate_trend_description(growth_events, growth_phases)

        # 生成摘要
        summary = self._generate_growth_summary(character_name, growth_events, growth_phases)

        return CharacterGrowthCurve(
            character_name=character_name,
            growth_events=growth_events,
            summary=summary,
            growth_phases=growth_phases,
            overall_trend=overall_trend,
        )

    def _analyze_growth_phases(self, events: List[GrowthEvent]) -> List[dict]:
        """分析成长阶段。"""
        if not events:
            return []

        phases = []
        # 按成长类型分组
        type_groups = {}
        for event in events:
            growth_type = event.growth_type
            if growth_type not in type_groups:
                type_groups[growth_type] = []
            type_groups[growth_type].append(event)

        # 为每种类型创建阶段
        for growth_type, type_events in type_groups.items():
            phase = {
                "start_chapter": type_events[0].chapter,
                "end_chapter": type_events[-1].chapter,
                "type": growth_type,
                "events_count": len(type_events),
                "high_significance_count": sum(1 for e in type_events if e.significance == "高"),
                "description": f"{growth_type}成长阶段"
            }
            phases.append(phase)

        return phases

    def _generate_trend_description(
        self,
        events: List[GrowthEvent],
        phases: List[dict]
    ) -> str:
        """生成趋势描述。"""
        if not events:
            return "无数据"

        # 统计各类型事件数量
        type_counts = {}
        for event in events:
            growth_type = event.growth_type
            type_counts[growth_type] = type_counts.get(growth_type, 0) + 1

        # 找出主要成长类型
        main_type = max(type_counts, key=type_counts.get)
        main_count = type_counts[main_type]

        # 高重要性事件数量
        high_sig_count = sum(1 for e in events if e.significance == "高")

        if high_sig_count > 0:
            return f"经历{len(events)}个成长事件，其中{high_sig_count}个关键转折点，主要在{main_type}方面成长"
        else:
            return f"经历{len(events)}个成长事件，主要在{main_type}方面发展"

    def _generate_growth_summary(
        self,
        character_name: str,
        events: List[GrowthEvent],
        phases: List[dict]
    ) -> str:
        """生成成长摘要。"""
        if not events:
            return f"{character_name}暂无成长记录"

        # 获取起止章节
        first_chapter = events[0].chapter
        last_chapter = events[-1].chapter

        # 统计成长类型
        type_counts = {}
        for event in events:
            growth_type = event.growth_type
            type_counts[growth_type] = type_counts.get(growth_type, 0) + 1

        type_desc = "、".join([f"{t}({c})" for t, c in type_counts.items()])

        return (
            f"{character_name}从{first_chapter}到{last_chapter}共经历{len(events)}个成长事件，"
            f"涉及{type_desc}等方面"
        )

    def generate_growth_chart_data(
        self,
        character_name: str
    ) -> Dict[str, Any]:
        """
        生成成长曲线图表数据。

        Args:
            character_name: 人物名称

        Returns:
            图表数据字典
        """
        curve = self.get_character_growth_curve(character_name)
        if curve is None:
            return {"error": f"人物不存在: {character_name}"}

        # 按章节分组
        chapter_events = {}
        for event in curve.growth_events:
            chapter = event.chapter or "未知"
            if chapter not in chapter_events:
                chapter_events[chapter] = []
            chapter_events[chapter].append({
                "name": event.event_name,
                "type": event.growth_type,
                "significance": event.significance,
                "description": event.description,
            })

        # 生成时间线数据
        timeline = []
        for chapter, events in sorted(chapter_events.items()):
            timeline.append({
                "chapter": chapter,
                "events": events,
                "total": len(events),
                "high_significance": sum(1 for e in events if e.get("significance") == "高"),
            })

        return {
            "character_name": character_name,
            "summary": curve.summary,
            "overall_trend": curve.overall_trend,
            "timeline": timeline,
            "growth_phases": curve.growth_phases,
            "total_events": len(curve.growth_events),
        }


# ── 核心函数（按任务要求） ──

def analyze_character_growth(
    character_name: str,
    knowledge_base: dict,
    use_ai: bool = True
) -> CharacterGrowthCurve:
    """
    分析角色成长事件，使用AI进行深度分析。

    Args:
        character_name: 角色名称
        knowledge_base: 知识库数据，包含 characters, events, settings
        use_ai: 是否使用AI进行分析（默认True）

    Returns:
        CharacterGrowthCurve 对象

    Raises:
        ValueError: 当角色不存在时
    """
    # 从知识库中查找角色
    character_data = None
    for char in knowledge_base.get("characters", []):
        if char.get("name") == character_name:
            character_data = char
            break

    if character_data is None:
        raise ValueError(f"角色 '{character_name}' 在知识库中不存在")

    # 提取角色相关的事件
    all_events = knowledge_base.get("events", [])
    growth_events = extract_growth_events(all_events, character_name)

    # 如果启用AI分析，使用AI进行深度成长分析
    if use_ai:
        growth_events = _ai_analyze_growth_events(character_name, growth_events, knowledge_base)

    # 划分成长阶段
    growth_phases = 划分成长阶段(growth_events)

    # 生成成长曲线
    growth_curve = generate_growth_curve(
        character_name=character_name,
        growth_events=growth_events,
        growth_phases=growth_phases
    )

    return growth_curve


def extract_growth_events(
    events: List[Event],
    character_name: str
) -> List[GrowthEvent]:
    """
    从事件列表中提取与特定角色相关的成长事件。

    Args:
        events: 事件列表（Event对象或dict）
        character_name: 角色名称

    Returns:
        成长事件列表
    """
    growth_events = []

    for event in events:
        # 支持Event对象和dict两种格式
        if isinstance(event, Event):
            participants = event.participants or []
            event_name = event.name
            event_time = event.time
            event_desc = event.description
            event_chapter = event.chapter
            event_importance = event.importance
        elif isinstance(event, dict):
            participants = event.get("participants", [])
            event_name = event.get("name", "")
            event_time = event.get("time", "")
            event_desc = event.get("description", "")
            event_chapter = event.get("chapter", "")
            event_importance = event.get("importance", "普通")
        else:
            continue

        # 检查角色是否参与该事件
        if character_name in participants:
            # 分类成长类型
            event_dict = event if isinstance(event, dict) else {
                "name": event_name,
                "description": event_desc
            }
            growth_type = classify_growth_type(event_dict)

            # 确定重要性
            significance = "高" if event_importance in ["高", "重要"] else "中"

            growth_event = GrowthEvent(
                event_name=event_name,
                chapter=event_chapter,
                time=event_time,
                description=event_desc,
                state_before="",
                state_after="",
                growth_type=growth_type,
                significance=significance
            )
            growth_events.append(growth_event)

    # 按章节排序
    growth_events.sort(key=lambda e: e.chapter)

    return growth_events


def classify_growth_type(event: dict) -> str:
    """
    分类成长类型（实力/地位/情感/认知/关系）。

    Args:
        event: 事件字典，包含 name 和 description 字段

    Returns:
        成长类型字符串
    """
    name = event.get("name", "")
    description = event.get("description", "")
    combined = name + description

    # 关键词匹配（按优先级排序）
    keywords = {
        "认知": ["领悟", "明白", "理解", "悟道", "觉醒", "参透", "顿悟", "学习", "思考"],
        "情感": ["相恋", "表白", "分离", "重逢", "思念", "爱", "相思", "情", "感动", "悲伤", "喜悦"],
        "地位": ["封赏", "加冕", "登基", "升迁", "任命", "册封", "加官", "封王", "晋升", "成为"],
        "关系": ["结盟", "背叛", "和解", "决裂", "合作", "断交", "和好", "相识", "相知", "分离"],
        "实力": ["修炼", "突破", "战胜", "击败", "升级", "晋升", "功力", "修为", "变强", "成长"],
        "性格": ["改变", "转变", "觉醒", "领悟", "成长", "成熟", "改变想法"],
        "命运": ["命运", "转折", "机遇", "危机", "改变命运", "宿命"],
    }

    for growth_type, kw_list in keywords.items():
        for kw in kw_list:
            if kw in combined:
                return growth_type

    return "其他"


def 划分成长阶段(growth_events: List[GrowthEvent]) -> List[dict]:
    """
    将成长事件划分为不同阶段。

    根据事件的章节和成长类型，将事件划分为不同的成长阶段。

    Args:
        growth_events: 成长事件列表

    Returns:
        成长阶段列表，每个阶段包含：
        - start_chapter: 起始章节
        - end_chapter: 结束章节
        - type: 阶段类型
        - events_count: 事件数量
        - high_significance_count: 高重要性事件数量
        - description: 阶段描述
    """
    if not growth_events:
        return []

    # 按章节排序
    sorted_events = sorted(growth_events, key=lambda e: e.chapter)

    # 按成长类型分组
    type_groups: Dict[str, List[GrowthEvent]] = {}
    for event in sorted_events:
        growth_type = event.growth_type
        if growth_type not in type_groups:
            type_groups[growth_type] = []
        type_groups[growth_type].append(event)

    phases = []

    # 为每种成长类型创建阶段
    for growth_type, type_events in type_groups.items():
        # 按章节排序
        type_events.sort(key=lambda e: e.chapter)

        # 计算阶段统计
        chapters = [e.chapter for e in type_events if e.chapter]
        start_chapter = chapters[0] if chapters else ""
        end_chapter = chapters[-1] if chapters else ""

        high_sig_count = sum(1 for e in type_events if e.significance == "高")

        # 生成阶段描述
        if len(type_events) == 1:
            description = f"{growth_type}成长：{type_events[0].event_name}"
        else:
            description = f"{growth_type}成长阶段（{len(type_events)}个事件）"

        phase = {
            "start_chapter": start_chapter,
            "end_chapter": end_chapter,
            "type": growth_type,
            "events_count": len(type_events),
            "high_significance_count": high_sig_count,
            "description": description,
            "events": [e.event_name for e in type_events]
        }
        phases.append(phase)

    # 按起始章节排序
    phases.sort(key=lambda p: p["start_chapter"])

    return phases


def generate_growth_curve(
    character_name: str,
    growth_events: List[GrowthEvent],
    growth_phases: Optional[List[dict]] = None
) -> CharacterGrowthCurve:
    """
    生成成长曲线数据。

    Args:
        character_name: 角色名称
        growth_events: 成长事件列表
        growth_phases: 成长阶段列表（可选，如果不提供则自动计算）

    Returns:
        CharacterGrowthCurve 对象
    """
    # 如果未提供阶段，则自动划分
    if growth_phases is None:
        growth_phases = 划分成长阶段(growth_events)

    # 生成整体趋势描述
    overall_trend = _generate_overall_trend(growth_events, growth_phases)

    # 生成摘要
    summary = _generate_summary(character_name, growth_events, growth_phases)

    return CharacterGrowthCurve(
        character_name=character_name,
        growth_events=growth_events,
        summary=summary,
        growth_phases=growth_phases,
        overall_trend=overall_trend,
    )


def _generate_overall_trend(
    growth_events: List[GrowthEvent],
    growth_phases: List[dict]
) -> str:
    """生成整体趋势描述。"""
    if not growth_events:
        return "无数据"

    # 统计各类型事件数量
    type_counts: Dict[str, int] = {}
    for event in growth_events:
        growth_type = event.growth_type
        type_counts[growth_type] = type_counts.get(growth_type, 0) + 1

    # 找出主要成长类型
    main_type = max(type_counts, key=type_counts.get)
    main_count = type_counts[main_type]

    # 高重要性事件数量
    high_sig_count = sum(1 for e in growth_events if e.significance == "高")

    # 阶段数量
    phase_count = len(growth_phases)

    if high_sig_count > 0:
        trend = f"经历{len(growth_events)}个成长事件，其中{high_sig_count}个关键转折点"
    else:
        trend = f"经历{len(growth_events)}个成长事件"

    trend += f"，主要在{main_type}方面成长"
    if phase_count > 1:
        trend += f"，经历{phase_count}个成长阶段"

    return trend


def _generate_summary(
    character_name: str,
    growth_events: List[GrowthEvent],
    growth_phases: List[dict]
) -> str:
    """生成成长摘要。"""
    if not growth_events:
        return f"{character_name}暂无成长记录"

    # 获取起止章节
    chapters = [e.chapter for e in growth_events if e.chapter]
    if chapters:
        first_chapter = chapters[0]
        last_chapter = chapters[-1]
    else:
        first_chapter = "未知"
        last_chapter = "未知"

    # 统计成长类型
    type_counts: Dict[str, int] = {}
    for event in growth_events:
        growth_type = event.growth_type
        type_counts[growth_type] = type_counts.get(growth_type, 0) + 1

    type_desc = "、".join([f"{t}({c})" for t, c in type_counts.items()])

    # 阶段描述
    phase_desc = ""
    if growth_phases:
        phase_types = [p["type"] for p in growth_phases]
        phase_desc = f"，经历{', '.join(set(phase_types))}等阶段"

    return (
        f"{character_name}从{first_chapter}到{last_chapter}共经历{len(growth_events)}个成长事件，"
        f"涉及{type_desc}等方面{phase_desc}"
    )


def render_growth_mermaid(
    growth_curve: CharacterGrowthCurve,
    title: Optional[str] = None
) -> str:
    """
    生成Mermaid timeline可视化代码。

    Args:
        growth_curve: 成长曲线对象
        title: 图表标题（可选）

    Returns:
        Mermaid timeline语法的字符串
    """
    if not title:
        title = f"{growth_curve.character_name}成长曲线"

    # Mermaid timeline 语法
    mermaid_lines = ["```mermaid", "timeline"]
    mermaid_lines.append(f"    title {title}")

    # 按章节分组事件
    chapter_events: Dict[str, List[GrowthEvent]] = {}
    for event in growth_curve.growth_events:
        chapter = event.chapter or "未知章节"
        if chapter not in chapter_events:
            chapter_events[chapter] = []
        chapter_events[chapter].append(event)

    # 按章节排序
    sorted_chapters = sorted(chapter_events.keys())

    for chapter in sorted_chapters:
        events = chapter_events[chapter]
        mermaid_lines.append(f"    section {chapter}")

        for event in events:
            # 根据成长类型添加不同标签
            type_label = _get_type_emoji(event.growth_type)
            significance_label = "★" if event.significance == "高" else ""

            # 事件描述（截断过长文本）
            desc = event.event_name
            if len(desc) > 30:
                desc = desc[:27] + "..."

            mermaid_lines.append(f"        {type_label} {desc} {significance_label}")

    # 添加成长阶段总结
    if growth_curve.growth_phases:
        mermaid_lines.append("    section 成长总结")
        for phase in growth_curve.growth_phases:
            phase_desc = phase.get("description", "")
            if phase_desc:
                mermaid_lines.append(f"        {phase_desc}")

    mermaid_lines.append("```")

    return "\n".join(mermaid_lines)


def _get_type_emoji(growth_type: str) -> str:
    """根据成长类型返回对应的标签（兼容非emoji环境）。"""
    emoji_map = {
        "实力": "[实力]",
        "地位": "[地位]",
        "情感": "[情感]",
        "认知": "[认知]",
        "关系": "[关系]",
        "性格": "[性格]",
        "命运": "[命运]",
        "状态": "[状态]",
        "其他": "[其他]",
    }
    return emoji_map.get(growth_type, "[其他]")


# ── AI分析辅助函数 ──

def _ai_analyze_growth_events(
    character_name: str,
    growth_events: List[GrowthEvent],
    knowledge_base: dict
) -> List[GrowthEvent]:
    """
    使用AI分析并补充成长事件。

    Args:
        character_name: 角色名称
        growth_events: 已提取的成长事件
        knowledge_base: 知识库数据

    Returns:
        增强后的成长事件列表
    """
    try:
        from src.analyzer import _call_deepseek_with_prompt
    except ImportError:
        # 如果无法导入AI模块，返回原始事件
        print("[警告] 无法导入AI模块，跳过AI分析")
        return growth_events

    # 如果没有事件，返回空列表
    if not growth_events:
        return growth_events

    # 构建分析提示
    events_text = "\n".join([
        f"- {e.event_name}: {e.description} (类型: {e.growth_type}, 重要性: {e.significance})"
        for e in growth_events
    ])

    system_prompt = f"""你是一个专业的文学分析师。请分析角色"{character_name}"的成长事件。

任务：
1. 检查现有成长事件的分类是否准确
2. 分析事件之间的因果关系
3. 评估每个事件对角色成长的重要性
4. 提供成长趋势分析

请用JSON格式返回分析结果，包含以下字段：
{{
    "events_analysis": [
        {{
            "event_name": "事件名称",
            "suggested_type": "建议的成长类型",
            "significance": "高/中/低",
            "impact": "对角色成长的影响"
        }}
    ],
    "growth_trend": "整体成长趋势描述",
    "key_turning_points": ["关键转折点列表"]
}}"""

    user_content = f"""角色: {character_name}

现有成长事件:
{events_text}

请分析这些成长事件。"""

    try:
        response = _call_deepseek_with_prompt(system_prompt, user_content)

        # 解析AI响应
        from src.utils import parse_ai_response
        analysis = parse_ai_response(response)

        # 根据AI分析结果更新事件
        events_analysis = analysis.get("events_analysis", [])
        for ai_analysis in events_analysis:
            event_name = ai_analysis.get("event_name", "")
            suggested_type = ai_analysis.get("suggested_type", "")
            suggested_significance = ai_analysis.get("significance", "")

            # 查找匹配的事件并更新
            for event in growth_events:
                if event.event_name == event_name:
                    if suggested_type and suggested_type in GROWTH_TYPES:
                        event.growth_type = suggested_type
                    if suggested_significance:
                        event.significance = suggested_significance
                    break

        print(f"[AI分析] 已分析 {character_name} 的 {len(growth_events)} 个成长事件")

    except Exception as e:
        print(f"[警告] AI分析失败: {e}")
        # AI分析失败时返回原始事件

    return growth_events


# ── 辅助函数 ──

def extract_growth_from_chapter_analysis(
    chapter_content: dict,
    chapter_num: int
) -> List[GrowthEvent]:
    """
    从章节内容中提取成长事件。

    Args:
        chapter_content: 章节内容字典
        chapter_num: 章节号

    Returns:
        成长事件列表
    """
    tracker = CharacterGrowthTracker()
    chapter_str = f"第{chapter_num}章"

    return tracker.extract_growth_events_from_analysis(
        chapter_content,
        chapter=chapter_str
    )


def batch_extract_growth_events(
    vault_dir: Path,
    book_title: str,
    chapter_analyses: List[dict]
) -> Dict[str, List[GrowthEvent]]:
    """
    批量提取章节分析中的成长事件。

    Args:
        vault_dir: Vault 目录
        book_title: 作品标题
        chapter_analyses: 章节分析结果列表

    Returns:
        人物名称 -> 成长事件列表
    """
    tracker = CharacterGrowthTracker(vault_dir, book_title)
    character_events: Dict[str, List[GrowthEvent]] = {}

    for i, analysis in enumerate(chapter_analyses):
        chapter_str = f"第{i + 1}章"
        events = tracker.extract_growth_events_from_analysis(analysis, chapter_str)

        for event in events:
            # 从事件名称中提取人物名
            char_name = event.event_name.split("状态更新")[0].split("与")[0]
            if char_name not in character_events:
                character_events[char_name] = []
            character_events[char_name].append(event)

    return character_events


def save_all_growth_events(
    vault_dir: Path,
    book_title: str,
    character_events: Dict[str, List[GrowthEvent]]
):
    """
    保存所有成长事件到知识库。

    Args:
        vault_dir: Vault 目录
        book_title: 作品标题
        character_events: 人物 -> 成长事件字典
    """
    tracker = CharacterGrowthTracker(vault_dir, book_title)

    for char_name, events in character_events.items():
        if events:
            tracker.save_growth_events(char_name, events)
            print(f"[成长曲线] 已保存 {char_name} 的 {len(events)} 个成长事件")
