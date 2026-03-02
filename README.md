# 🤖 Unpaywall Bot — Исследование уязвимостей paywall-систем

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)

**Проект по информационной безопасности**  
Автор: Anfixit

---

## 📋 О проекте

**Unpaywall Bot** — это исследовательский Telegram-бот, демонстрирующий уязвимости клиентских paywall-систем ведущих новостных изданий.

### 🎯 Цель исследования

Показать, что **soft/metered paywall**, реализованные на стороне клиента (JavaScript overlay), не являются надёжным средством защиты контента, и предложить рекомендации по усилению защиты.

### 📊 Поддерживаемые издания

| Издание | Тип paywall | Метод обхода | Сложность |
|---------|-------------|--------------|-----------|
| The Telegraph | Soft | Отключение JS | Низкая |
| NY Times | Metered | Googlebot spoof | Средняя |
| The Times UK | Hard | Headless + auth | Высокая |
| **Spiegel, Zeit, FAZ** | Freemium | JS disable + маркеры S+/Z+/F+ | Средняя |
| **Süddeutsche** | Freemium | `?reduced=true` | Средняя |
| **New Yorker, Vanity Fair** | Metered | Googlebot spoof | Средняя |
| **Republic.io** | Hard | Headless + auth | Высокая |

---

## 🏗️ Архитектура

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Пользователь│────▶│ Telegram Bot │────▶│  Классификатор│
└─────────────┘     └──────────────┘     └─────────────┘
                           │                      │
                           ▼                      ▼
                    ┌──────────────┐     ┌─────────────┐
                    │  Оркестратор │◀────│ paywall_map │
                    └──────────────┘     └─────────────┘
                           │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │ Методы   │    │Платформы │    │  Кеш     │
   │ обхода   │    │          │    │ (Redis)  │
   └──────────┘    └──────────┘    └──────────┘
```

### 🧩 Ключевые компоненты

| Компонент | Назначение |
|-----------|------------|
| **`orchestrator.py`** | Координация всех этапов обработки |
| **`paywall_classifier.py`** | Определение типа paywall по YAML-конфигу |
| **`methods/`** | Базовые методы обхода (JS disable, Googlebot, headless) |
| **`platforms/`** | Специфичная логика для конкретных изданий |
| **`storage/`** | Кеширование статей в Redis |
| **`auth/`** | Шифрованное хранение сессий и аккаунтов |
| **`middleware/`** | Rate limiting, аудит, белый список |

---

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (рекомендуется) или pip
- Redis (для продакшена)
- Playwright (для headless-методов)

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/anfixit/unpaywallbot.git
cd unpaywallbot

# 2. Установить зависимости через uv
uv sync --all-extras

# 3. Установить Playwright
uv run playwright install chromium

# 4. Создать файл с переменными окружения
cp .env.example .env.local
# Отредактировать .env.local, добавить BOT_TOKEN и ENCRYPTION_KEY

# 5. Запустить Redis (или использовать docker-compose)
docker-compose up -d redis

# 6. Запустить бота
uv run python -m bot.main
```

### 🐳 Запуск через Docker

```bash
# Создать .env.production с продакшен-токенами
cp .env.example .env.production

# Запустить всё сразу
docker-compose up -d

# Посмотреть логи
docker-compose logs -f bot
```

---

## 🔧 Конфигурация

### Переменные окружения (`.env`)

```env
# Telegram
BOT_TOKEN=your_telegram_bot_token

# Redis
REDIS_URL=redis://localhost:6379/0

# Безопасность
ENCRYPTION_KEY=your_32_char_encryption_key
ALLOWED_USERS=123456789,987654321  # опционально

# Логирование
LOG_LEVEL=INFO

# Окружение
ENV=development  # или production
```

### Конфигурация paywall (`data/paywall_map.yaml`)

```yaml
spiegel.de:
  type: freemium
  platform: german_freemium
  method: js_disable

nytimes.com:
  type: metered
  method: googlebot_spoof

thetimes.com:
  type: hard
  method: headless_auth
```

---

## 🧪 Тестирование

```bash
# Запустить все тесты
uv run pytest

# С покрытием
uv run pytest --cov=bot --cov-report=html

# Конкретный тест
uv run pytest tests/test_methods_js_disable.py -v

# Интеграционный тест Telegraph
uv run pytest tests/test_telegraph.py -v
```

### Быстрое тестирование URL

```bash
# Проверить конкретную статью
uv run python scripts/test_paywall.py https://www.spiegel.de/plus/artikel --verbose

# С имитацией пользователя
uv run python scripts/test_paywall.py https://nytimes.com/article --user-id 123
```

---

## 📊 Анализ и отчёты

### Генерация статистики из логов

```bash
# Анализ за последние 7 дней
uv run python scripts/generate_report.py

# За 30 дней
uv run python scripts/generate_report.py --days 30
```

### Jupyter Notebook для глубокого анализа

```bash
uv run jupyter notebook notebooks/analysis.ipynb
```

Примеры аналитики:
- Распределение типов paywall
- Процент успешных обходов
- Время ответа по методам
- Топ пользователей
- Динамика по дням

---

## 👤 Управление аккаунтами

### Добавление аккаунта

