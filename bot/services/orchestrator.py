"""Оркестратор — координация всех компонентов.

Собирает вместе:
- Классификатор paywall
- Платформенные обработчики
- Методы обхода
- Кеш статей
- Экстрактор контента
- Менеджер аккаунтов
"""


from bot.auth.account_manager import AccountManager
from bot.constants import BypassMethod, PaywallType
from bot.models.article import Article
from bot.models.user_request import UserRequest
from bot.services.content_extractor import ContentExtractor
from bot.services.methods.archive_relay import fetch_via_archive
from bot.services.methods.googlebot_spoof import fetch_via_googlebot_spoof
from bot.services.methods.headless_auth import fetch_via_headless_auth
from bot.services.methods.js_disable import fetch_via_js_disable
from bot.services.paywall_classifier import PaywallClassifier
from bot.services.platforms.conde_nast import CondeNastPlatform
from bot.services.platforms.german_freemium import GermanFreemiumPlatform
from bot.services.platforms.republic import RepublicPlatform
from bot.storage.cache import get_cached_article, save_article_to_cache

__all__ = ['Orchestrator']


class Orchestrator:
    """Оркестратор — координация всех компонентов."""

    def __init__(
        self,
        classifier: PaywallClassifier | None = None,
        account_manager: AccountManager | None = None,
        extractor: ContentExtractor | None = None,
    ) -> None:
        """Инициализировать оркестратор.

        Args:
            classifier: Классификатор paywall.
            account_manager: Менеджер аккаунтов.
            extractor: Экстрактор контента.
        """
        self.classifier = classifier or PaywallClassifier()
        self.account_manager = account_manager
        self.extractor = extractor or ContentExtractor()

        # Инициализируем платформы
        self.platforms: dict[str, object] = {
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
        username: str | None = None,
        skip_cache: bool = False,
    ) -> UserRequest:
        """Обработать URL: классификация → кеш → обход.

        Args:
            url: URL статьи.
            user_id: ID пользователя Telegram (для авторизации).
            username: Имя пользователя (для логов).
            skip_cache: Игнорировать кеш (принудительный запрос).

        Returns:
            UserRequest с результатами обработки.
        """
        # Создаём запрос для логирования
        request = UserRequest(
            user_id=user_id or 0,
            username=username,
            original_url=url,
        )

        try:
            # 1. Проверяем кеш (если не просили пропустить)
            if not skip_cache:
                cached = await get_cached_article(url)
                if cached:
                    request.article = cached
                    request.success = True
                    request.processed_at = datetime.now()
                    return request

            # 2. Классифицируем
            paywall_info = await self.classifier.classify(url)
            request.paywall_info = paywall_info

            # 3. Если тип неизвестен — пробуем archive.ph
            if not paywall_info.is_known:
                article = await fetch_via_archive(
                    url,
                    extractor=self.extractor,
                )
                request.article = article
                request.success = article is not None

                if article:
                    article.paywall_type = PaywallType.UNKNOWN
                    article.extraction_method = BypassMethod.ARCHIVE_RELAY
                    await save_article_to_cache(article)

                request.processed_at = datetime.now()
                return request

            # 4. Если есть платформа — делегируем ей
            if paywall_info.platform and paywall_info.platform in self.platforms:
                platform = self.platforms[paywall_info.platform]
                article = await platform.handle(
                    url,
                    paywall_info,
                    user_id=user_id,
                )
                request.article = article
                request.success = article is not None

                if article:
                    article.paywall_type = paywall_info.paywall_type
                    article.extraction_method = paywall_info.suggested_method
                    await save_article_to_cache(article)

                request.processed_at = datetime.now()
                return request

            # 5. Нет платформы — используем метод из классификации
            if paywall_info.suggested_method:
                article = await self._fetch_with_method(
                    url,
                    paywall_info.suggested_method,
                    user_id,
                )
                request.article = article
                request.success = article is not None

                if article:
                    article.paywall_type = paywall_info.paywall_type
                    article.extraction_method = paywall_info.suggested_method
                    await save_article_to_cache(article)

                request.processed_at = datetime.now()
                return request

            # 6. Ничего не сработало — fallback на archive
            article = await fetch_via_archive(
                url,
                extractor=self.extractor,
            )
            request.article = article
            request.success = article is not None

            if article:
                article.paywall_type = PaywallType.UNKNOWN
                article.extraction_method = BypassMethod.ARCHIVE_RELAY
                await save_article_to_cache(article)

            request.processed_at = datetime.now()
            return request

        except Exception as e:
            request.complete(error=e)
            return request

    async def _fetch_with_method(
        self,
        url: str,
        method: BypassMethod,
        user_id: int | None = None,
    ) -> Article | None:
        """Выбрать и вызвать нужный метод обхода.

        Args:
            url: URL статьи.
            method: Метод обхода.
            user_id: ID пользователя (для headless).

        Returns:
            Article или None.
        """
        if method == BypassMethod.JS_DISABLE:
            return await fetch_via_js_disable(url, extractor=self.extractor)

        if method == BypassMethod.ARCHIVE_RELAY:
            return await fetch_via_archive(url, extractor=self.extractor)

        if method == BypassMethod.GOOGLEBOT_SPOOF:
            return await fetch_via_googlebot_spoof(url, extractor=self.extractor)

        if method == BypassMethod.HEADLESS_AUTH:
            if not user_id or not self.account_manager:
                return None
            return await fetch_via_headless_auth(
                url,
                user_id=user_id,
                account_manager=self.account_manager,
                extractor=self.extractor,
            )

        return None
