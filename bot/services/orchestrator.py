"""Оркестратор — координация всех компонентов.

Собирает вместе классификатор, платформы, методы
обхода, кеш, экстрактор и менеджер аккаунтов.
"""

import asyncio
import logging

import httpx

from bot.auth.account_manager import AccountManager
from bot.constants import BypassMethod, PaywallType
from bot.models.article import Article
from bot.models.user_request import UserRequest
from bot.services.content_extractor import (
    ContentExtractor,
)
from bot.services.methods.archive_relay import (
    fetch_via_archive,
)
from bot.services.methods.googlebot_spoof import (
    fetch_via_googlebot_spoof,
)
from bot.services.methods.headless_auth import (
    fetch_via_headless_auth,
)
from bot.services.methods.js_disable import (
    fetch_via_js_disable,
)
from bot.services.methods.wsj import (
    fetch_via_wsj,
)
from bot.services.paywall_classifier import (
    PaywallClassifier,
)
from bot.services.platforms.conde_nast import (
    CondeNastPlatform,
)
from bot.services.platforms.german_freemium import (
    GermanFreemiumPlatform,
)
from bot.services.platforms.republic import (
    RepublicPlatform,
)
from bot.services.protocols import PlatformProtocol
from bot.storage.cache import (
    get_cached_article,
    save_article_to_cache,
)

__all__ = ['Orchestrator']

logger = logging.getLogger(__name__)

# Множество для хранения ссылок на фоновые задачи.
# Предотвращает сборку GC до завершения (§17.5).
_background_tasks: set[asyncio.Task] = set()