```bash
# Общий аккаунт для всех пользователей
uv run python scripts/register_accounts.py \
  --domain nytimes.com \
  --email user@example.com \
  --password securepass \
  --shared

# Личный аккаунт для конкретного пользователя Telegram
uv run python scripts/register_accounts.py \
  --domain spiegel.de \
  --email user@example.com \
  --password securepass \
  --user-id 123456789
```

### Шифрование

Все сессии и cookies хранятся в зашифрованном виде с использованием `cryptography.Fernet`. Ключ шифрования задаётся в `ENCRYPTION_KEY`.

---

## 🛡️ Безопасность

### Принятые меры

| Угроза | Защита |
|--------|--------|
| Утечка токена бота | `SecretStr` в Pydantic, `.env` не в git |
| Компрометация сессий | Шифрование всех cookies |
| DOS-атаки | Rate limiting (10/мин, 30/час, 100/день) |
| Неавторизованный доступ | Whitelist middleware |
| Утечка данных в логи | Никаких секретов в логах |

### Рекомендации для продакшена

- [ ] Использовать разные токены для dev/prod
- [ ] Включить `DEBUG=false` в продакшене
- [ ] Настроить резервное копирование Redis
- [ ] Регулярно обновлять зависимости (`uv run pip-audit`)
- [ ] Мониторинг через Sentry (опционально)

---

## 📈 Результаты исследования

> **Ключевой вывод:** Soft и metered paywall, реализованные на стороне клиента (JavaScript overlay), не являются надёжным средством защиты контента. Автоматизированный инструмент способен обходить такую защиту с минимальными затратами.

### По каждому изданию

| Издание | Вывод |
|---------|-------|
| **The Telegraph** | Полный текст в DOM, отключение JS полностью обходит paywall |
| **NY Times** | ML-модель усложняет массовый обход, но контент всё ещё в DOM |
| **The Times UK** | Hard paywall — контент не в DOM, требует headless + авторизацию |
| **Spiegel/Zeit/FAZ** | Freemium-маркеры требуют проверки, но базовый контент доступен |
| **Republic.io** | Hard paywall с антибот-защитой, только через headless |

### Рекомендации издателям

1. **Server-side content gating** — не отдавать полный текст без авторизации
2. **Googlebot IP verification** — проверять через reverse DNS
3. **Behavioral analytics** — отслеживать mouse movements, scroll depth
4. **Rate limiting** — ограничить число статей на аккаунт
5. **Блокировка datacenter IP** — обычные читатели не приходят с VPS
6. **JS challenge** — Datadome / PerimeterX перед отдачей контента

---

## 🧰 Технологический стек

| Категория | Инструменты |
|-----------|-------------|
| **Язык** | Python 3.12 |
| **Telegram** | Aiogram 3.x |
| **Конфигурация** | Pydantic Settings + .env |
| **HTTP** | HTTPX, Playwright |
| **Парсинг** | BeautifulSoup4, readability-lxml |
| **Кеш** | Redis |
| **Безопасность** | Cryptography (Fernet) |
| **Логирование** | Structured logging (JSON) |
| **Тестирование** | Pytest, pytest-cov, pytest-asyncio |
| **Линтер/Форматтер** | Ruff |
| **Типизация** | Mypy |
| **Пакетный менеджер** | uv |
| **Контейнеризация** | Docker, Docker Compose |

---

## 📁 Структура проекта

```
unpaywallbot/
├── bot/                      # Основной код
│   ├── auth/                 # Авторизация и аккаунты
│   ├── handlers/             # Telegram-хендлеры
│   ├── middleware/           # Rate limiting, аудит, whitelist
│   ├── models/               # Датаклассы (Article, PaywallInfo)
│   ├── services/             # Бизнес-логика
│   │   ├── methods/          # Методы обхода
│   │   ├── platforms/        # Платформенная специфика
│   │   └── orchestrator.py   # Оркестратор
│   ├── storage/              # Redis и кеш
│   └── utils/                # Утилиты
├── data/                      # Данные
│   ├── logs/                  # Логи (JSON)
│   ├── sessions/              # Зашифрованные сессии
│   ├── paywall_map.yaml       # Конфигурация paywall
│   └── user_agents.yaml       # База User-Agent
├── docs/                       # Документация для диплома
├── scripts/                    # Вспомогательные скрипты
├── tests/                      # Тесты
├── notebooks/                   # Jupyter для анализа
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml              # Зависимости и конфиги
└── README.md
```

---

## 📝 Лицензия

Этот проект распространяется под лицензией **GNU Affero General Public License v3.0**.  
Код предоставляется исключительно в образовательных целях и для исследований в области информационной безопасности.

---

## ⚠️ Дисклеймер

> Данный инструмент создан **исключительно для образовательных целей** и авторизованного тестирования безопасности. Автор не несёт ответственности за любое незаконное использование. Перед использованием убедитесь, что ваши действия не нарушают законодательство вашей страны и условия использования целевых сайтов.

---

## 📬 Контакты

По вопросам исследования и сотрудничества:  
- Telegram: [@Anfikus](https://t.me/Anfikus)  
- GitHub: [@anfixit](https://github.com/anfixit)

---

**Сделано с ❤️ к информационной безопасности**
