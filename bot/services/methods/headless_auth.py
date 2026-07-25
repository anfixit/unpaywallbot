"""Authenticated headless browser extraction.

The default bot runtime does not enable this component. It is kept
for explicitly configured research environments with owned accounts.
"""

import asyncio
import logging

from playwright.async_api import (
    Page,
    Playwright,
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
from bot.services.content_extractor import ContentExtractor
from bot.utils.url_utils import (
    is_same_domain,
    normalize_url,
)

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
    """Extract a page with an explicitly configured account."""
    norm_url = normalize_url(url)
    if not norm_url:
        return None

    account = await account_manager.get_account_for_url(
        norm_url,
        user_id,
    )
    if not account:
        msg = f'Нет аккаунта для {norm_url}'
        raise RuntimeError(msg)

    if extractor is None:
        extractor = ContentExtractor()

    playwright: Playwright | None = None
    browser = None
    context = None
    page = None

    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
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
            # Playwright does not expose SetCookieParam at runtime.
            # Stored cookies are validated by Playwright on insertion.
            await context.add_cookies(
                account.session_cookies,  # type: ignore[arg-type]
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

        if _is_login_page(page.url):
            if not is_same_domain(page.url, norm_url):
                msg = (
                    'Cross-domain login redirect blocked: '
                    f'{page.url}'
                )
                raise RuntimeError(msg)

            logger.info(
                'Редирект на login для %s',
                norm_url,
            )
            await _handle_login(page, account)
            await page.goto(
                norm_url,
                wait_until='networkidle',
                timeout=_NAVIGATION_TIMEOUT,
            )

        try:
            await page.wait_for_selector(
                _CONTENT_SELECTORS,
                timeout=_CONTENT_WAIT_TIMEOUT,
            )
        except PlaywrightTimeout:
            logger.debug(
                'Контент-селектор не найден за %dms',
                _CONTENT_WAIT_TIMEOUT,
            )
            await asyncio.sleep(_FALLBACK_WAIT)

        html = await page.content()

        cookies = await context.cookies()
        account.session_cookies = [
            dict(cookie) for cookie in cookies
        ]
        await account_manager.save_account(account)

        return extractor.extract(html, norm_url)
    finally:
        if page:
            await page.close()
        if context:
            await context.close()
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


def _is_login_page(url: str) -> bool:
    """Check whether the current URL is a login page."""
    lower = url.lower()
    return 'login' in lower or 'signin' in lower


async def _handle_login(
    page: Page,
    account: Account,
) -> None:
    """Fill a same-domain login form."""
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
    password_selectors = [
        'input[type="password"]',
        'input[name="password"]',
    ]

    email_filled = False
    for selector in email_selectors:
        if await page.locator(selector).count():
            await page.fill(
                selector,
                account.email,
            )
            email_filled = True
            break

    password_filled = False
    for selector in password_selectors:
        if await page.locator(selector).count():
            await page.fill(
                selector,
                account.password,
            )
            password_filled = True
            break

    if not email_filled or not password_filled:
        msg = 'Login form fields not found'
        raise RuntimeError(msg)

    submit_selectors = [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Login")',
    ]
    for selector in submit_selectors:
        if await page.locator(selector).count():
            await page.click(selector)
            break
    else:
        msg = 'Login submit button not found'
        raise RuntimeError(msg)

    await page.wait_for_url(
        '**/*',
        wait_until='networkidle',
        timeout=_LOGIN_REDIRECT_TIMEOUT,
    )
