"""
Story Wiki - 配置模块
管理 API key、路径、模型参数等。

优化：添加内存和性能相关配置。
"""
import os
import psutil
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
VAULT_DIR = Path(os.environ.get("STORY_WIKI_VAULT", r"D:\Obsidian_Work\story_wiki"))
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

# ── 创作管线参数 ──
CREATE_DEFAULT_CHAPTERS = 5      # 默认生成章节数
CREATE_WORDS_PER_CHAPTER = 2500  # 每章目标字数
CREATE_MAX_RETRIES = 3           # 单章最大重试次数
CREATE_OUTPUT_DIR = DATA_DIR / "novels"  # 输出目录

# ── 质量检查参数 ──
MIN_WORDS = 2000                 # 章节最少字数
MAX_WORDS = 3000                 # 章节最多字数
DUPLICATE_THRESHOLD = 0.6        # 重复度阈值

# ── API 重试参数 ──
MAX_RETRIES = 3                  # 最大重试次数
RETRY_BASE_DELAY = 2             # 首次重试等待秒数（指数退避）

# ── 内存和性能优化配置 ──
# 大文件流式读取阈值（字节）
LARGE_FILE_THRESHOLD = 1 * 1024 * 1024  # 1MB
# 分块读取大小（字节）
CHUNK_READ_SIZE = 64 * 1024  # 64KB
# 请求体大小警告阈值（字节）
REQUEST_SIZE_WARNING = 10 * 1024 * 1024  # 10MB
# 请求体大小限制（字节）
REQUEST_SIZE_LIMIT = 50 * 1024 * 1024  # 50MB
# 最大匹配数（避免内存爆炸）
MAX_MATCHES = 1000

# ── 商业化管理配置 ──
DEFAULT_WORDS_PER_CHAPTER = 2500  # 默认每章字数
MIN_CHAPTER_WORDS = 1500          # 章节最少字数（商业化要求）
MAX_CHAPTER_WORDS = 4000          # 章节最多字数（商业化要求）

COMMERCIAL_CONFIG = {
    "words_per_chapter": DEFAULT_WORDS_PER_CHAPTER,
    "min_chapter_words": MIN_CHAPTER_WORDS,
    "max_chapter_words": MAX_CHAPTER_WORDS,
}

PLATFORM_RATES = {
    "番茄小说": {
        "rate_per_1000": 0.02,
        "min_chapters": 30,
        "payment_model": "订阅制",
        "currency": "CNY",
        "description": "番茄小说，流量大，适合新人",
        "formatting_rules": {"indent": "    "},
    },
    "起点中文网": {
        "rate_per_1000": 0.03,
        "min_chapters": 40,
        "payment_model": "订阅制",
        "currency": "CNY",
        "description": "起点中文网，读者付费意愿强",
        "formatting_rules": {"indent": "    "},
    },
    "晋江文学城": {
        "rate_per_1000": 0.025,
        "min_chapters": 35,
        "payment_model": "订阅制",
        "currency": "CNY",
        "description": "晋江文学城，女性读者为主",
        "formatting_rules": {"indent": "    "},
    },
}

# ── 内存监控 ──
def get_system_memory() -> dict:
    """获取系统内存信息。"""
    try:
        mem = psutil.virtual_memory()
        return {
            "total_gb": mem.total / 1024 / 1024 / 1024,
            "available_gb": mem.available / 1024 / 1024 / 1024,
            "used_percent": mem.percent,
        }
    except Exception:
        return {"total_gb": 0, "available_gb": 0, "used_percent": 0}


def get_process_memory() -> dict:
    """获取当前进程内存信息。"""
    try:
        process = psutil.Process()
        mem = process.memory_info()
        return {
            "rss_mb": mem.rss / 1024 / 1024,
            "vms_mb": mem.vms / 1024 / 1024,
        }
    except Exception:
        return {"rss_mb": 0, "vms_mb": 0}


def print_memory_status():
    """打印内存使用状态。"""
    sys_mem = get_system_memory()
    proc_mem = get_process_memory()

    print(f"[内存] 系统: {sys_mem['available_gb']:.1f}GB 可用 / {sys_mem['total_gb']:.1f}GB 总计 ({sys_mem['used_percent']:.1f}% 已用)")
    print(f"[内存] 进程: {proc_mem['rss_mb']:.1f}MB RSS / {proc_mem['vms_mb']:.1f}MB VMS")


# ── 确保必要目录存在 ──
def ensure_dirs():
    """创建必要的目录结构。"""
    for d in [INPUT_DIR, STATE_DIR, VAULT_DIR]:
        d.mkdir(parents=True, exist_ok=True)

# ── 启动时自动创建 ──
ensure_dirs()

# ── 启动时打印系统信息 ──
print_memory_status()
