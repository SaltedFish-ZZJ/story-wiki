"""
Story Wiki Web UI — FastAPI 后端。
直接读取 Obsidian .md 文件，提供 JSON API 给前端。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from web.auth import (
    auth_enabled,
    clear_session,
    require_auth,
    set_session,
    verify_password,
)

# 保证 `python -m uvicorn web.app:app` 与包内导入两种方式都能找到 src 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── 路径配置 ──────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
# 默认读取本地生成目录，也支持 Obsidian Vault
OUTPUT_DIR = BASE_DIR / "data" / "output"
# 上传文件存放目录（复用 CLI 分析的输入目录）
INPUT_DIR = BASE_DIR / "data" / "input"
# 上传限制
ALLOWED_EXTS = {".txt", ".md", ".epub", ".pdf", ".docx"}
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100MB

# ── .md 文件解析器 ────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^|\]]+?)(?:\|([^\]]+?))?\]\]")


def _parse_fm(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _extract_section(text: str, header: str) -> str:
    pat = re.compile(
        rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=^##\s|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pat.search(text)
    return m.group(1).strip() if m else ""


def _parse_section_links(text: str, header: str) -> list[dict]:
    section = _extract_section(text, header)
    if not section:
        return []
    results = []
    for line in section.split("\n"):
        line = line.strip().lstrip("- ")
        m = _WIKILINK_RE.search(line)
        if m:
            path = m.group(1)
            display = m.group(2) or path.rsplit("/", 1)[-1]
            after = _WIKILINK_RE.sub("", line).strip().lstrip("—- ").strip()
            results.append({"path": path, "name": display, "description": after})
    return results


def _body_summary(text: str) -> str:
    """提取 frontmatter 之后、第一个 ## 之前的正文摘要。"""
    without_fm = _FRONTMATTER_RE.sub("", text, count=1)
    lines = []
    for line in without_fm.split("\n"):
        s = line.strip()
        if s.startswith("##"):
            break
        if s and not s.startswith("#") and not s.startswith(">") and "---" not in s:
            lines.append(s)
    return " ".join(lines)[:300]


def _extract_name(text: str, fallback: str) -> str:
    """从 .md 正文中提取 # 标题作为名称，跳过 frontmatter。"""
    # 跳过 frontmatter
    without_fm = _FRONTMATTER_RE.sub("", text, count=1)
    for line in without_fm.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _read_md(filepath: Path) -> str:
    try:
        return filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ── 作品目录发现 ──────────────────────────────────────────────


def _find_book_dir(title: str) -> Path | None:
    """在 OUTPUT_DIR 下查找作品目录。支持 title/title/ 和 title/ 两种结构。"""
    candidate = OUTPUT_DIR / title / title
    if (candidate / "_index.md").exists():
        return candidate
    candidate2 = OUTPUT_DIR / title
    if (candidate2 / "_index.md").exists():
        return candidate2
    return None


# ── 缓存 ─────────────────────────────────────────────────────

_cache: dict[str, dict] = {}


