"""
商业化管理模块
提供多平台发布支持、收益估算、格式转换等功能
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from .interfaces import CommercialManagerInterface, ChapterContent
from .config import (
    COMMERCIAL_CONFIG, PLATFORM_RATES, DEFAULT_WORDS_PER_CHAPTER,
    MIN_CHAPTER_WORDS, MAX_CHAPTER_WORDS
)


@dataclass
class PlatformInfo:
    """平台信息数据结构"""
    name: str
    rate_per_1000: float  # 千字价格
    min_chapters: int
    payment_model: str  # "订阅制", "买断制", "打赏制"
    currency: str = "CNY"
    description: str = ""
    formatting_rules: Optional[dict] = None


class CommercialManager(CommercialManagerInterface):
    """商业化管理器实现"""

    def __init__(self, config: dict = None):
        """
        初始化商业化管理器

        Args:
            config: 配置字典
        """
        if config is None:
            config = {}

        self.config = config
        self.output_dir = Path(config.get("output_dir", "./output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 加载平台配置
        self.platforms = self._load_platforms()

        # 默认配置
        self.words_per_chapter = config.get(
            "words_per_chapter",
            COMMERCIAL_CONFIG.get("words_per_chapter", DEFAULT_WORDS_PER_CHAPTER)
        )

    def _load_platforms(self) -> Dict[str, PlatformInfo]:
        """加载平台配置"""
        platforms = {}
        for name, info in PLATFORM_RATES.items():
            platforms[name] = PlatformInfo(
                name=name,
                rate_per_1000=info.get("rate_per_1000", 0.02),
                min_chapters=info.get("min_chapters", 30),
                payment_model=info.get("payment_model", "订阅制"),
                currency=info.get("currency", "CNY"),
                description=info.get("description", ""),
                formatting_rules=info.get("formatting_rules", {})
            )
        return platforms

    def estimate_words_per_chapter(self) -> int:
        """
        估算每章字数

        Returns:
            每章预计字数
        """
        return self.words_per_chapter

    def estimate_total_words(self, num_chapters: int) -> int:
        """
        估算总字数

        Args:
            num_chapters: 章节数

        Returns:
            预计总字数
        """
        return num_chapters * self.words_per_chapter

    def calculate_revenue(self, total_words: int, platform: str) -> dict:
        """
        计算收益

        Args:
            total_words: 总字数
            platform: 平台名称

        Returns:
            收益计算结果
        """
        if platform not in self.platforms:
            raise ValueError(f"不支持的平台: {platform}。支持的平台: {list(self.platforms.keys())}")

        platform_info = self.platforms[platform]
        rate_per_1000 = platform_info.rate_per_1000

        # 计算千字数
        thousands = total_words / 1000.0

        # 计算收益
        estimated_revenue = thousands * rate_per_1000

        return {
            "platform": platform,
            "total_words": total_words,
            "rate": rate_per_1000,
            "estimated_revenue": round(estimated_revenue, 2),
            "currency": platform_info.currency,
            "payment_model": platform_info.payment_model
        }

    def format_for_platform(self, content: str, platform: str) -> str:
        """
        格式化内容为平台格式

        Args:
            content: 小说内容
            platform: 目标平台

        Returns:
            格式化后的内容
        """
        if platform not in self.platforms:
            raise ValueError(f"不支持的平台: {platform}。支持的平台: {list(self.platforms.keys())}")

        platform_info = self.platforms[platform]
        formatting_rules = platform_info.formatting_rules or {}

        lines = content.split('\n')
        formatted_lines = []

        for line in lines:
            # 处理标题
            if line.startswith('## '):
                title = line[3:].strip()
                indent = formatting_rules.get("indent", "    ")
                formatted_lines.append(f"{indent}{title}")
            elif line.startswith('# '):
                # 一级标题作为书名，跳过
                continue
            else:
                formatted_lines.append(line)

        return '\n'.join(formatted_lines)

    def get_platform_info(self, platform: str) -> dict:
        """
        获取平台信息

        Args:
            platform: 平台名称

        Returns:
            平台详细信息
        """
        if platform not in self.platforms:
            raise ValueError(f"不支持的平台: {platform}。支持的平台: {list(self.platforms.keys())}")

        platform_info = self.platforms[platform]
        return {
            "name": platform_info.name,
            "rate_per_1000": platform_info.rate_per_1000,
            "min_chapters": platform_info.min_chapters,
            "payment_model": platform_info.payment_model,
            "currency": platform_info.currency,
            "description": platform_info.description
        }

    def compare_platforms(self, total_words: int) -> List[dict]:
        """
        比较各平台收益

        Args:
            total_words: 总字数

        Returns:
            各平台收益对比列表
        """
        results = []
        for platform_name in self.platforms:
            revenue_info = self.calculate_revenue(total_words, platform_name)
            platform_info = self.platforms[platform_name]
            results.append({
                "platform": platform_name,
                "estimated_revenue": revenue_info["estimated_revenue"],
                "currency": revenue_info["currency"],
                "rate_per_1000": platform_info.rate_per_1000,
                "payment_model": platform_info.payment_model,
                "min_chapters": platform_info.min_chapters
            })

        # 按收益降序排列
        results.sort(key=lambda x: x["estimated_revenue"], reverse=True)
        return results

    def generate_publishing_report(
        self,
        book_title: str,
        total_words: int,
        chapters: int
    ) -> dict:
        """
        生成发布报告

        Args:
            book_title: 书名
            total_words: 总字数
            chapters: 章节数

        Returns:
            发布报告
        """
        words_per_chapter = total_words // chapters if chapters > 0 else 0
        platform_comparison = self.compare_platforms(total_words)

        return {
            "book_title": book_title,
            "statistics": {
                "total_words": total_words,
                "chapters": chapters,
                "words_per_chapter": words_per_chapter
            },
            "platform_comparison": platform_comparison,
            "recommendation": self._get_recommendation(platform_comparison, chapters)
        }

    def _get_recommendation(self, comparison: List[dict], chapters: int) -> dict:
        """获取推荐平台"""
        if not comparison:
            return {"platform": None, "reason": "无可用平台"}

        # 检查是否满足最低章节要求
        suitable_platforms = [
            p for p in comparison
            if chapters >= p["min_chapters"]
        ]

        if not suitable_platforms:
            # 推荐章节要求最低的平台
            min_req_platform = min(comparison, key=lambda x: x["min_chapters"])
            return {
                "platform": min_req_platform["platform"],
                "reason": f"当前章节数({chapters})较少，推荐{min_req_platform['platform']}（最低{min_req_platform['min_chapters']}章）"
            }

        # 推荐收益最高的平台
        best_platform = suitable_platforms[0]
        return {
            "platform": best_platform["platform"],
            "reason": f"收益最高，预计{best_platform['currency']} {best_platform['estimated_revenue']}"
        }

    def run(self, input_data: dict) -> dict:
        """
        运行模块

        Args:
            input_data: {
                "action": "calculate" | "compare" | "report",
                "total_words": 总字数,
                "platform": 平台名称（可选）,
                "book_title": 书名（可选）,
                "chapters": 章节数（可选）
            }

        Returns:
            处理结果
        """
        action = input_data.get("action", "compare")
        total_words = input_data.get("total_words", 0)
        platform = input_data.get("platform")
        book_title = input_data.get("book_title", "未命名作品")
        chapters = input_data.get("chapters", 0)

        if action == "calculate" and platform:
            return self.calculate_revenue(total_words, platform)
        elif action == "compare":
            return {"comparison": self.compare_platforms(total_words)}
        elif action == "report":
            return self.generate_publishing_report(book_title, total_words, chapters)
        else:
            raise ValueError(f"无效的操作: {action}")

    def validate(self, output_data: dict) -> bool:
        """
        验证输出

        Args:
            output_data: 输出数据

        Returns:
            是否有效
        """
        if "estimated_revenue" in output_data:
            return output_data["estimated_revenue"] >= 0
        elif "comparison" in output_data:
            return isinstance(output_data["comparison"], list)
        elif "statistics" in output_data:
            return output_data["statistics"]["total_words"] > 0
        return False
