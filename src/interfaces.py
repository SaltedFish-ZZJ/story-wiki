"""
Story Wiki 模块接口规范
所有模块必须实现这些接口，确保模块间的一致性和可替换性。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from src.config import MIN_WORDS, MAX_WORDS


@dataclass
class Character:
    """人物数据结构"""
    name: str
    identity: str = ""
    personality: str = ""
    gender: str = "未知"
    faction: str = ""
    aliases: List[str] = None
    role_tags: List[str] = None
    status: str = "活跃"
    relationships: List[dict] = None
    related_settings: List[str] = None
    quotes: List[str] = None
    motivation: str = ""
    current_state: str = ""
    growth_events: List['GrowthEvent'] = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
        if self.role_tags is None:
            self.role_tags = []
        if self.relationships is None:
            self.relationships = []
        if self.related_settings is None:
            self.related_settings = []
        if self.quotes is None:
            self.quotes = []
        if self.growth_events is None:
            self.growth_events = []


@dataclass
class GrowthEvent:
    """角色成长事件"""
    event_name: str
    chapter: str = ""
    time: str = ""
    description: str = ""
    state_before: str = ""
    state_after: str = ""
    growth_type: str = ""  # 实力/地位/情感/认知/关系
    significance: str = "中"  # 高/中/低


@dataclass
class CharacterGrowthCurve:
    """角色成长曲线"""
    character_name: str
    growth_events: List[GrowthEvent]
    summary: str
    growth_phases: List[dict]  # 成长阶段划分
    overall_trend: str  # 整体趋势描述


@dataclass
class Setting:
    """设定数据结构"""
    name: str
    type: str = ""
    description: str = ""
    related_characters: List[str] = None
    related_settings: List[str] = None

    def __post_init__(self):
        if self.related_characters is None:
            self.related_characters = []
        if self.related_settings is None:
            self.related_settings = []


@dataclass
class Event:
    """事件数据结构"""
    name: str
    time: str = ""
    participants: List[str] = None
    location: str = ""
    description: str = ""
    cause: List[str] = None
    effect: List[str] = None
    chapter: str = ""
    importance: str = "普通"

    def __post_init__(self):
        if self.participants is None:
            self.participants = []
        if self.cause is None:
            self.cause = []
        if self.effect is None:
            self.effect = []


@dataclass
class PlotOutline:
    """情节大纲数据结构"""
    title: str
    theme: str
    conflict: str
    structure: dict  # 起承转合
    key_points: List[str]
    ending_direction: str


@dataclass
class ChapterContent:
    """章节内容数据结构"""
    chapter_num: int
    title: str
    content: str
    word_count: int
    characters_involved: List[str]
    events_happened: List[str]


class BaseModule(ABC):
    """基础模块接口"""

    @abstractmethod
    def __init__(self, config: dict):
        """初始化模块"""
        pass

    @abstractmethod
    def run(self, input_data: dict) -> dict:
        """运行模块"""
        pass

    @abstractmethod
    def validate(self, output_data: dict) -> bool:
        """验证输出"""
        pass


class VaultManagerInterface(BaseModule):
    """知识库管理接口"""

    @abstractmethod
    def load_all_cards(self) -> Dict[str, List[dict]]:
        """
        加载所有卡片

        Returns:
            {
                "characters": [人物卡片列表],
                "settings": [设定卡片列表],
                "events": [事件卡片列表]
            }
        """
        pass

    @abstractmethod
    def load_character(self, name: str) -> Optional[Character]:
        """
        加载人物卡片

        Args:
            name: 人物名称

        Returns:
            人物对象，如果不存在返回 None
        """
        pass

    @abstractmethod
    def load_setting(self, name: str) -> Optional[Setting]:
        """
        加载设定卡片

        Args:
            name: 设定名称

        Returns:
            设定对象，如果不存在返回 None
        """
        pass

    @abstractmethod
    def load_event(self, name: str) -> Optional[Event]:
        """
        加载事件卡片

        Args:
            name: 事件名称

        Returns:
            事件对象，如果不存在返回 None
        """
        pass

    @abstractmethod
    def update_character(self, name: str, updates: dict):
        """
        更新人物卡片

        Args:
            name: 人物名称
            updates: 更新内容
        """
        pass

    @abstractmethod
    def update_setting(self, name: str, updates: dict):
        """
        更新设定卡片

        Args:
            name: 设定名称
            updates: 更新内容
        """
        pass

    @abstractmethod
    def add_event(self, event: Event):
        """
        添加事件卡片

        Args:
            event: 事件对象
        """
        pass

    @abstractmethod
    def get_timeline(self) -> List[dict]:
        """
        获取事件时间线

        Returns:
            按时间排序的事件列表
        """
        pass

    @abstractmethod
    def search_cards(self, keyword: str) -> Dict[str, List[dict]]:
        """
        搜索卡片

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的卡片列表
        """
        pass


class PlotGeneratorInterface(BaseModule):
    """情节生成接口"""

    @abstractmethod
    def generate_outline(self, book_title: str, knowledge_base: dict) -> PlotOutline:
        """
        生成情节大纲

        Args:
            book_title: 作品标题
            knowledge_base: 知识库内容

        Returns:
            情节大纲对象
        """
        pass

    @abstractmethod
    def identify_gaps(self, timeline: List[dict], knowledge_base: dict) -> List[dict]:
        """
        识别情节空白

        Args:
            timeline: 事件时间线
            knowledge_base: 知识库内容

        Returns:
            情节空白列表
        """
        pass

    @abstractmethod
    def validate_outline(self, outline: PlotOutline, knowledge_base: dict) -> bool:
        """
        验证大纲

        Args:
            outline: 情节大纲
            knowledge_base: 知识库内容

        Returns:
            是否有效
        """
        pass

    @abstractmethod
    def expand_outline(self, outline: PlotOutline, gap: dict) -> PlotOutline:
        """
        扩展大纲（填充情节空白）

        Args:
            outline: 原始大纲
            gap: 情节空白

        Returns:
            扩展后的大纲
        """
        pass


class ChapterGeneratorInterface(BaseModule):
    """章节生成接口"""

    @abstractmethod
    def generate_chapter(
        self,
        chapter_num: int,
        outline: PlotOutline,
        context: dict,
        total_chapters: int = None
    ) -> ChapterContent:
        """
        生成章节内容

        Args:
            chapter_num: 章节号
            outline: 情节大纲
            context: 上下文信息（前文内容、人物状态等）
            total_chapters: 总章节数，用于映射大纲结构

        Returns:
            章节内容对象
        """
        pass

    @abstractmethod
    def quality_check(
        self,
        content: ChapterContent,
        characters: List[Character]
    ) -> Dict[str, Any]:
        """
        质量检查

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
        pass

    @abstractmethod
    def check_character_consistency(
        self,
        content: ChapterContent,
        character: Character
    ) -> bool:
        """
        检查人物一致性

        Args:
            content: 章节内容
            character: 人物对象

        Returns:
            是否一致
        """
        pass

    @abstractmethod
    def check_timeline_consistency(
        self,
        content: ChapterContent,
        timeline: List[dict]
    ) -> bool:
        """
        检查时间线一致性

        Args:
            content: 章节内容
            timeline: 事件时间线

        Returns:
            是否一致
        """
        pass


