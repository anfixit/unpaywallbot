"""Метод обхода hard paywall через headless-браузер с авторизацией.

Принцип работы: для hard paywall (Times, FT, Republic) контента нет в DOM
без валидной сессии. Используем Playwright для запуска браузера,
логинимся и забираем контент.
"""

import asyncio

from playwright.async_api import Page, async_playwright

from bot.auth.account_manager import AccountManager
from bot.models.article import Article
from bot.services.content_extractor import ContentExtractor
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_headless_auth']

# Константы для браузера
BROWSER_TIMEOUT = 30000  # 30 секунд
NAVIGATION_TIMEOUT = 30000
WAIT_FOR_CONTENT_TIMEOUT = 10000


async def fetch_via_headless_auth(
    url: str,
    user_id: int,
    account_manager: AccountManager,
    extractor: ContentExtractor | None = None,
) -> Article | None:
    """Извлечь статью через headless-браузер с авторизацией.

    Запускает браузер, логинится (если нужно) и забирает контент.
    Требует установленного playwright и браузеров.

    Args:
        url: URL статьи.
        user_id: ID пользователя Telegram (для получения аккаунта).
        account_manager: Менеджер аккаунтов.
        extractor: Экстрактор контента.

    Returns:
        Объект Article или None, если не удалось.

    Raises:
        RuntimeError: Если не удалось получить аккаунт или запустить браузер.
    """
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    # Получаем аккаунт для этого домена
    account = await account_manager.get_account_for_url(norm_url, user_id)
    if not account:
        raise RuntimeError(f'Нет доступного аккаунта для {norm_url}')

    if extractor is None:
        extractor = ContentExtractor()

    browser = None
    context = None
    page = None

    try:
        # Запускаем браузер
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled'],
        )

        # Создаём контекст с сохранёнными куками
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        )

        # Восстанавливаем сессию
        if account.session_cookies:
            await context.add_cookies(account.session_cookies)

        page = await context.new_page()
        page.set_default_timeout(BROWSER_TIMEOUT)

        # Переходим на страницу
        response = await page.goto(
            norm_url,
            wait_until='networkidle',
            timeout=NAVIGATION_TIMEOUT,
        )

        if not response or response.status >= 400:
            raise RuntimeError(f'HTTP {response.status if response else "unknown"}')

        # Проверяем, не выкинуло ли на логин
        if 'login' in page.url.lower() or 'signin' in page.url.lower():
            # Пробуем залогиниться
            await _handle_login(page, account)

            # Снова идём на статью
            await page.goto(norm_url, wait_until='networkidle')

        # Ждём появления контента
        try:
            await page.wait_for_selector('article, .article, .content, main', timeout=WAIT_FOR_CONTENT_TIMEOUT)
        except:
            # Если нет явного селектора, просто подождём
            await asyncio.sleep(2)

        # Получаем HTML
        html = await page.content()

        # Сохраняем обновлённые куки
        account.session_cookies = await context.cookies()
        await account_manager.save_account(account)

        # Извлекаем контент
        article = extractor.extract(html, norm_url)

        return article

    finally:
        # Закрываем всё аккуратно
        if page:
            await page.close()
        if context:
            await context.close()
        if browser:
            await browser.close()


async def _handle_login(page: Page, account: 'Account') -> None:
    """Обработать логин, если потребовался.

    Args:
        page: Страница браузера.
        account: Аккаунт с логином/паролем.
    """
    # Ждём форму логина
    await page.wait_for_selector('form, input[type="email"], input[type="password"]', timeout=5000)

    # Пробуем разные селекторы для полей
    email_selectors = ['input[type="email"]', 'input[name="email"]', 'input[name="login"]']
    pass_selectors = ['input[type="password"]', 'input[name="password"]']

    # Заполняем email
    for selector in email_selectors:
        if await page.locator(selector).count():
            await page.fill(selector, account.email)
            break

    # Заполняем пароль
    for selector in pass_selectors:
        if await page.locator(selector).count():
            await page.fill(selector, account.password)
            break

    # Жмём кнопку submit
    submit_selectors = ['button[type="submit"]', 'input[type="submit"]', 'button:has-text("Login")']
    for selector in submit_selectors:
        if await page.locator(selector).count():
            await page.click(selector)
            break

    # Ждём редиректа
    await page.wait_for_url('**/*', wait_until='networkidle', timeout=10000)
