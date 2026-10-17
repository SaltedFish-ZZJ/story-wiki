"""
Story Wiki - Web 上传与后台分析任务测试
覆盖：POST /api/documents（格式/大小/空文件校验）、POST /api/analyze、
GET /api/tasks/{id} 轮询、任务成功/失败路径、失败回滚、docx 提取。
"""
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import web.app as webapp  # noqa: E402
from web import tasks as task_mgr  # noqa: E402
from src.extractor import extract_text  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """隔离输入/输出目录的测试客户端。"""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.setattr(webapp, "INPUT_DIR", input_dir)
    monkeypatch.setattr(webapp, "OUTPUT_DIR", output_dir)
    return TestClient(webapp.app), input_dir, output_dir


def _wait_task(task_id: str, timeout: float = 10.0) -> dict:
    """轮询等待任务结束（后台线程）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        t = task_mgr.get_task(task_id)
        if t and t["status"] in ("done", "failed"):
            return t
        time.sleep(0.05)
    raise TimeoutError(f"任务 {task_id} 未在 {timeout}s 内结束")


# ── POST /api/documents ──────────────────────────────────────


class TestUpload:
    def test_upload_txt(self, client):
        client, input_dir, _ = client
        resp = client.post(
            "/api/documents",
            files={"file": ("测试小说.txt", "第一章 开始\n正文内容".encode("utf-8"), "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "测试小说.txt"
        assert data["title"] == "测试小说"
        assert (input_dir / "测试小说.txt").read_bytes().startswith("第一章".encode())

    def test_upload_rejects_bad_ext(self, client):
        client, _, _ = client
        resp = client.post(
            "/api/documents",
            files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_upload_rejects_empty(self, client):
        client, _, _ = client
        resp = client.post(
            "/api/documents", files={"file": ("empty.txt", b"", "text/plain")}
        )
        assert resp.status_code == 400

    def test_upload_no_overwrite(self, client):
        client, input_dir, _ = client
        for _ in range(2):
            resp = client.post(
                "/api/documents", files={"file": ("同名.txt", b"content", "text/plain")}
            )
            assert resp.status_code == 200
        txts = list(input_dir.glob("同名*.txt"))
        assert len(txts) == 2  # 第二次自动加时间戳后缀

    def test_upload_custom_title(self, client):
        client, _, _ = client
        resp = client.post(
            "/api/documents",
            files={"file": ("raw_name.txt", b"x", "text/plain")},
            data={"title": "我的书"},
        )
        assert resp.json()["title"] == "我的书"


# ── POST /api/analyze + GET /api/tasks ───────────────────────


class TestAnalyzeTask:
    def _fake_analysis(self, title="测试之书"):
        return {
            "title": title,
            "summary": "测试简介",
            "characters": [{"name": "甲", "identity": "主角"}],
            "settings": [],
            "events": [],
        }

    def test_unknown_file_404(self, client):
        client, _, _ = client
        resp = client.post("/api/analyze", json={"filename": "不存在.txt"})
        assert resp.status_code == 404

    def test_missing_filename_400(self, client):
        client, _, _ = client
        resp = client.post("/api/analyze", json={})
        assert resp.status_code == 400

    def test_task_success_flow(self, client, monkeypatch):
        """成功路径：analyze → generate（写 _index.md）→ done 100%。"""
        client, input_dir, output_dir = client
        (input_dir / "书.txt").write_text("第一章 开端\n内容", encoding="utf-8")

        import src.pipeline as pipeline_mod
        import src.generator as generator_mod

        monkeypatch.setattr(
            pipeline_mod, "analyze_chaptered",
            lambda text, title=None, **kw: self._fake_analysis(title or "书"),
        )

        def fake_generate(analysis, output_dir=None):
            out = Path(output_dir) if output_dir else webapp.OUTPUT_DIR
            book = out / analysis["title"] / analysis["title"]
            book.mkdir(parents=True, exist_ok=True)
            (book / "_index.md").write_text(
                f"---\ntype: book\ntags: [book]\n---\n# {analysis['title']}\n",
                encoding="utf-8",
            )
            return [str(book / "_index.md")]

        monkeypatch.setattr(generator_mod, "generate_vault", fake_generate)

        resp = client.post("/api/analyze", json={"filename": "书.txt"})
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        task = _wait_task(task_id)
        assert task["status"] == "done"
        assert task["progress"] == 100

        # HTTP 查询同一任务
        r2 = client.get(f"/api/tasks/{task_id}")
        assert r2.status_code == 200
        assert r2.json()["status"] == "done"

        # 新书出现在作品列表（书名默认取文件名 stem）
        books = client.get("/api/books").json()["books"]
        assert any(b["title"] == "书" for b in books)

    def test_task_failure_and_rollback(self, client, monkeypatch):
        """失败路径：分析抛异常 → failed + error 信息，不留半成品目录。"""
        client, input_dir, output_dir = client
        (input_dir / "坏书.txt").write_text("第一章 开端\n内容", encoding="utf-8")

        import src.pipeline as pipeline_mod

        def boom(text, title=None, **kw):
            raise RuntimeError("LLM 连接超时")

        monkeypatch.setattr(pipeline_mod, "analyze_chaptered", boom)

        resp = client.post("/api/analyze", json={"filename": "坏书.txt"})
        task_id = resp.json()["task_id"]
        task = _wait_task(task_id)

        assert task["status"] == "failed"
        assert "LLM 连接超时" in task["error"]
        assert list(output_dir.iterdir()) == []  # 无半成品

    def test_task_404(self, client):
        client, _, _ = client
        assert client.get("/api/tasks/no-such-id").status_code == 404


# ── 任务表基础行为 ───────────────────────────────────────────


class TestTaskRegistry:
    def test_create_and_get(self):
        tid = task_mgr.create_task("书名", "书名.txt")
        t = task_mgr.get_task(tid)
        assert t["status"] == "pending"
        assert t["title"] == "书名"
        assert task_mgr.get_task("nonexistent") is None

    def test_update_fields(self):
        tid = task_mgr.create_task("书名", "书名.txt")
        task_mgr._update(tid, progress=50, message="halfway")
        assert task_mgr.get_task(tid)["progress"] == 50


# ── docx 提取 ────────────────────────────────────────────────


class TestDocxExtraction:
    def test_extract_docx_paragraphs_and_tables(self, tmp_path):
        pytest.importorskip("docx")
        import docx as docx_lib

        path = tmp_path / "报告.docx"
        document = docx_lib.Document()
        document.add_paragraph("第一章 合同签署")
        document.add_paragraph("甲方与乙方达成合作。")
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "项目"
        table.rows[0].cells[1].text = "金额"
        document.save(str(path))

        text = extract_text(str(path))
        assert "第一章 合同签署" in text
        assert "甲方与乙方达成合作。" in text
        assert "项目 | 金额" in text  # 表格按行拼接

    def test_docx_missing_dependency_message(self, tmp_path, monkeypatch):
        """未安装 python-docx 时报错信息带安装指引。"""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "docx":
                raise ImportError("No module named 'docx'")
            return real_import(name, *args, **kwargs)

        path = tmp_path / "x.docx"
        path.write_bytes(b"fake")
        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(ImportError, match="story-wiki\\[office\\]"):
            extract_text(str(path))
