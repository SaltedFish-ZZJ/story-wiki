"""
Story Wiki - 项目管理模块
跨作品管理：列出所有作品、跨作品搜索、人物相似度匹配、跨作品时间线。
"""
from typing import Dict, List, Optional

from src.interfaces import BaseModule
from src.config import VAULT_DIR
from src.vault_manager import VaultManager
from src.utils import normalize_name
from src.logging_setup import get_logger

logger = get_logger("project_manager")


class ProjectManager(BaseModule):
    """
    跨作品项目管理器。

    职责：
    - 列出 Vault 中所有作品及统计信息
    - 跨作品关键词搜索
    - 跨作品人物相似度匹配
    - 跨作品事件时间线合并
    """

    def __init__(self, config: dict = None):
        """
        初始化项目管理器。

        Args:
            config: 配置字典，支持：
                - vault_dir: Vault 根目录（可选，默认 VAULT_DIR）
        """
        self.config = config or {}
        self.vault_dir = self.config.get("vault_dir", VAULT_DIR)

    def _create_vault_manager(self, book_title: str = "") -> VaultManager:
        """创建 VaultManager 实例。"""
        cfg = {"vault_dir": self.vault_dir}
        if book_title:
            cfg["book_title"] = book_title
        return VaultManager(cfg)

    # ── 列出所有作品 ──────────────────────────────────────────────

    def list_books(self) -> List[dict]:
        """
        列出所有已分析的作品及统计信息。

        Returns:
            [{"title": "红楼梦", "path": "...", "characters": 17, "events": 5, "settings": 3}, ...]
        """
        vm = self._create_vault_manager()
        return vm.list_books()

    # ── 跨作品搜索 ──────────────────────────────────────────────

    def search_cross_book(self, keyword: str) -> Dict[str, List[dict]]:
        """
        跨作品搜索卡片，返回按作品分组的结果。

        Args:
            keyword: 搜索关键词

        Returns:
            {
                "红楼梦": {"characters": [...], "settings": [...], "events": [...]},
                "西游记": {...},
            }
        """
        books = self.list_books()
        results = {}

        for book in books:
            vm = self._create_vault_manager(book["title"])
            try:
                matches = vm.search_cards(keyword)
                # 只保留有结果的作品
                has_results = any(matches[k] for k in ["characters", "settings", "events"])
                if has_results:
                    # 给每张卡片标注来源作品
                    for card_type in ["characters", "settings", "events"]:
                        for card in matches[card_type]:
                            card["book"] = book["title"]
                    results[book["title"]] = matches
            except (OSError, ValueError, RuntimeError) as e:
                logger.warning(f"搜索书籍 {book['title']} 失败: {e}")
                continue

        return results

    # ── 跨作品人物相似度匹配 ────────────────────────────────────

    def find_similar_characters(self) -> List[dict]:
        """
        跨作品人物相似度匹配。

        匹配策略（从简到严）：
        1. 归一化名称完全匹配 → confidence: high
        2. 一方名称在另一方别名列表中 → confidence: high
        3. 名称子串匹配（>= 2字符） → confidence: medium
        4. 同势力 + 同身份关键词 → confidence: low

        Returns:
            [{"character_a": {...}, "character_b": {...},
              "match_type": "exact", "confidence": "high"}, ...]
        """
        books = self.list_books()
        if len(books) < 2:
            return []

        # 收集所有作品的人物，标注来源
        all_characters = []
        for book in books:
            vm = self._create_vault_manager(book["title"])
            try:
                cards = vm.load_all_cards()
                for char in cards.get("characters", []):
                    char["book"] = book["title"]
                    all_characters.append(char)
            except (OSError, ValueError, RuntimeError) as e:
                logger.warning(f"加载 {book['title']} 人物失败: {e}")
                continue

        if len(all_characters) < 2:
            return []

        # 两两比较
        matches = []
        seen_pairs = set()

        for i, a in enumerate(all_characters):
            for j, b in enumerate(all_characters):
                if i >= j:
                    continue

                # 跳过同一作品内的人物
                if a.get("book") == b.get("book"):
                    continue

                pair_key = (
                    (a.get("name", ""), a.get("book", "")),
                    (b.get("name", ""), b.get("book", "")),
                )
                if pair_key in seen_pairs:
                    continue

                result = self._compare_characters(a, b)
                if result:
                    seen_pairs.add(pair_key)
                    matches.append({
                        "character_a": {
                            "name": a.get("name", ""),
                            "book": a.get("book", ""),
                            "identity": a.get("identity", ""),
                        },
                        "character_b": {
                            "name": b.get("name", ""),
                            "book": b.get("book", ""),
                            "identity": b.get("identity", ""),
                        },
                        "match_type": result["match_type"],
                        "confidence": result["confidence"],
                    })

        return matches

    def _compare_characters(self, a: dict, b: dict) -> Optional[dict]:
        """
        比较两个人物是否可能是同一实体。

        Returns:
            {"match_type": str, "confidence": str} 或 None
        """
        name_a = a.get("name", "")
        name_b = b.get("name", "")
        if not name_a or not name_b:
            return None

        # 策略 1：归一化名称精确匹配
        norm_a = normalize_name(name_a)
        norm_b = normalize_name(name_b)
        if norm_a and norm_b and norm_a == norm_b:
            return {"match_type": "exact", "confidence": "high"}

        # 策略 2：别名匹配
        aliases_a = set(a.get("aliases", []))
        aliases_b = set(b.get("aliases", []))

        if name_a in aliases_b or name_b in aliases_a:
            return {"match_type": "alias", "confidence": "high"}

        # 归一化后的别名也匹配
        norm_aliases_a = {normalize_name(al) for al in aliases_a if al}
        norm_aliases_b = {normalize_name(al) for al in aliases_b if al}
        if norm_a in norm_aliases_b or norm_b in norm_aliases_a:
            return {"match_type": "alias", "confidence": "high"}

        # 策略 3：子串匹配（>= 2 字符）
        if len(norm_a) >= 2 and len(norm_b) >= 2:
            if norm_a in norm_b or norm_b in norm_a:
                return {"match_type": "substring", "confidence": "medium"}

        # 策略 4：同势力 + 同身份关键词
        faction_a = a.get("faction", "").strip()
        faction_b = b.get("faction", "").strip()
        identity_a = a.get("identity", "").strip()
        identity_b = b.get("identity", "").strip()

        if (faction_a and faction_b and faction_a == faction_b
                and identity_a and identity_b and identity_a == identity_b):
            return {"match_type": "attribute", "confidence": "low"}

        return None

    # ── 单本书摘要 ──────────────────────────────────────────────

    def get_book_summary(self, book_title: str) -> Optional[dict]:
        """
        获取单本书的详细摘要。

        Args:
            book_title: 作品标题

        Returns:
            {"title": "...", "characters": [...], "settings_count": N,
             "events_count": N, "timeline_span": "..."} 或 None
        """
        vm = self._create_vault_manager(book_title)
        try:
            cards = vm.load_all_cards()
        except (OSError, ValueError):
            return None

        characters = cards.get("characters", [])
        events = cards.get("events", [])
        settings = cards.get("settings", [])

        # 人物摘要
        char_summaries = []
        for c in characters:
            char_summaries.append({
                "name": c.get("name", ""),
                "identity": c.get("identity", ""),
                "faction": c.get("faction", ""),
                "status": c.get("status", "未知"),
                "relationships_count": len(c.get("relationships", [])),
            })

        # 时间线跨度
        times = [e.get("time", "") for e in events if e.get("time")]
        timeline_span = ""
        if times:
            sorted_times = sorted(times)
            timeline_span = f"{sorted_times[0]} ~ {sorted_times[-1]}" if len(sorted_times) > 1 else sorted_times[0]

        return {
            "title": book_title,
            "characters_count": len(characters),
            "characters": char_summaries,
            "settings_count": len(settings),
            "events_count": len(events),
            "timeline_span": timeline_span,
        }

    # ── 跨作品时间线 ──────────────────────────────────────────────

    def get_cross_book_timeline(self) -> List[dict]:
        """
        跨作品事件时间线合并，按时间排序。

        Returns:
            [{"name": "宝黛初见", "time": "...", "book": "红楼梦", ...}, ...]
        """
        books = self.list_books()
        all_events = []

        for book in books:
            vm = self._create_vault_manager(book["title"])
            try:
                timeline = vm.get_timeline()
                for event in timeline:
                    event["book"] = book["title"]
                    all_events.append(event)
            except (OSError, ValueError, RuntimeError) as e:
                logger.warning(f"加载 {book['title']} 时间线失败: {e}")
                continue
        all_events.sort(key=lambda e: e.get("time", "\uffff"))
        return all_events

    # ── BaseModule 接口实现 ────────────────────────────────────

    def run(self, input_data: dict) -> dict:
        """
        运行模块。

        支持的 action：
            - list_books: 列出所有作品
            - search_cross_book: 跨作品搜索（需 keyword）
            - find_similar_characters: 跨作品人物匹配
            - get_book_summary: 单本书摘要（需 book_title）
            - get_cross_book_timeline: 跨作品时间线
        """
        if not isinstance(input_data, dict):
            return {"success": False, "error": "input_data 必须是 dict"}

        action = input_data.get("action", "")

        try:
            if action == "list_books":
                return {"success": True, "books": self.list_books()}

            elif action == "search_cross_book":
                keyword = input_data.get("keyword", "")
                if not keyword:
                    return {"success": False, "error": "缺少 keyword 参数"}
                return {"success": True, "results": self.search_cross_book(keyword)}

            elif action == "find_similar_characters":
                return {"success": True, "matches": self.find_similar_characters()}

            elif action == "get_book_summary":
                book_title = input_data.get("book_title", "")
                if not book_title:
                    return {"success": False, "error": "缺少 book_title 参数"}
                summary = self.get_book_summary(book_title)
                if summary is None:
                    return {"success": False, "error": f"作品不存在或读取失败: {book_title}"}
                return {"success": True, "summary": summary}

            elif action == "get_cross_book_timeline":
                return {"success": True, "timeline": self.get_cross_book_timeline()}

            else:
                return {"success": False, "error": f"未知 action: {action}"}

        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as e:
            return {"success": False, "error": str(e)}

    def validate(self, output_data: dict) -> bool:
        """验证输出数据格式。"""
        if not isinstance(output_data, dict):
            return False
        if "success" not in output_data:
            return False
        if output_data["success"]:
            return True
        return "error" in output_data