class NovelLoggerInterface(BaseModule):
    """日志记录接口"""

    @abstractmethod
    def save_chapter(self, chapter_num: int, content: ChapterContent):
        """
        保存章节

        Args:
            chapter_num: 章节号
            content: 章节内容
        """
        pass

    @abstractmethod
    def update_knowledge_log(self, changes: dict):
        """
        更新知识库日志

        Args:
            changes: 变更内容
            {
                "new_characters": [新人物列表],
                "updated_characters": [更新的人物列表],
                "new_events": [新事件列表],
                "new_settings": [新设定列表]
            }
        """
        pass

    @abstractmethod
    def merge_novel(self, book_title: str) -> str:
        """
        合并为完整小说

        Args:
            book_title: 作品标题

        Returns:
            完整小说内容
        """
        pass

    @abstractmethod
    def get_progress(self, book_title: str) -> dict:
        """
        获取写作进度

        Args:
            book_title: 作品标题

        Returns:
            {
                "total_chapters": 总章节数,
                "completed_chapters": 已完成章节数,
                "total_words": 总字数,
                "last_updated": 最后更新时间
            }
        """
        pass

    @abstractmethod
    def resume_writing(self, book_title: str) -> int:
        """
        恢复写作（断点续写）

        Args:
            book_title: 作品标题

        Returns:
            下一个要写的章节号
        """
        pass


