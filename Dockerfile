FROM python:3.11-slim

LABEL org.opencontainers.image.title="Noteyard"
LABEL org.opencontainers.image.description="Local copy-first Apple Notes recovery and review toolkit with a stdio MCP surface."
LABEL org.opencontainers.image.source="https://github.com/xiaojiou176-open/noteyard"
LABEL io.modelcontextprotocol.server.name="io.github.xiaojiou176-open/noteyard-mcp"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

COPY . /workspace

RUN python -m pip install --upgrade pip && \
    python -m pip install ".[mcp]"

CMD ["notes-recovery", "--help"]
