"""
Story Wiki - 配置模块
管理 API key、路径、模型参数等。
"""
import os
from pathlib import Path

# ── .env 文件加载器（复用 tarot-cli 模式，无第三方依赖）──
def _load_dotenv():
    """从项目根目录加载 .env 文件。"""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

_load_dotenv()

# ── 项目根目录 ──
PROJECT_ROOT = Path(__file__).parent.parent

# ── DeepSeek API 配置 ──
DEEPSEEK_API_KEY = os.environ.get("STORY_WIKI_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("STORY_WIKI_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("STORY_WIKI_MODEL", "deepseek-chat")

# ── 路径配置 ──
VAULT_DIR = Path(os.environ.get("STORY_WIKI_VAULT", r"D:\Obsidian_Work\myself_wiki\story_wiki"))
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
STATE_DIR = DATA_DIR / "state"
CACHE_DIR = STATE_DIR / "cache"

# ── 分析参数 ──
MAX_TEXT_LENGTH = 400000     # DeepSeek 1M上下文，留余量设40万字（约40-80万token）
TEMPERATURE = 0.3            # 低温度，输出更稳定
MAX_TOKENS = 8192            # 最大输出 token（增加以容纳更多人物/设定）

# ── 分章分析参数 ──
CHAPTER_THRESHOLD = 5000     # 超过此字数自动启用分章分析
CHAPTER_CHUNK_SIZE = 5000    # 无章节标记时每块的目标字数
CHAPTER_CONTEXT_CHARS = 500  # 每章分析时附加的已知人物/设定上下文摘要最大字数

# ── 增量分析参数 ──
INCREMENTAL_STATE_FILE = ".incremental_state.json"  # 增量状态文件名

# ── 确保必要目录存在 ──
def ensure_dirs():
    """创建必要的目录结构。"""
    for d in [INPUT_DIR, STATE_DIR, VAULT_DIR]:
        d.mkdir(parents=True, exist_ok=True)

# ── 启动时自动创建 ──
ensure_dirs()