class QualityCheckerInterface(BaseModule):
    """质量检测接口"""

    @abstractmethod
    def check_logic_consistency(
        self,
        content: ChapterContent,
        characters: List[Character],
        events: List[Event]
    ) -> Dict[str, Any]:
        """
        检查逻辑一致性

        Returns:
            {
                "passed": True/False,
                "issues": [问题列表]
            }
        """
        pass

    @abstractmethod
    def check_word_count(
        self,
        content: ChapterContent,
        min_words: int = MIN_WORDS,
        max_words: int = MAX_WORDS
    ) -> bool:
        """
        检查字数

        Args:
            content: 章节内容
            min_words: 最少字数
            max_words: 最多字数

        Returns:
            是否符合要求
        """
        pass

    @abstractmethod
    def check_duplicates(
        self,
        content: ChapterContent,
        previous_chapters: List[str]
    ) -> bool:
        """
        检查重复内容

        Args:
            content: 章节内容
            previous_chapters: 之前章节的内容列表

        Returns:
            是否有重复
        """
        pass

    @abstractmethod
    def check_sensitive_words(
        self,
        content: ChapterContent
    ) -> List[str]:
        """
        检查敏感词

        Args:
            content: 章节内容

        Returns:
            敏感词列表
        """
        pass


class ConverterInterface(BaseModule):
    """格式转换接口"""

    @abstractmethod
    def convert_to_platform(
        self,
        novel_content: str,
        platform: str
    ) -> str:
        """
        转换为平台格式

        Args:
            novel_content: 小说内容
            platform: 目标平台（番茄/起点/晋江）

        Returns:
            转换后的内容
        """
        pass

    @abstractmethod
    def convert_to_epub(
        self,
        novel_content: str,
        metadata: dict
    ) -> str:
        """
        转换为 EPUB 格式

        Args:
            novel_content: 小说内容
            metadata: 元数据（标题、作者等）

        Returns:
            EPUB 文件路径
        """
        pass

    @abstractmethod
    def convert_to_txt(
        self,
        novel_content: str
    ) -> str:
        """
        转换为纯文本格式

        Args:
            novel_content: 小说内容

        Returns:
            纯文本内容
        """
        pass


class CommercialManagerInterface(BaseModule):
    """商业化管理接口"""

    @abstractmethod
    def estimate_words_per_chapter(self) -> int:
        """
        估算每章字数

        Returns:
            每章预计字数
        """
        pass

    @abstractmethod
    def estimate_total_words(self, num_chapters: int) -> int:
        """
        估算总字数

        Args:
            num_chapters: 章节数

        Returns:
            预计总字数
        """
        pass

    @abstractmethod
    def calculate_revenue(self, total_words: int, platform: str) -> dict:
        """
        计算收益

        Args:
            total_words: 总字数
            platform: 平台（番茄/起点/晋江）

        Returns:
            {
                "platform": 平台名称,
                "total_words": 总字数,
                "rate": 千字价格,
                "estimated_revenue": 预估收益,
                "currency": 货币单位
            }
        """
        pass

    @abstractmethod
    def format_for_platform(
        self,
        content: str,
        platform: str
    ) -> str:
        """
        格式化内容为平台格式

        Args:
            content: 小说内容
            platform: 目标平台

        Returns:
            格式化后的内容
        """
        pass

    @abstractmethod
    def get_platform_info(self, platform: str) -> dict:
        """
        获取平台信息

        Args:
            platform: 平台名称

        Returns:
            {
                "name": 平台名称,
                "rate_per_1000": 千字价格,
                "min_chapters": 最少章节,
                "payment_model": 收益模式,
                "currency": 货币单位
            }
        """
        pass

    @abstractmethod
    def compare_platforms(self, total_words: int) -> List[dict]:
        """
        比较各平台收益

        Args:
            total_words: 总字数

        Returns:
            各平台收益对比列表
        """
        pass
