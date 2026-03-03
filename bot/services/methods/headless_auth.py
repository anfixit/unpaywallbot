"""Метод обхода hard paywall через headless-браузер.

Принцип: для hard paywall контента нет в DOM без
валидной сессии. Используем Playwright для запуска
браузера, логина и извлечения контента.
"""

import asyncio
import logging

from playwright.async_api import (
    Page,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeout,
)

from bot.auth.account_manager import (
    Account,
    AccountManager,
)
from bot.models.article import Article
from bot.services.content_extractor import (
    ContentExtractor,
)
from bot.utils.url_utils import normalize_url

__all__ = ['fetch_via_headless_auth']

logger = logging.getLogger(__name__)

_BROWSER_TIMEOUT = 30_000
_NAVIGATION_TIMEOUT = 30_000
_CONTENT_WAIT_TIMEOUT = 10_000
_LOGIN_FORM_TIMEOUT = 5_000
_LOGIN_REDIRECT_TIMEOUT = 10_000
_FALLBACK_WAIT = 2

_DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36'
)

_CONTENT_SELECTORS = (
    'article, .article, .content, main'
)


async def fetch_via_headless_auth(
    url: str,
    user_id: int,
    account_manager: AccountManager,
    extractor: ContentExtractor | None = None,
) -> Article | None:
    """Извлечь статью через headless-браузер.

    Args:
        url: URL статьи.
        user_id: ID пользователя Telegram.
        account_manager: Менеджер аккаунтов.
        extractor: Экстрактор контента.

    Returns:
        Article или None.

    Raises:
        RuntimeError: Нет аккаунта или браузера.
    """
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    account = (
        await account_manager.get_account_for_url(
            norm_url, user_id,
        )
    )
    if not account:
        msg = f'Нет аккаунта для {norm_url}'
        raise RuntimeError(msg)

    if extractor is None:
        extractor = ContentExtractor()

    browser = None
    context = None
    page = None

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features'
                '=AutomationControlled',
            ],
        )

        context = await browser.new_context(
            viewport={
                'width': 1280,
                'height': 800,
            },
            user_agent=_DEFAULT_USER_AGENT,
        )

        if account.session_cookies:
            await context.add_cookies(
                account.session_cookies,
            )

        page = await context.new_page()
        page.set_default_timeout(_BROWSER_TIMEOUT)

        response = await page.goto(
            norm_url,
            wait_until='networkidle',
            timeout=_NAVIGATION_TIMEOUT,
        )

        if not response or response.status >= 400:
            status = (
                response.status if response
                else 'unknown'
            )
            msg = f'HTTP {status}'
            raise RuntimeError(msg)

        # Проверяем, не выкинуло ли на логин
        if _is_login_page(page.url):
            logger.info(
                'Редирект на логин для %s',
                norm_url,
            )
            await _handle_login(page, account)
            await page.goto(
                norm_url,
                wait_until='networkidle',
            )

        try:
            await page.wait_for_selector(
                _CONTENT_SELECTORS,
                timeout=_CONTENT_WAIT_TIMEOUT,
            )
        except PlaywrightTimeout:
            logger.debug(
                'Контент-селектор не найден '
                'за %dms, ждём fallback',
                _CONTENT_WAIT_TIMEOUT,
            )
            await asyncio.sleep(_FALLBACK_WAIT)

        html = await page.content()

        # Обновляем cookies для следующего раза
        account.session_cookies = (
            await context.cookies()
        )
        await account_manager.save_account(account)

        return extractor.extract(html, norm_url)

    finally:
        if page:
            await page.close()
        if context:
            await context.close()
        if browser:
            await browser.close()


def _is_login_page(url: str) -> bool:
    """Проверить, является ли URL логин-страницей."""
    lower = url.lower()
    return 'login' in lower or 'signin' in lower


async def _handle_login(
    page: Page,
    account: Account,
) -> None:
    """Обработать логин на странице.

    Args:
        page: Страница браузера.
        account: Аккаунт с email/password.
    """
    await page.wait_for_selector(
        'form, input[type="email"], '
        'input[type="password"]',
        timeout=_LOGIN_FORM_TIMEOUT,
    )

    email_selectors = [
        'input[type="email"]',
        'input[name="email"]',
        'input[name="login"]',
    ]
    pass_selectors = [
        'input[type="password"]',
        'input[name="password"]',
    ]

    for selector in email_selectors:
        if await page.locator(selector).count():
            await page.fill(
                selector, account.email,
            )
            break

    for selector in pass_selectors:
        if await page.locator(selector).count():
            await page.fill(
                selector, account.password,
            )
            break

    submit_selectors = [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Login")',
    ]
    for selector in submit_selectors:
        if await page.locator(selector).count():
            await page.click(selector)
            break

    await page.wait_for_url(
        '**/*',
        wait_until='networkidle',
        timeout=_LOGIN_REDIRECT_TIMEOUT,
    )
