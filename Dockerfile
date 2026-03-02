FROM python:3.12-slim

WORKDIR /app

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Копируем зависимости
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Копируем код
COPY . .

# Устанавливаем Playwright
RUN uv run playwright install chromium

# Запуск
CMD ["uv", "run", "python", "-m", "bot.main"]
