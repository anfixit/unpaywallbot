# Unpaywall Bot

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-blue.svg)](http://mypy-lang.org/)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://img.shields.io/badge/tests-pytest-orange.svg)](https://docs.pytest.org/)

**Pet - роект по информационной безопасности**
Автор: [anfixit](https://github.com/anfixit)

---

## О проекте

Unpaywall Bot — исследовательский Telegram-бот, демонстрирующий уязвимости клиентских paywall-систем ведущих новостных изданий.

### Цель исследования

Показать, что soft/metered paywall, реализованные на стороне клиента (JavaScript overlay), не являются надёжным средством защиты контента, и предложить рекомендации по усилению защиты.

### Поддерживаемые издания

| Издание | Тип paywall | Метод обхода | Сложность |
|---------|-------------|--------------|-----------|
| The Telegraph | Soft | Отключение JS | Низкая |
| NY Times | Metered | Googlebot spoof | Средняя |
| The Times UK | Hard | Headless + auth | Высокая |
| Spiegel, Zeit, FAZ | Freemium | JS disable + маркеры S+/Z+/F+ | Средняя |
| Sueddeutsche | Freemium | `?reduced=true` | Средняя |
| New Yorker, Vanity Fair | Metered | Googlebot spoof | Средняя |
| Republic.io | Hard | Headless + auth | Высокая |

---

## Архитектура

```
Пользователь --> Telegram Bot --> Классификатор --> Оркестратор
                                                        |
                         +----------+----------+--------+--------+
                         |          |          |        |        |
                    js_disable  googlebot  german  headless  archive
                         |          |          |        |        |
                         +----------+----------+--------+--------+
                                        |
                                  Content Extractor --> Redis Cache --> Пользователь
```

### Ключевые компоненты

| Компонент | Назначение |
|-----------|------------|
| `orchestrator.py` | Координация всех этапов обработки |
| `paywall_classifier.py` | Определение типа paywall по YAML-конфигу |
| `methods/` | Базовые методы обхода (JS disable, Googlebot, headless) |
| `platforms/` | Специфичная логика для конкретных изданий |
| `storage/` | Кеширование статей в Redis |
| `auth/` | Шифрованное хранение сессий и аккаунтов |
| `middleware/` | Rate limiting, аудит, белый список |

Полная диаграмма: [`docs/architecture.mermaid`](docs/architecture.mermaid)

---

## Быстрый старт

### Предварительные требования

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (рекомендуется) или pip
- Redis
- Playwright (для headless-методов)

### Установка

```bash
git clone https://github.com/anfixit/unpaywallbot.git
cd unpaywallbot

uv sync --all-extras
uv run playwright install chromium

cp .env.example .env.local
# Отредактировать .env.local: BOT_TOKEN, ENCRYPTION_KEY
```

### Запуск

```bash
# Redis
docker compose up -d redis

# Бот
uv run python -m bot.main
```

### Запуск через Docker

```bash
cp .env.example .env.production
# Отредактировать .env.production

docker compose up -d
docker compose logs -f bot
```

---

## Конфигурация

### Переменные окружения

| Переменная | Обязательная | Описание |
|------------|:------------:|----------|
| `BOT_TOKEN` | да | Токен Telegram-бота от BotFather |
| `ENCRYPTION_KEY` | да | Ключ шифрования сессий (мин. 16 символов) |
| `REDIS_URL` | нет | URL Redis (по умолчанию `redis://localhost:6379/0`) |
| `ALLOWED_USERS` | нет | Whitelist Telegram user_id через запятую |
| `LOG_LEVEL` | нет | Уровень логирования (по умолчанию `INFO`) |
| `ENV` | нет | Окружение: `development` или `production` |

### Конфигурация paywall

Файл `data/paywall_map.yaml` содержит маппинг доменов на типы paywall и методы обхода. Подробности — в комментариях внутри файла.

---

## Тестирование

```bash
# Все тесты с покрытием
uv run pytest

# Конкретный модуль
uv run pytest tests/test_classifier.py -v

# Интеграционный тест (требует сеть)
uv run pytest tests/test_telegraph.py -v
```

### Тестирование конкретного URL

```bash
uv run python -m scripts.test_paywall https://www.spiegel.de/plus/artikel -v
```

### Линтинг и типизация

```bash
uv run ruff check bot/
uv run mypy bot/
```

---

## Управление аккаунтами

```bash
# Общий аккаунт
uv run python -m scripts.register_accounts \
    --domain nytimes.com \
    --email user@example.com \
    --password securepass \
    --shared

# Личный аккаунт
uv run python -m scripts.register_accounts \
    --domain spiegel.de \
    --email user@example.com \
    --password securepass \
    --user-id 123456789
```

Все credentials хранятся в зашифрованном виде (Fernet + PBKDF2).

---

## Аналитика

```bash
uv run python -m scripts.generate_report --days 30
```

Для глубокого анализа: `notebooks/analysis.ipynb`.

---

## Рекомендации по защите

По результатам исследования, эффективная защита paywall требует:

1. **Server-side content gating** — не отдавать полный текст без авторизации
2. **Googlebot IP verification** — проверять через reverse DNS
3. **Behavioral analytics** — отслеживать mouse movements, scroll depth
4. **Rate limiting** — ограничить число статей на аккаунт
5. **Блокировка datacenter IP** — обычные читатели не приходят с VPS
6. **JS challenge** — Datadome / PerimeterX перед отдачей контента

---

## Структура проекта

```
unpaywallbot/
├── bot/                        # Основной код
│   ├── auth/                   # Шифрование и аккаунты
│   ├── handlers/               # Telegram-хендлеры
│   ├── middleware/             # Rate limiting, аудит, whitelist
│   ├── models/                 # Датаклассы (Article, PaywallInfo)
│   ├── services/               # Бизнес-логика
│   │   ├── methods/            # Методы обхода
│   │   ├── platforms/          # Платформенная специфика
│   │   ├── orchestrator.py     # Оркестратор
│   │   └── protocols.py        # PlatformProtocol (PEP 544)
│   ├── storage/                # Redis и кеш
│   └── utils/                  # URL, текст, логирование
├── data/                       # Конфиги и данные
├── docs/                       # Документация
├── scripts/                    # CLI-утилиты
├── tests/                      # Тесты (pytest)
├── notebooks/                  # Jupyter для анализа
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## Технологический стек

| Категория | Инструменты |
|-----------|-------------|
| Язык | Python 3.12 |
| Telegram | Aiogram 3.x |
| Конфигурация | Pydantic Settings |
| HTTP | HTTPX, Playwright |
| Парсинг | readability-lxml |
| Кеш | Redis |
| Безопасность | cryptography (Fernet + PBKDF2) |
| Логирование | QueueHandler + QueueListener (async-safe) |
| Тестирование | pytest, pytest-asyncio, pytest-cov |
| Линтер | Ruff |
| Типизация | mypy (strict) |
| Пакетный менеджер | uv |
| Контейнеризация | Docker, Docker Compose |

---

## Модель угроз

Документ: [`docs/threat_model.md`](docs/threat_model.md)

| Угроза | Вероятность | Влияние | Меры защиты |
|--------|:-----------:|:-------:|-------------|
| Утечка токена бота | Низкая | Высокое | `.env` + `SecretStr` |
| Компрометация аккаунтов | Средняя | Высокое | Fernet-шифрование |
| DoS через бота | Средняя | Среднее | Rate limiting middleware |
| Юридические претензии | Низкая | Высокое | Дисклеймер, research only |

---

## Лицензия

Распространяется под лицензией [GNU Affero General Public License v3.0](LICENSE)

Код предоставляется исключительно в образовательных целях.

---

## Дисклеймер

> Данный инструмент создан **исключительно для образовательных целей** и авторизованного тестирования безопасности. Автор не несёт ответственности за любое незаконное использование. Перед использованием убедитесь, что ваши действия не нарушают законодательство вашей страны и условия использования целевых сайтов.

---

## Контакты

- Telegram: [@Anfikus](https://t.me/Anfikus)
- GitHub: [@anfixit](https://github.com/anfixit)