def _load_book(title: str, force: bool = False) -> dict:
    if force:
        _cache.pop(title, None)
    if title in _cache:
        return _cache[title]

    book_dir = _find_book_dir(title)
    if not book_dir:
        raise HTTPException(404, f"作品 '{title}' 不存在")

    characters, events, settings = [], [], []

    for md_file in book_dir.rglob("*.md"):
        if md_file.name.startswith("_") or md_file.name == "timeline.md":
            continue
        rel = md_file.relative_to(book_dir)
        if not rel.parts:
            continue
        category = rel.parts[0]
        text = _read_md(md_file)
        if not text:
            continue
        fm = _parse_fm(text)

        if category == "characters" and fm.get("type") == "character":
            name = _extract_name(text, md_file.stem)
            status_m = re.search(r"[🟢⚫🔴🟡⚪]\s*(\S+)", text)
            characters.append({
                "name": name,
                "status": status_m.group(1) if status_m else "未知",
                "gender": fm.get("gender", "未知"),
                "faction": fm.get("faction", ""),
                "role_tags": fm.get("role_tags", []),
                "color": fm.get("color", "character-minor"),
                "identity": _extract_section(text, "身份"),
                "personality": _extract_section(text, "性格"),
                "relationships": _parse_section_links(text, "人际关系"),
                "related_settings": _parse_section_links(text, "关联设定"),
                "events": _parse_section_links(text, "参与事件"),
                "quotes": _extract_section(text, "经典语录"),
                "subfolder": md_file.parent.name,
            })

        elif category == "events" and fm.get("type") == "event":
            name = _extract_name(text, md_file.stem)
            events.append({
                "name": name,
                "time": fm.get("time", ""),
                "chapter": fm.get("chapter", ""),
                "importance": fm.get("importance", "中"),
                "color": fm.get("color", "event-normal"),
                "summary": _body_summary(text),
                "participants": _parse_section_links(text, "参与人物"),
                "location": _parse_section_links(text, "发生地点"),
                "cause": _parse_section_links(text, "前置事件"),
                "effect": _parse_section_links(text, "后续影响"),
                "subfolder": md_file.parent.name,
            })

        elif category == "settings" and fm.get("type") == "setting":
            name = _extract_name(text, md_file.stem)
            settings.append({
                "name": name,
                "setting_type": fm.get("setting_type", "概念"),
                "description": (_extract_section(text, "描述") or _body_summary(text))[:200],
                "characters": _parse_section_links(text, "关联人物"),
                "events": _parse_section_links(text, "关联事件"),
                "subfolder": md_file.parent.name,
            })

    data = {"characters": characters, "events": events, "settings": settings}
    _cache[title] = data
    return data


# ── FastAPI 应用 ──────────────────────────────────────────────

app = FastAPI(title="Story Wiki Web UI")

# 挂载静态文件
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


@app.get("/api/books")
async def api_books():
    """列出所有作品。"""
    books = []
    if not OUTPUT_DIR.exists():
        return {"books": []}
    for child in sorted(OUTPUT_DIR.iterdir()):
        if child.is_dir():
            book_dir = _find_book_dir(child.name)
            if book_dir:
                books.append({"title": child.name})
    return {"books": books}


@app.post("/api/reload")
async def api_reload():
    """清空作品缓存（ingest / 手动改卡后调用，让新数据立即可见）。"""
    _cache.clear()
    return {"reloaded": True}


@app.get("/api/books/{title}/overview")
async def api_overview(title: str):
    """作品概览：统计 + 核心人物 + 摘要。"""
    data = _load_book(title)
    index_file = _find_book_dir(title) / "_index.md"
    index_text = _read_md(index_file) if index_file else ""
    summary = ""
    if index_text:
        # 提取 blockquote 摘要
        for line in index_text.split("\n"):
            line = line.strip()
            if line.startswith("> "):
                summary = line[2:]
                break

    # 核心人物（role_tags 含"主角"或"男主/女主"）
    top_chars = [
        c for c in data["characters"]
        if any(t in (c.get("role_tags") or []) for t in ["主角", "男主", "女主"])
    ][:12]

    # 按角色分组统计
    groups = {"核心人物": 0, "重要配角": 0, "其他人物": 0}
    for c in data["characters"]:
        tags = set(c.get("role_tags") or [])
        if "主角" in tags or "男主" in tags or "女主" in tags:
            groups["核心人物"] += 1
        elif tags - {"路人"}:
            groups["重要配角"] += 1
        else:
            groups["其他人物"] += 1

    return {
        "title": title,
        "summary": summary,
        "stats": {
            "characters": len(data["characters"]),
            "events": len(data["events"]),
            "settings": len(data["settings"]),
        },
        "character_groups": groups,
        "top_characters": [
            {"name": c["name"], "identity": c["identity"], "role_tags": c["role_tags"], "color": c["color"]}
            for c in top_chars
        ],
    }


@app.get("/api/books/{title}/characters")
async def api_characters(title: str, q: str = ""):
    """人物列表，支持搜索。"""
    data = _load_book(title)
    chars = data["characters"]
    if q:
        q_lower = q.lower()
        chars = [
            c for c in chars
            if q_lower in c["name"].lower()
            or q_lower in (c.get("identity") or "").lower()
            or any(q_lower in t.lower() for t in (c.get("role_tags") or []))
        ]
    # 按角色分组
    result = {"核心人物": [], "重要配角": [], "其他人物": []}
    for c in chars:
        tags = set(c.get("role_tags") or [])
        if "主角" in tags or "男主" in tags or "女主" in tags:
            result["核心人物"].append(c)
        elif tags - {"路人"}:
            result["重要配角"].append(c)
        else:
            result["其他人物"].append(c)
    return {"characters": result, "total": len(chars)}


