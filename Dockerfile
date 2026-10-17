# Story Wiki 生产镜像
# 构建：docker build -t story-wiki .
# 运行：docker run -p 8000:8000 --env-file .env story-wiki
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖再拷代码，充分利用层缓存
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e ".[web,formats,office]"

COPY src/ ./src/
COPY web/ ./web/
COPY docs/ ./docs/
COPY .env.example ./

# 非 root 运行；data/ 与 vault/ 通过挂载卷提供
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/data /app/vault \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/books')" || exit 1

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
