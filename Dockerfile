ARG UV_VERSION=0.11.32

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH="/app/.venv/bin:${PATH}"

COPY --from=uv /uv /uvx /usr/local/bin/

RUN groupadd --gid 10001 appuser \
    && useradd --create-home --uid 10001 \
        --gid appuser appuser

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project \
    && python -m playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright

COPY --chown=appuser:appuser . .
RUN uv sync --locked --no-dev \
    && mkdir -p /app/data/logs \
    && chown -R appuser:appuser /app/data

USER appuser

CMD ["python", "-m", "bot.main"]
