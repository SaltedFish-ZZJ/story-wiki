"""
Story Wiki - Agent 驱动模式命令。

把「LLM 分析」这一环交给外部 Agent（WorkBuddy / Claude / Trae 等）：
- --plan  ：纯本地把小说切章，产出 manifest.json + 章节原文，交给 Agent 逐章分析
- --ingest：接收 Agent 生成的卡片 JSON，校验后增量写入知识库（Obsidian 卡片 + FTS 索引）

全程零 API 调用。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from src.config import VAULT_DIR
from src.extractor import extract_text
from src.logging_setup import get_logger
from src.splitter import DEFAULT_CHUNK_SIZE, split_chapters
from src.utils import safe_filename

logger = get_logger("agent")

# Agent 工作区（manifest + 章节原文）
AGENT_RUNS_DIR = Path("data/agent_runs")


# ── plan：切章，产出 Agent 任务清单 ──────────────────────────


def run_plan(args) -> None:
    input_path = Path(args.plan)
    if not input_path.exists():
        print(f"[错误] 输入文件不存在: {input_path}")
        sys.exit(1)

    text = extract_text(str(input_path))
    if not text.strip():
        print("[错误] 提取到的文本为空")
        sys.exit(1)

    title = args.title or input_path.stem
    run_dir = AGENT_RUNS_DIR / safe_filename(title)
    chapters_dir = run_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    chapters = split_chapters(text, chunk_size=args.chunk_size or DEFAULT_CHUNK_SIZE)

    manifest = {
        "title": title,
        "source": str(input_path.resolve()),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "total_chapters": len(chapters),
        "chapters": [],
    }
    for ch in chapters:
        fname = f"chapter-{ch.index:03d}.txt"
        (chapters_dir / fname).write_text(ch.text, encoding="utf-8")
        manifest["chapters"].append({
            "num": ch.index,
            "title": ch.title,
            "file": str((chapters_dir / fname).resolve()),
            "chars": ch.char_count,
        })

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"作品: {title}")
    print(f"章节: {len(chapters)} 章，共 {sum(c['chars'] for c in manifest['chapters'])} 字")
    print(f"任务清单: {manifest_path.resolve()}")
    print("下一步: 用你自己的模型逐章阅读章节文件，按 skills/story-wiki/SKILL.md 的卡片"
          " schema 生成 cards.json，然后执行 --ingest 写入知识库。")


# ── ingest：接收 Agent 卡片 JSON，校验 + 增量写库 ────────────────


def _norm_participants(raw) -> list[str]:
    """participants 兼容字符串数组与 {name} 对象数组。"""
    out = []
    for p in raw or []:
        if isinstance(p, str):
            out.append(p.strip())
        elif isinstance(p, dict) and p.get("name"):
            out.append(str(p["name"]).strip())
    return [p for p in out if p]


def _norm_names(raw) -> list[str]:
    """related_* / cause / effect 字段归一化为字符串数组（兼容 {name} 对象）。"""
    return [n for n in _norm_participants(raw)]


def _validate(cards: dict, source: str) -> tuple[dict, list[str]]:
    """宽松校验 + 规范化；返回 (analysis, warnings)。缺 name 的实体丢弃。"""
    warns = []
    analysis = {
        "title": cards.get("title") or "未命名作品",
        "summary": cards.get("summary") or "",
        "incremental": True,
        "characters": [], "settings": [], "events": [],
    }
    for c in cards.get("characters") or []:
        if not (c.get("name") or "").strip():
            warns.append("人物卡缺 name，已跳过")
            continue
        c = dict(c)
        # generator 约定：relationships[].target 为字符串、related_settings 为字符串数组
        for r in c.get("relationships") or []:
            if isinstance(r, dict) and isinstance(r.get("target"), dict):
                r["target"] = r["target"].get("name") or ""
        c["related_settings"] = _norm_names(c.get("related_settings"))
        analysis["characters"].append(c)
    for s in cards.get("settings") or []:
        if not (s.get("name") or "").strip():
            warns.append("设定卡缺 name，已跳过")
            continue
        s = dict(s)
        s["related_characters"] = _norm_names(s.get("related_characters"))
        s["related_settings"] = _norm_names(s.get("related_settings"))
        analysis["settings"].append(s)
    for e in cards.get("events") or []:
        if not (e.get("name") or "").strip():
            warns.append("事件卡缺 name，已跳过")
            continue
        e = dict(e)
        e["participants"] = _norm_participants(e.get("participants"))
        e["cause"] = _norm_names(e.get("cause"))
        e["effect"] = _norm_names(e.get("effect"))
        analysis["events"].append(e)
    if not any(analysis[k] for k in ("characters", "settings", "events")):
        warns.append("卡片为空：没有任何人物/设定/事件")
    return analysis, warns


def run_ingest(args) -> None:
    cards_path = Path(args.ingest)
    if not cards_path.exists():
        print(f"[错误] 卡片文件不存在: {cards_path}")
        sys.exit(1)
    try:
        cards = json.loads(cards_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[错误] JSON 解析失败: {e}")
        sys.exit(1)
    if not isinstance(cards, dict):
        print("[错误] 卡片文件顶层必须是 JSON 对象")
        sys.exit(1)

    # CLI 注入：整批卡片的章节归属与书名
    if args.book_title:
        cards.setdefault("title", args.book_title)
    chapter = args.chapter
    if chapter:
        for e in cards.get("events") or []:
            if not e.get("chapter"):
                e["chapter"] = chapter

    analysis, warns = _validate(cards, str(cards_path))
    for w in warns:
        print(f"[警告] {w}")
    if analysis.get("title") == "未命名作品" and not args.book_title:
        print("[错误] 缺少书名：卡片 JSON 提供 title 字段，或调用时加 --book-title")
        sys.exit(1)

    from src.generator import generate_vault_incremental

    output = Path(args.output).resolve() if args.output else (Path("data/output")).resolve()
    files = generate_vault_incremental(analysis, output_dir=output)

    # 通知运行中的 Web 服务清缓存，让新数据立即可见（服务未启动则静默跳过）
    try:
        import urllib.request

        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/reload", method="POST", data=b"")
        urllib.request.urlopen(req, timeout=2)
        web_note = "Web 缓存已刷新"
    except Exception:  # noqa: BLE001
        web_note = "Web 服务未运行，启动后自动读取最新数据"

    print(f"作品: {analysis['title']}")
    print(f"写入: 人物 {len(analysis['characters'])} / 设定 {len(analysis['settings'])}"
          f" / 事件 {len(analysis['events'])}，生成/更新 {len(files)} 个文件")
    print(f"输出目录: {output}")
    print(f"{web_note} · 查看: Web 界面（python -m uvicorn web.app:app --port 8000）或 MCP 工具")
