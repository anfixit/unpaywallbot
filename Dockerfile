FROM python:3.12-slim

# Без .pyc в контейнере, без буферизации stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Не запускаем от root (§13.2)
RUN useradd -m appuser
WORKDIR /app

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest \
    /uv /usr/local/bin/uv

# Зависимости отдельным слоем (кэш Docker)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Playwright (chromium для headless-методов)
RUN uv run playwright install --with-deps chromium

# Копируем код
COPY --chown=appuser:appuser . .

USER appuser

CMD ["uv", "run", "python", "-m", "bot.main"]
