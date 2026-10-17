"""
Story Wiki - Web 后台分析任务管理
用标准库 threading 实现单并发后台任务：上传的书在后台线程跑完整分析管线，
前端通过 GET /api/tasks/{task_id} 轮询进度。

任务状态存内存（重启即清空），只保留最近 _MAX_TASKS 条防止无限增长。
"""
from __future__ import annotations

import shutil
import threading
import uuid
from collections import OrderedDict
from pathlib import Path

from src.logging_setup import get_logger

logger = get_logger("web.tasks")

# 单并发：同一时间只跑一个分析任务（LLM API 有速率限制，排队即可）
_TASK_LOCK = threading.Lock()
_RUN_LOCK = threading.Condition(_TASK_LOCK)
_RUNNING = False

_tasks: OrderedDict[str, dict] = OrderedDict()
_MAX_TASKS = 200


def _update(task_id: str, **fields) -> None:
    with _TASK_LOCK:
        task = _tasks.get(task_id)
        if task:
            task.update(fields)


def create_task(title: str, filename: str) -> str:
    """登记一个 pending 任务，返回 task_id。"""
    task_id = uuid.uuid4().hex[:12]
    with _TASK_LOCK:
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",       # pending / running / done / failed
            "progress": 0,             # 0-100
            "message": "排队中",
            "title": title,
            "filename": filename,
            "error": None,
            "created_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        }
        # 超限清理：丢掉最早的已完成任务
        while len(_tasks) > _MAX_TASKS:
            for tid, t in list(_tasks.items()):
                if t["status"] in ("done", "failed"):
                    del _tasks[tid]
                    break
            else:
                break
    return task_id


def get_task(task_id: str) -> dict | None:
    with _TASK_LOCK:
        t = _tasks.get(task_id)
        return dict(t) if t else None


def start_analysis(task_id: str, file_path: Path, title: str,
                   output_dir: Path, incremental: bool = False) -> None:
    """启动后台线程执行分析（单并发排队）。"""
    thread = threading.Thread(
        target=_run_with_lock,
        args=(task_id, file_path, title, output_dir, incremental),
        daemon=True,
        name=f"analyze-{task_id}",
    )
    thread.start()


def _run_with_lock(task_id: str, file_path: Path, title: str,
                   output_dir: Path, incremental: bool) -> None:
    """同一时间只允许一个分析任务在跑，其余排队等前一个结束。"""
    global _RUNNING
    with _RUN_LOCK:
        while _RUNNING:
            _RUN_LOCK.wait(timeout=600)  # 最多等 10 分钟，防死锁
        _RUNNING = True
    try:
        _run(task_id, file_path, title, output_dir, incremental)
    finally:
        with _RUN_LOCK:
            _RUNNING = False
            _RUN_LOCK.notify_all()


def _run(task_id: str, file_path: Path, title: str,
         output_dir: Path, incremental: bool) -> None:
    """执行完整分析管线，进度分档：提取 10% / 章节 15-85% / 生成 90% / 入库 100%。"""
    try:
        _update(task_id, status="running", progress=5, message="读取文件...")

        # 1. 提取文本
        from src.extractor import extract_text
        text = extract_text(str(file_path))
        if not text.strip():
            raise ValueError("提取到的文本为空，无法分析")
        _update(task_id, progress=10, message=f"提取完成，共 {len(text):,} 字")

        # 2. 分章分析（AI 调用，占大头）
        from src.pipeline import analyze_chaptered

        def on_chapter_start(chapter) -> None:
            _update(task_id, message=f"分析第 {chapter.index} 章：{chapter.title}")

        def on_chapter_done(chapter, result) -> None:
            # 进度按章数推进：15% → 85%
            _update(task_id, progress=15 + int(70 * chapter.index / max(chapter.index, 1)),
                    message=f"完成第 {chapter.index} 章：{chapter.title}")

        analysis = analyze_chaptered(
            text, title=title,
            on_chapter_start=on_chapter_start, on_chapter_done=on_chapter_done,
        )

        # 3. 生成卡片（失败时回滚新建的书目录，不留半成品）
        book_dir = output_dir / Path(analysis.get("title", title)).name
        existed_before = book_dir.exists()
        _update(task_id, progress=90, message="生成 Obsidian 卡片...")
        from src.generator import generate_vault
        generate_vault(analysis, output_dir=output_dir)

        # 4. 完成入库由 generator._auto_index 钩子自动完成
        n_chars = len(analysis.get("characters", []))
        _update(task_id, status="done", progress=100,
                message=f"完成《{analysis.get('title', title)}》："
                        f"{n_chars} 个人物已入库")

    except Exception as exc:  # noqa: BLE001 — 后台任务兜底，任何失败都记到任务上
        logger.exception(f"分析任务 {task_id} 失败")
        _rollback(output_dir, file_path.parent.name)
        _update(task_id, status="failed", progress=100,
                message="分析失败", error=str(exc)[:500])


def _rollback(output_dir: Path, _unused: str) -> None:
    """失败回滚：删除本次分析新建但未完成的半成品书目录（已有目录不动）。"""
    # 简单策略：输出目录下 mtime 在最近 30 分钟内、且无 _index.md 的书目录视为半成品
    import time

    if not output_dir.exists():
        return
    now = time.time()
    for child in output_dir.iterdir():
        if not child.is_dir():
            continue
        book_dir = child / child.name
        target = book_dir if book_dir.exists() else child
        try:
            recent = now - child.stat().st_mtime < 1800
            has_index = (book_dir / "_index.md").exists()
            if recent and not has_index:
                shutil.rmtree(child, ignore_errors=True)
                logger.warning(f"已回滚半成品目录: {child}")
        except OSError:
            continue
