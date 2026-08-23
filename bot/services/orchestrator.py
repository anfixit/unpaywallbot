"""Координация классификации, извлечения и кеша."""

import logging

import httpx

from bot.auth.account_manager import AccountManager
from bot.constants import BypassMethod, PaywallType
from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.models.user_request import UserRequest
from bot.services.content_extractor import ContentExtractor
from bot.services.methods.archive_relay import fetch_via_archive
from bot.services.methods.googlebot_spoof import (
    fetch_via_googlebot_spoof,
)
from bot.services.methods.headless_auth import fetch_via_headless_auth
from bot.services.methods.js_disable import fetch_via_js_disable
from bot.services.methods.wsj import fetch_via_wsj
from bot.services.paywall_classifier import PaywallClassifier
from bot.services.platforms.conde_nast import CondeNastPlatform
from bot.services.platforms.german_freemium import (
    GermanFreemiumPlatform,
)
from bot.services.platforms.republic import RepublicPlatform
from bot.services.protocols import PlatformProtocol
from bot.storage.cache import (
    get_cached_article,
    save_article_to_cache,
)
from bot.utils.url_utils import extract_domain

__all__ = ['Orchestrator']

logger = logging.getLogger(__name__)

# Ошибки, после которых остаётся смысл пробовать
# другой источник, а не сообщать о сбое обработки.
_RECOVERABLE_ERRORS = (
    httpx.HTTPError,
    OSError,
    RuntimeError,
)


