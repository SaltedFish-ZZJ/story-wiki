"""
Story Wiki - 测试基础设施（conftest.py）

提供共享的 pytest fixtures 和路径配置，消除各测试文件中的 sys.path hack 和重复代码。

约定：
  - 中文注释，snake_case 命名
  - 所有 fixtures 使用 tmp_path（pytest 内置）管理临时目录，确保自动清理
"""
import sys
from pathlib import Path

import pytest

# ── 路径配置 ──────────────────────────────────────────────────
# 确保项目根目录在 sys.path 中（pyproject.toml 的 pythonpath 已配置，此处作为兜底）
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ── 共享数据结构 fixtures ─────────────────────────────────────

@pytest.fixture
def sample_character_dict():
    """返回一个标准的人物字典（dict 格式，用于需要 dict 的场景）。"""
    return {
        "name": "测试人物",
        "identity": "主角",
        "personality": "勇敢无畏",
        "gender": "男",
        "faction": "测试阵营",
        "role_tags": ["主角"],
        "status": "活跃",
        "aliases": ["测试别名"],
        "relationships": [],
    }


@pytest.fixture
def sample_character_obj():
    """返回一个标准的 Character 数据结构实例。"""
    from src.interfaces import Character
    return Character(
        name="测试人物",
        identity="主角",
        personality="勇敢无畏",
        gender="男",
        faction="测试阵营",
        role_tags=["主角"],
        status="活跃",
        aliases=["测试别名"],
        relationships=[],
        motivation="测试动机",
        current_state="测试状态",
        quotes=[],
        related_settings=[],
    )


@pytest.fixture
def sample_chapter_content():
    """返回一个标准的 ChapterContent 数据结构实例。"""
    from src.interfaces import ChapterContent
    return ChapterContent(
        chapter_num=1,
        title="测试第1章",
        content="这是第一章的测试内容。" * 50,
        word_count=1000,
        characters_involved=["测试人物"],
        events_happened=["测试事件"],
    )


@pytest.fixture
def sample_knowledge_base():
    """返回一个标准的知识库数据（dict 格式），包含人物、设定、事件。"""
    return {
        "characters": [
            {"name": "主角A", "identity": "英雄", "personality": "勇敢", "gender": "男"},
            {"name": "配角B", "identity": "导师", "personality": "智慧", "gender": "男"},
        ],
        "settings": [
            {"name": "测试地点", "type": "地点", "description": "故事发生地"},
        ],
        "events": [
            {
                "name": "测试事件",
                "time": "第1章",
                "participants": ["主角A"],
                "cause": [],
            },
        ],
    }


# ── Vault 相关 fixtures ───────────────────────────────────────

@pytest.fixture
def vault_dir(tmp_path):
    """创建一个包含单本作品的测试 Vault 目录，返回 Path。

    目录结构：
        tmp_path/
        └── 测试作品/
            ├── characters/
            ├── settings/
            └── events/
    """
    from src.vault_manager import _safe_filename
    book_dir = tmp_path / _safe_filename("测试作品")
    for subdir in ["characters", "settings", "events"]:
        (book_dir / subdir).mkdir(parents=True, exist_ok=True)
    return book_dir


@pytest.fixture
def multi_book_vault(tmp_path):
    """创建一个包含多本作品的测试 Vault 目录，返回 (vault_dir, book_titles)。

    目录结构：
        tmp_path/
        ├── 作品A/
        │   ├── characters/
        │   ├── settings/
        │   └── events/
        └── 作品B/
            ├── characters/
            ├── settings/
            └── events/
    """
    from src.vault_manager import _safe_filename

    books = {
        "作品A": {
            "characters": {
                "主角A.md": """---
type: character
gender: 男
faction: 阵营A
---

# 主角A

> 活跃

## 身份
英雄

## 性格
勇敢

## 人际关系
- [[characters/配角B|配角B]] — 伙伴
""",
            },
            "settings": {},
            "events": {},
        },
        "作品B": {
            "characters": {
                "人物C.md": """---
type: character
gender: 女
faction: 阵营B
---

# 人物C

> 活跃

## 身份
战士

## 性格
坚毅
""",
            },
            "settings": {},
            "events": {},
        },
    }

    for book_title, dirs in books.items():
        book_dir = tmp_path / _safe_filename(book_title)
        for subdir, files in dirs.items():
            subdir_path = book_dir / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)
            for filename, content in files.items():
                (subdir_path / filename).write_text(content, encoding="utf-8")

    return tmp_path, list(books.keys())


# ── 配置 fixtures ─────────────────────────────────────────────

@pytest.fixture
def default_config():
    """返回默认的测试配置字典。"""
    return {}


@pytest.fixture
def custom_config():
    """返回自定义的测试配置字典。"""
    return {
        "min_words": 1500,
        "max_words": 2500,
        "temperature": 0.5,
    }
