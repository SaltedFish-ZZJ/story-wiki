#!/usr/bin/env bash
# Story Wiki 一键启动（Linux/macOS）
# 首次运行会自动创建虚拟环境并安装依赖

set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "[Story Wiki] 创建虚拟环境..."
    python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -c "import fastapi" 2>/dev/null; then
    echo "[Story Wiki] 安装依赖..."
    python -m pip install -e ".[web,formats,office]"
fi

echo "[Story Wiki] 构建 SQLite 索引..."
python -m src.indexer

echo "[Story Wiki] 启动 Web 界面: http://127.0.0.1:8000"
exec python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