@app.get("/api/books/{title}/characters/{name}")
async def api_character_detail(title: str, name: str):
    """单个人物详情。"""
    data = _load_book(title)
    for c in data["characters"]:
        if c["name"] == name:
            return c
    raise HTTPException(404, f"人物 '{name}' 不存在")


@app.get("/api/books/{title}/graph")
async def api_graph(title: str, depth: int = 1, center: str = ""):
    """关系图数据：nodes + edges。"""
    data = _load_book(title)

    # 角色标签 → 颜色映射（苹果色系）
    color_map = {
        "character-protagonist": "#ff3b30",
        "character-supporting": "#007aff",
        "character-minor": "#8e8e93",
    }

    nodes = []
    node_set = set()
    edges = []
    edge_set = set()

    def add_node(char: dict):
        if char["name"] in node_set:
            return
        node_set.add(char["name"])
        nodes.append({
            "id": char["name"],
            "symbolSize": 20 if "主角" in (char.get("role_tags") or []) else 12,
            "itemStyle": {"color": color_map.get(char["color"], "#8e8e93")},
            "role_tags": char.get("role_tags", []),
            "subfolder": char.get("subfolder", ""),
        })

    # 如果指定了 center，只显示该人物的邻居
    if center:
        center_char = None
        for c in data["characters"]:
            if c["name"] == center:
                center_char = c
                break
        if center_char:
            add_node(center_char)
            neighbor_names = set()
            for r in center_char.get("relationships", []):
                neighbor_names.add(r["name"])
            for nc in data["characters"]:
                if nc["name"] in neighbor_names:
                    add_node(nc)
                    ekey = (center_char["name"], nc["name"])
                    if ekey not in edge_set:
                        edge_set.add(ekey)
                        rel_desc = ""
                        for r in center_char["relationships"]:
                            if r["name"] == nc["name"]:
                                rel_desc = r.get("description", "")
                                break
                        edges.append({
                            "source": center_char["name"],
                            "target": nc["name"],
                            "label": rel_desc[:10],
                        })
    else:
        # 全量：只显示有 ≥1 条关系的人物
        char_names = {c["name"] for c in data["characters"]}
        rel_count: dict[str, int] = {}
        for c in data["characters"]:
            for r in c.get("relationships", []):
                if r["name"] in char_names:
                    rel_count[c["name"]] = rel_count.get(c["name"], 0) + 1
                    rel_count[r["name"]] = rel_count.get(r["name"], 0) + 1

        for c in data["characters"]:
            if rel_count.get(c["name"], 0) >= 1:
                add_node(c)

        for c in data["characters"]:
            for r in c.get("relationships", []):
                if r["name"] in node_set and c["name"] in node_set:
                    ekey = tuple(sorted([c["name"], r["name"]]))
                    if ekey not in edge_set:
                        edge_set.add(ekey)
                        edges.append({
                            "source": c["name"],
                            "target": r["name"],
                            "label": r.get("description", "")[:10],
                        })

    return {"nodes": nodes, "edges": edges}


@app.get("/api/books/{title}/timeline")
async def api_timeline(title: str, importance: str = "", character: str = ""):
    """时间线数据。"""
    data = _load_book(title)
    events = data["events"]

    if importance:
        events = [e for e in events if e["importance"] == importance]

    if character:
        events = [
            e for e in events
            if any(p["name"] == character for p in e.get("participants", []))
        ]

    # 按 importance 排序（高 > 中 > 低）
    imp_order = {"高": 0, "中": 1, "低": 2}
    events.sort(key=lambda e: imp_order.get(e["importance"], 1))

    return {"events": events, "total": len(events)}


@app.get("/api/books/{title}/settings")
async def api_settings_list(title: str):
    """设定与地点列表（04 设定章节用）。"""
    data = _load_book(title)
    return {"settings": data["settings"], "total": len(data["settings"])}


# ── 全局全文检索（SQLite + FTS5） ─────────────────────────────


