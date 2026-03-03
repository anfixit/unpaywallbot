# Unpaywall Bot

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-blue.svg)](http://mypy-lang.org/)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://img.shields.io/badge/tests-pytest-orange.svg)](https://docs.pytest.org/)

**Дипломный проект по информационной безопасности**
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
| `ALLOWED_USERS` | нет | Whitelist Telegram user_id в формате JSON-массива (`[123, 456]`) |
| `LOG_LEVEL` | нет | Уровень логирования (по умолчанию `INFO`) |
| `ENV` | нет | Окружение: `development` или `production` |

### Конфигурация paywall

Файл `data/paywall_map.yaml` содержит маппинг доменов на типы paywall и методы обхода. Подробности — в комментариях внутри файла.

---

## CI/CD

Проект использует GitHub Actions с многоступенчатым pipeline:

```
lint ─────────┐
typecheck ────┤
test ─────────┼──► docker push ──► deploy ──► telegram notify
security ─────┘
```

### Этапы pipeline

| Этап | Инструмент | Описание |
|------|-----------|----------|
| Lint | Ruff | Статический анализ кода |
| Types | mypy | Проверка типизации |
| Tests | pytest | 99 тестов, coverage ≥ 60% |
| Security | pip-audit | Аудит зависимостей на CVE (§8.9) |
| Docker | GHCR | Сборка и push образа в GitHub Container Registry |
| Deploy | SSH | Обновление кода и перезапуск сервиса на сервере |
| Notify | Telegram | Уведомление о результате деплоя |

Docker-образ публикуется с двумя тегами: `latest` и SHA коммита (для возможности отката).

### Настройка секретов

GitHub → Settings → Secrets and variables → Actions:

**Environment secrets** (environment `production`):

| Секрет | Описание |
|--------|----------|
| `BOT_TOKEN` | Токен Telegram-бота |
| `ENCRYPTION_KEY` | Ключ шифрования сессий |
| `ALLOWED_USERS` | JSON-массив разрешённых user_id (`[]` для открытого доступа) |
| `TELEGRAM_CHAT_ID` | Telegram ID для уведомлений о деплое |

**Repository secrets:**

| Секрет | Описание |
|--------|----------|
| `SSH_HOST` | IP-адрес сервера |
| `SSH_USER` | Пользователь для SSH (`deploy`) |
| `SSH_PRIVATE_KEY` | Приватный SSH-ключ |
| `DEPLOY_PATH` | Путь к проекту на сервере |

---

## Деплой на сервер

### Подготовка сервера

#### 1. Пользователь и SSH

```bash
# Создать пользователя deploy
sudo adduser deploy
sudo usermod -aG sudo deploy

# Настроить SSH-ключи
su - deploy
mkdir -p ~/.ssh && chmod 700 ~/.ssh
# Добавить публичный ключ в ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### 2. Системные зависимости

```bash
sudo apt update && sudo apt install -y \
    python3.12 python3.12-venv \
    git curl redis-server
```

#### 3. Установка uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 4. Структура проекта

```bash
sudo mkdir -p /opt/projects/unpaywallbot
sudo chown deploy:deploy /opt/projects/unpaywallbot
sudo mkdir -p /var/log/unpaywallbot
sudo chown deploy:deploy /var/log/unpaywallbot

cd /opt/projects
git clone git@github.com:anfixit/unpaywallbot.git
cd unpaywallbot
uv sync --no-dev
uv run playwright install --with-deps chromium
```

#### 5. Systemd-сервис

Создать `/etc/systemd/system/unpaywallbot.service`:

```ini
[Unit]
Description=Unpaywall Bot
After=network.target redis-server.service
Wants=redis-server.service

[Service]
User=deploy
WorkingDirectory=/opt/projects/unpaywallbot
ExecStart=/home/deploy/.local/bin/uv run python -m bot.main
Restart=always
StandardOutput=append:/var/log/unpaywallbot/out.log
StandardError=append:/var/log/unpaywallbot/err.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable unpaywallbot
sudo systemctl start unpaywallbot
```

#### 6. Sudo без пароля (только для CI/CD)

Создать `/etc/sudoers.d/deploy`:

```
deploy ALL=(ALL) NOPASSWD: \
    /usr/bin/systemctl restart unpaywallbot, \
    /usr/bin/systemctl is-active unpaywallbot, \
    /usr/bin/systemctl is-active --quiet unpaywallbot, \
    /usr/bin/systemctl status unpaywallbot --no-pager, \
    /usr/bin/journalctl -u unpaywallbot -n 30 --no-pager
```

#### 7. Redis

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping  # → PONG
```

### Ручной деплой

```bash
ssh deploy@<server-ip>
cd /opt/projects/unpaywallbot
git pull origin main
uv sync --no-dev
sudo systemctl restart unpaywallbot
sudo systemctl status unpaywallbot
```

При push в `main` деплой происходит автоматически через GitHub Actions.

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
├── .github/workflows/          # CI/CD pipeline
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
| CI/CD | GitHub Actions, GHCR |
| Деплой | systemd, SSH |

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

Код предоставляется исключительно в исследовательских и образовательных целях.

---

## Дисклеймер

> Данный инструмент создан **исключительно для исследовательских целей** и авторизованного тестирования безопасности. Автор не несёт ответственности за любое незаконное использование. Перед использованием убедитесь, что ваши действия не нарушают законодательство вашей страны и условия использования целевых сайтов.

---

## Контакты

- Telegram: [@Anfikus](https://t.me/Anfikus)
- GitHub: [@anfixit](https://github.com/anfixit)
