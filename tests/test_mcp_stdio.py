"""
Story Wiki - MCP server 真实协议层冒烟测试

子进程启动 stdio server，走完整 MCP 握手：
initialize → notifications/initialized → tools/list → tools/call

此前 21 个 MCP 测试只直接调用工具函数，未验证真实客户端接入路径。
本文件保证 Claude Desktop 等外部 MCP 客户端按标准协议接入时可用。
"""

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest

pytest.importorskip("mcp")

ROOT = Path(__file__).resolve().parent.parent
INIT_TIMEOUT = 60  # 首次响应含 Python/mcp SDK 导入，放宽


@pytest.fixture(scope="module")
def proc():
    p = subprocess.Popen(
        [sys.executable, str(ROOT / "web" / "mcp_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
    )
    yield p
    p.kill()
    p.wait(timeout=10)


@pytest.fixture(scope="module")
def lines(proc):
    """后台线程持续收集 stdout 行，主线程带超时消费（防 pipe 死锁）。"""
    q: queue.Queue = queue.Queue()

    def pump():
        try:
            for line in proc.stdout:
                q.put(line)
        except ValueError:
            pass
        q.put(None)  # EOF 标记

    threading.Thread(target=pump, daemon=True).start()
    return q


def send(proc, obj):
    proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def recv(lines, want_id, timeout=INIT_TIMEOUT):
    """读取指定 id 的 JSON-RPC 响应，跳过通知/日志等无关行。"""
    while True:
        line = lines.get(timeout=timeout)
        if line is None:
            pytest.fail("MCP server stdout 提前关闭")
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == want_id:
            return msg


def test_stdio_full_handshake(proc, lines):
    """initialize → initialized → tools/list → tools/call 全链路。"""
    # 1) initialize 握手
    send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "smoke-test", "version": "0"}}})
    init = recv(lines, 1)
    assert "error" not in init, init
    assert init["result"]["serverInfo"]["name"]

    # 2) initialized 通知（无 id，无响应）
    send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    # 3) tools/list → 9 个只读工具
    send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = recv(lines, 2, timeout=30)
    assert "error" not in tools, tools
    names = [t["name"] for t in tools["result"]["tools"]]
    assert len(names) == 9
    for expected in ("list_books", "search", "get_character",
                     "get_event", "get_setting", "get_timeline", "get_graph"):
        assert expected in names

    # 4) tools/call → list_books 真实执行（读本地库）
    send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "list_books", "arguments": {}}})
    call = recv(lines, 3, timeout=30)
    assert "error" not in call, call
    assert call["result"]["isError"] is False
    payload = json.loads(call["result"]["content"][0]["text"])
    assert "books" in payload


def test_stdio_tool_error_is_data_not_crash(proc, lines):
    """查询不存在的书：业务层返回 error 字段，进程不崩溃、协议层无错误。"""
    send(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "get_character",
                           "arguments": {"book": "不存在的书", "name": "不存在的人"}}})
    call = recv(lines, 4, timeout=30)
    assert "error" not in call, call          # 协议层无 JSON-RPC error
    assert call["result"]["isError"] is False  # 工具层不抛异常
    payload = json.loads(call["result"]["content"][0]["text"])
    assert payload.get("error")               # 业务层报错信息

    # 进程仍存活，可继续服务后续请求
    send(proc, {"jsonrpc": "2.0", "id": 5, "method": "tools/list"})
    assert "error" not in recv(lines, 5, timeout=30)