@app.get("/api/search")
async def api_search(q: str = "", kind: str = "", limit: int = 20):
    """跨作品全文检索实体（人物/事件/设定），走 SQLite FTS5。"""
    if not q.strip():
        return {"results": [], "total": 0}
    try:
        from src.db import connect, search_entities

        conn = connect()
        try:
            results = search_entities(
                conn, q, kind=kind or None, limit=limit
            )
        finally:
            conn.close()
    except ImportError:
        raise HTTPException(503, "SQLite 元数据层不可用（缺少 src/db.py）")
    return {"results": results, "total": len(results)}


# ── 文档上传与后台分析任务 ────────────────────────────────────


@app.post("/api/documents", dependencies=[Depends(require_auth)])
async def api_upload_document(file: UploadFile = File(...), title: str = Form("")):
    """上传待分析文档（txt/md/epub/pdf/docx），保存到 data/input/。"""
    from src.utils import safe_filename

    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            400, f"不支持的格式 {ext or '(无后缀)'}，允许: {', '.join(sorted(ALLOWED_EXTS))}"
        )
    data = await file.read()
    if not data:
        raise HTTPException(400, "上传文件为空")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"文件超过大小限制（{MAX_UPLOAD_BYTES // 1024 // 1024}MB）")

    # 同名不覆盖：追加时间戳后缀
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = safe_filename(Path(filename).stem) or "untitled"
    dest = INPUT_DIR / f"{stem}{ext}"
    if dest.exists():
        import time as _time
        dest = INPUT_DIR / f"{stem}_{_time.strftime('%Y%m%d_%H%M%S')}{ext}"
    dest.write_bytes(data)

    return {
        "filename": dest.name,
        "size": len(data),
        "title": title.strip() or stem,
        "path": str(dest),
    }


@app.post("/api/analyze", dependencies=[Depends(require_auth)])
async def api_start_analyze(payload: dict):
    """
    启动后台分析任务：{"filename": "...", "title": "可选", "incremental": false}

    立即返回 task_id，用 GET /api/tasks/{task_id} 轮询进度。
    """
    from web import tasks as task_mgr

    filename = (payload or {}).get("filename", "")
    if not filename:
        raise HTTPException(400, "缺少 filename")
    file_path = INPUT_DIR / Path(filename).name
    if not file_path.exists():
        raise HTTPException(404, f"文件不存在: {filename}，请先上传")
    if file_path.suffix.lower() not in ALLOWED_EXTS:
        raise HTTPException(400, "不支持的文件格式")

    title = (payload.get("title") or "").strip() or file_path.stem
    incremental = bool(payload.get("incremental", False))

    task_id = task_mgr.create_task(title, file_path.name)
    task_mgr.start_analysis(task_id, file_path, title, OUTPUT_DIR, incremental)
    return {"task_id": task_id, "status": "pending"}