class Orchestrator:
    """Координировать обработку пользовательского URL."""

    def __init__(
        self,
        classifier: PaywallClassifier | None = None,
        account_manager: AccountManager | None = None,
        extractor: ContentExtractor | None = None,
    ) -> None:
        """Инициализировать зависимости оркестратора."""
        self.classifier = classifier or PaywallClassifier()
        self.account_manager = account_manager
        self.extractor = extractor or ContentExtractor()
        self.platforms: dict[str, PlatformProtocol] = {
            'german_freemium': GermanFreemiumPlatform(
                extractor=self.extractor,
                account_manager=self.account_manager,
            ),
            'conde_nast': CondeNastPlatform(
                extractor=self.extractor,
            ),
            'republic': RepublicPlatform(
                extractor=self.extractor,
                account_manager=self.account_manager,
            ),
        }

    async def process_url(
        self,
        url: str,
        user_id: int | None = None,
        skip_cache: bool = False,
    ) -> UserRequest:
        """Классифицировать URL и получить доступный текст."""
        request = UserRequest(
            user_id=user_id or 0,
            original_url=url,
        )

        try:
            if not skip_cache:
                cached = await get_cached_article(url)
                if cached:
                    return await self._complete(
                        request,
                        cached,
                        cache_article=False,
                    )

            paywall_info = await self.classifier.classify(url)
            request.paywall_info = paywall_info

            if not paywall_info.is_known:
                article = await self._handle_unknown(url)
                return await self._complete(
                    request,
                    article,
                    PaywallType.UNKNOWN,
                )

            platform_name = paywall_info.platform
            if platform_name and platform_name in self.platforms:
                article = await self._run_platform(
                    self.platforms[platform_name],
                    platform_name,
                    url,
                    paywall_info,
                    user_id,
                )
                return await self._complete(
                    request,
                    article,
                    paywall_info.paywall_type,
                    paywall_info.suggested_method,
                )

            if paywall_info.suggested_method:
                article = await self._fetch_with_method(
                    url,
                    paywall_info.suggested_method,
                    user_id,
                )
                if not article or article.is_empty:
                    article = await self._fallback(url)
                return await self._complete(
                    request,
                    article,
                    paywall_info.paywall_type,
                    paywall_info.suggested_method,
                )

            article = await self._handle_unknown(url)
            return await self._complete(
                request,
                article,
                PaywallType.UNKNOWN,
            )
        except Exception:
            logger.exception(
                'Ошибка обработки домена: %s',
                extract_domain(url),
            )
            request.complete(
                error=RuntimeError(
                    'Внутренняя ошибка обработки',
                ),
            )
            return request

    async def _run_platform(
        self,
        platform: PlatformProtocol,
        platform_name: str,
        url: str,
        paywall_info: PaywallInfo,
        user_id: int | None,
    ) -> Article | None:
        """Выполнить платформенный обработчик.

        Платформа сама выбирает стратегию. Сетевая
        или конфигурационная ошибка не должна ронять
        запрос: в этом случае пробуем публичный архив.
        """
        try:
            return await platform.handle(
                url,
                paywall_info,
                user_id=user_id,
            )
        except _RECOVERABLE_ERRORS:
            logger.warning(
                'Платформа %s не отработала для %s',
                platform_name,
                extract_domain(url),
                exc_info=True,
            )
            return await self._fallback(url)

    async def _handle_unknown(
        self,
        url: str,
    ) -> Article | None:
        """Попробовать публичные методы по очереди."""
        domain = extract_domain(url)
        methods = (
            ('js_disable', fetch_via_js_disable),
            ('googlebot', fetch_via_googlebot_spoof),
            ('archive', fetch_via_archive),
        )

        for name, fetcher in methods:
            try:
                article = await fetcher(
                    url,
                    extractor=self.extractor,
                )
            except (httpx.HTTPError, OSError):
                logger.debug(
                    '%s: сетевая ошибка для %s',
                    name,
                    domain,
                    exc_info=True,
                )
                continue

            if article and not article.is_empty:
                return article

        return None

    async def _fallback(
        self,
        url: str,
    ) -> Article | None:
        """Попробовать существующий archive.ph snapshot."""
        domain = extract_domain(url)
        logger.info('Fallback archive.ph для %s', domain)
        try:
            return await fetch_via_archive(
                url,
                extractor=self.extractor,
            )
        except (httpx.HTTPError, OSError):
            logger.warning(
                'archive.ph fallback: ошибка для %s',
                domain,
                exc_info=True,
            )
            return None

    async def _complete(
        self,
        request: UserRequest,
        article: Article | None,
        paywall_type: PaywallType | None = None,
        proposed_method: BypassMethod | None = None,
        *,
        cache_article: bool = True,
    ) -> UserRequest:
        """Завершить запрос и дождаться записи в кеш."""
        if article and paywall_type:
            article.paywall_type = paywall_type
        if (
            article
            and proposed_method
            and article.extraction_method is None
        ):
            article.extraction_method = proposed_method

        request.complete(article=article)
        if article and cache_article:
            await save_article_to_cache(article)
        return request

    async def _fetch_with_method(
        self,
        url: str,
        method: BypassMethod,
        user_id: int | None = None,
    ) -> Article | None:
        """Выполнить метод, не роняя запрос на ошибке.

        Возвращает None, если метод недоступен или
        упал: вызывающий код перейдёт к архивному
        fallback.
        """
        try:
            return await self._dispatch_method(
                url,
                method,
                user_id,
            )
        except _RECOVERABLE_ERRORS:
            logger.warning(
                'Метод %s не отработал для %s',
                method,
                extract_domain(url),
                exc_info=True,
            )
            return None

    async def _dispatch_method(
        self,
        url: str,
        method: BypassMethod,
        user_id: int | None = None,
    ) -> Article | None:
        """Выполнить выбранный метод извлечения."""
        if method == BypassMethod.JS_DISABLE:
            return await fetch_via_js_disable(
                url,
                extractor=self.extractor,
            )

        if method == BypassMethod.ARCHIVE_RELAY:
            return await fetch_via_archive(
                url,
                extractor=self.extractor,
            )

        if method == BypassMethod.GOOGLEBOT_SPOOF:
            return await fetch_via_googlebot_spoof(
                url,
                extractor=self.extractor,
            )

        if method == BypassMethod.HEADLESS_AUTH:
            if not user_id or not self.account_manager:
                return None
            return await fetch_via_headless_auth(
                url,
                user_id=user_id,
                account_manager=self.account_manager,
                extractor=self.extractor,
            )

        if method == BypassMethod.WSJ_BYPASS:
            return await fetch_via_wsj(
                url,
                extractor=self.extractor,
            )

        return None
