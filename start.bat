@echo off
REM Story Wiki 一键启动（Windows）
REM 首次运行会自动创建虚拟环境并安装依赖

cd /d "%~dp0"

if not exist .venv (
    echo [Story Wiki] 创建虚拟环境...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo [Story Wiki] 安装依赖...
    python -m pip install -e ".[web,formats,office]"
)

echo [Story Wiki] 构建 SQLite 索引...
python -m src.indexer

echo [Story Wiki] 启动 Web 界面: http://127.0.0.1:8000
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