@app.get("/api/tasks/{task_id}")
async def api_task_status(task_id: str):
    """查询后台分析任务进度。"""
    from web import tasks as task_mgr

    task = task_mgr.get_task(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")
    return task


# ── LLM 设置页接口（受鉴权保护）──────────────────────────────


def _settings_payload() -> dict:
    from src import config as app_config

    cfg = app_config.get_llm_config()
    return {
        "api_key_masked": app_config.mask_key(cfg["api_key"]),
        "has_api_key": bool(cfg["api_key"]),
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "auth_enabled": auth_enabled(),
    }


@app.get("/api/settings", dependencies=[Depends(require_auth)])
async def api_get_settings():
    """读取当前 LLM 连接配置（Key 打码返回）。"""
    return _settings_payload()


@app.post("/api/settings", dependencies=[Depends(require_auth)])
async def api_save_settings(payload: dict):
    """保存 LLM 连接配置并写回 .env。api_key 留空表示沿用原值。"""
    from src import config as app_config

    payload = payload or {}
    base_url = (payload.get("base_url") or "").strip()
    if base_url and not base_url.startswith(("http://", "https://")):
        raise HTTPException(400, "BASE_URL 必须以 http:// 或 https:// 开头")

    cfg = app_config.set_llm_config(
        api_key=(payload.get("api_key") or "").strip() or None,
        base_url=base_url or None,
        model=(payload.get("model") or "").strip() or None,
        env_path=BASE_DIR / ".env",  # 仅此处显式持久化
    )
    return {
        "saved": True,
        "api_key_masked": app_config.mask_key(cfg["api_key"]),
        "has_api_key": bool(cfg["api_key"]),
        "base_url": cfg["base_url"],
        "model": cfg["model"],
    }


@app.post("/api/settings/test", dependencies=[Depends(require_auth)])
async def api_test_settings(payload: dict):
    """用（可选的未保存）配置发一次最小补全请求，验证连通性。

    请求体字段留空时回退到已保存配置——便于"先测再存"。
    """
    import time as _time

    import requests as _requests

    from src import config as app_config

    payload = payload or {}
    saved = app_config.get_llm_config()
    base_url = (payload.get("base_url") or "").strip() or saved["base_url"]
    model = (payload.get("model") or "").strip() or saved["model"]
    api_key = (payload.get("api_key") or "").strip() or saved["api_key"]

    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(400, "BASE_URL 必须以 http:// 或 https:// 开头")
    if not api_key:
        return {"ok": False, "message": "未配置 API Key", "latency_ms": 0}

    url = base_url.rstrip("/") + "/v1/chat/completions"
    started = _time.perf_counter()
    try:
        resp = _requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
            timeout=15,
        )
    except _requests.RequestException as exc:
        return {
            "ok": False,
            "message": f"连接失败：{exc.__class__.__name__}",
            "latency_ms": 0,
        }
    latency = int((_time.perf_counter() - started) * 1000)

    if resp.status_code == 200:
        return {"ok": True, "message": f"连接成功（{model}）", "latency_ms": latency}
    if resp.status_code in (401, 403):
        return {"ok": False, "message": "认证失败：API Key 无效", "latency_ms": latency}
    try:
        detail = resp.json().get("error", {}).get("message", "") or resp.text[:120]
    except ValueError:
        detail = resp.text[:120]
    return {"ok": False, "message": f"HTTP {resp.status_code}：{detail}", "latency_ms": latency}


# ── 登录 / 登出（P2 最小鉴权）────────────────────────────────

_LOGIN_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>登录 - Story Wiki</title>
<style>
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         display: flex; align-items: center; justify-content: center;
         min-height: 100vh; margin: 0; background: #f5f5f7; }
  .card { background: #fff; border-radius: 16px; padding: 40px;
          width: 320px; box-shadow: 0 4px 24px rgba(0,0,0,.08); }
  h1 { font-size: 20px; margin: 0 0 8px; color: #1d1d1f; }
  p  { font-size: 13px; color: #8e8e93; margin: 0 0 24px; }
  input { width: 100%; box-sizing: border-box; padding: 11px 12px;
          border: 1px solid #d1d1d6; border-radius: 8px; font-size: 14px;
          margin-bottom: 14px; }
  button { width: 100%; padding: 11px; border: none; border-radius: 8px;
           background: #007aff; color: #fff; font-size: 14px;
           font-weight: 600; cursor: pointer; }
  .err { color: #ff3b30; font-size: 13px; margin-bottom: 12px; min-height: 16px; }
</style>
</head>
<body>
  <form class="card" method="post" action="/login">
    <h1>Story Wiki</h1>
    <p>请输入访问密码</p>
    <div class="err">{error}</div>
    <input type="password" name="password" placeholder="访问密码" autofocus>
    <button type="submit">登 录</button>
  </form>
</body>
</html>"""


@app.get("/login")
async def login_page(error: str = ""):
    """登录页（鉴权未开启时直接跳首页）。"""
    if not auth_enabled():
        return RedirectResponse("/")
    return HTMLResponse(_LOGIN_PAGE.replace("{error}", error))


@app.post("/login")
async def login_submit(request: Request):
    """校验密码并种下 session cookie。"""
    if not auth_enabled():
        return RedirectResponse("/")
    form = await request.form()
    password = str(form.get("password", ""))
    if verify_password(password):
        response = RedirectResponse("/", status_code=303)
        set_session(response)
        return response
    return HTMLResponse(
        _LOGIN_PAGE.replace("{error}", "密码错误，请重试"), status_code=401
    )


@app.post("/logout")
async def logout():
    """登出：清除 session cookie。"""
    response = RedirectResponse("/", status_code=303)
    clear_session(response)
    return response