class Orchestrator:
    """Оркестратор — координация всех компонентов."""

    def __init__(
        self,
        classifier: (
            PaywallClassifier | None
        ) = None,
        account_manager: (
            AccountManager | None
        ) = None,
        extractor: (
            ContentExtractor | None
        ) = None,
    ) -> None:
        """Инициализировать оркестратор.

        Args:
            classifier: Классификатор paywall.
            account_manager: Менеджер аккаунтов.
            extractor: Экстрактор контента.
        """
        self.classifier = (
            classifier or PaywallClassifier()
        )
        self.account_manager = account_manager
        self.extractor = (
            extractor or ContentExtractor()
        )

        self.platforms: dict[
            str, PlatformProtocol
        ] = {
            'german_freemium': (
                GermanFreemiumPlatform(
                    extractor=self.extractor,
                    account_manager=(
                        self.account_manager
                    ),
                )
            ),
            'conde_nast': CondeNastPlatform(
                extractor=self.extractor,
            ),
            'republic': RepublicPlatform(
                extractor=self.extractor,
                account_manager=(
                    self.account_manager
                ),
            ),
        }

    async def process_url(
        self,
        url: str,
        user_id: int | None = None,
        username: str | None = None,
        skip_cache: bool = False,
    ) -> UserRequest:
        """Обработать URL: классификация -> обход.

        Каждая ветка завершается fallback на
        archive.ph, чтобы минимизировать
        «не удалось получить статью».

        Args:
            url: URL статьи.
            user_id: ID пользователя Telegram.
            username: Имя пользователя.
            skip_cache: Игнорировать кеш.

        Returns:
            UserRequest с результатами.
        """
        request = UserRequest(
            user_id=user_id or 0,
            username=username,
            original_url=url,
        )

        try:
            # 1. Кеш
            if not skip_cache:
                cached = await get_cached_article(
                    url,
                )
                if cached:
                    return self._complete(
                        request, cached,
                    )

            # 2. Классификация
            paywall_info = (
                await self.classifier.classify(url)
            )
            request.paywall_info = paywall_info

            # 3. Неизвестный тип ->
            #    js_disable -> archive.ph
            if not paywall_info.is_known:
                article = (
                    await self._handle_unknown(url)
                )
                return self._complete(
                    request, article,
                    PaywallType.UNKNOWN,
                    BypassMethod.JS_DISABLE,
                )

            # 4. Есть платформа -> делегируем
            platform_name = paywall_info.platform
            if (
                platform_name
                and platform_name in self.platforms
            ):
                platform = self.platforms[
                    platform_name
                ]
                article = await platform.handle(
                    url,
                    paywall_info,
                    user_id=user_id,
                )
                # Платформы сами делают fallback,
                # но если всё равно None:
                if not article or article.is_empty:
                    article = (
                        await self._fallback(url)
                    )
                return self._complete(
                    request, article,
                    paywall_info.paywall_type,
                    paywall_info.suggested_method,
                )

            # 5. Есть метод -> используем + fallback
            if paywall_info.suggested_method:
                article = (
                    await self._fetch_with_method(
                        url,
                        paywall_info.suggested_method,
                        user_id,
                    )
                )
                if not article or article.is_empty:
                    article = (
                        await self._fallback(url)
                    )
                return self._complete(
                    request, article,
                    paywall_info.paywall_type,
                    paywall_info.suggested_method,
                )

            # 6. Ни платформы, ни метода
            article = (
                await self._handle_unknown(url)
            )
            return self._complete(
                request, article,
                PaywallType.UNKNOWN,
                BypassMethod.ARCHIVE_RELAY,
            )

        except Exception:
            logger.exception(
                'Ошибка обработки URL: %s', url,
            )
            request.complete(error=Exception(
                'Внутренняя ошибка обработки',
            ))
            return request

    async def _handle_unknown(
        self,
        url: str,
    ) -> Article | None:
        """Обработать неизвестный сайт.

        js_disable -> googlebot -> archive.ph.
        Каждый шаг обёрнут в try/except — сетевые
        ошибки не должны прерывать цепочку.

        Args:
            url: URL статьи.

        Returns:
            Article или None.
        """
        # 1. js_disable — быстро, работает для
        #    большинства soft paywall
        try:
            article = await fetch_via_js_disable(
                url, extractor=self.extractor,
            )
            if article and not article.is_empty:
                return article
        except (
            httpx.HTTPError,
            OSError,
        ):
            logger.debug(
                'js_disable: сетевая ошибка'
                ' для %s',
                url,
                exc_info=True,
            )

        # 2. googlebot — для metered
        logger.debug(
            'js_disable не помог для %s,'
            ' пробуем googlebot',
            url,
        )
        try:
            article = (
                await fetch_via_googlebot_spoof(
                    url, extractor=self.extractor,
                )
            )
            if article and not article.is_empty:
                return article
        except (
            httpx.HTTPError,
            OSError,
        ):
            logger.debug(
                'googlebot: сетевая ошибка'
                ' для %s',
                url,
                exc_info=True,
            )

        # 3. archive.ph — последний шанс
        logger.debug(
            'googlebot не помог для %s,'
            ' пробуем archive.ph',
            url,
        )
        try:
            return await fetch_via_archive(
                url, extractor=self.extractor,
            )
        except (
            httpx.HTTPError,
            OSError,
        ):
            logger.warning(
                'archive.ph: сетевая ошибка'
                ' для %s',
                url,
                exc_info=True,
            )
            return None

    async def _fallback(
        self,
        url: str,
    ) -> Article | None:
        """Универсальный fallback: archive.ph.

        Args:
            url: URL статьи.

        Returns:
            Article или None.
        """
        logger.info(
            'Fallback archive.ph для %s', url,
        )
        try:
            return await fetch_via_archive(
                url, extractor=self.extractor,
            )
        except (
            httpx.HTTPError,
            OSError,
        ):
            logger.warning(
                'archive.ph fallback: сетевая'
                ' ошибка для %s',
                url,
                exc_info=True,
            )
            return None

    def _complete(
        self,
        request: UserRequest,
        article: Article | None,
        paywall_type: (
            PaywallType | None
        ) = None,
        method: BypassMethod | None = None,
    ) -> UserRequest:
        """Завершить запрос и закешировать.

        Args:
            request: Текущий запрос.
            article: Извлечённая статья.
            paywall_type: Тип paywall.
            method: Метод обхода.

        Returns:
            Тот же request с заполненными полями.
        """
        if article and paywall_type:
            article.paywall_type = paywall_type
        if article and method:
            article.extraction_method = method

        request.complete(article=article)

        if article:
            self._schedule_cache(article)

        return request

    @staticmethod
    def _schedule_cache(
        article: Article,
    ) -> None:
        """Поставить кеширование в фон.

        Не падает если Redis не подключён —
        кеш опционален.
        """
        try:
            # Проверяем что Redis доступен
            from bot.storage.redis_client import (
                get_redis_client,
            )
            redis = get_redis_client()
            if redis._redis is None:
                return
        except Exception:
            return

        task = asyncio.create_task(
            save_article_to_cache(article),
        )
        _background_tasks.add(task)
        task.add_done_callback(
            _background_tasks.discard,
        )

    async def _fetch_with_method(
        self,
        url: str,
        method: BypassMethod,
        user_id: int | None = None,
    ) -> Article | None:
        """Вызвать конкретный метод обхода.

        Args:
            url: URL статьи.
            method: Метод обхода.
            user_id: ID пользователя (headless).

        Returns:
            Article или None.
        """
        if method == BypassMethod.JS_DISABLE:
            return await fetch_via_js_disable(
                url, extractor=self.extractor,
            )

        if method == BypassMethod.ARCHIVE_RELAY:
            return await fetch_via_archive(
                url, extractor=self.extractor,
            )

        if method == BypassMethod.GOOGLEBOT_SPOOF:
            return await fetch_via_googlebot_spoof(
                url, extractor=self.extractor,
            )

        if method == BypassMethod.HEADLESS_AUTH:
            if (
                not user_id
                or not self.account_manager
            ):
                return None
            try:
                return (
                    await fetch_via_headless_auth(
                        url,
                        user_id=user_id,
                        account_manager=(
                            self.account_manager
                        ),
                        extractor=self.extractor,
                    )
                )
            except RuntimeError:
                logger.warning(
                    'headless_auth не удался'
                    ' для %s',
                    url,
                )
                return None

        if method == BypassMethod.WSJ_BYPASS:
            return await fetch_via_wsj(
                url, extractor=self.extractor,
            )

        return None
