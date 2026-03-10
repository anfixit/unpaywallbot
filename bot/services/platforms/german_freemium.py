"""Платформа для немецких freemium-изданий.

Spiegel S+, Zeit Z+, FAZ F+, Süddeutsche,
Tagesspiegel, Welt, Berliner Zeitung.

Цепочка методов:
1. js_disable — быстро, работает для бесплатных
2. googlebot_spoof — отдаёт полный S+/WELTplus
   контент (проверено curl: 424KB / 753KB)
3. archive.ph — последний шанс
"""

import logging
import re
from urllib.parse import (
    parse_qs,
    urlencode,
    urlparse,
)

from bot.auth.account_manager import AccountManager
from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
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

__all__ = ['GermanFreemiumPlatform']

logger = logging.getLogger(__name__)

# Если js_disable вернул меньше — считаем
# что это лид, а не полная статья.
_MIN_ARTICLE_LENGTH = 500


class GermanFreemiumPlatform:
    """Обработчик немецких freemium-изданий."""

    PREMIUM_URL_PATTERNS: dict[str, str] = {
        'spiegel.de': (
            r'/plus/|spiegel-plus|s\+'
        ),
        'zeit.de': r'/plus/|zeit-plus|z\+',
        'faz.net': r'/faz-plus|f\+',
        'sueddeutsche.de': r'plus|reduced=true',
        'tagesspiegel.de': r'/plus/',
        'welt.de': r'/plus/',
        'berliner-zeitung.de': r'/plus/',
    }

    def __init__(
        self,
        extractor: ContentExtractor | None = None,
        account_manager: (
            AccountManager | None
        ) = None,
    ) -> None:
        """Инициализировать платформу."""
        self.extractor = (
            extractor or ContentExtractor()
        )
        self.account_manager = account_manager

    async def handle(
        self,
        url: str,
        paywall_info: PaywallInfo,
        *,
        user_id: int | None = None,
    ) -> Article | None:
        """Обработать URL немецкого издания.

        Стратегия:
        1. js_disable (быстро)
        2. Если мало текста → googlebot_spoof
        3. Premium + аккаунт → headless_auth
        4. archive.ph как fallback

        Args:
            url: URL статьи.
            paywall_info: Информация о paywall.
            user_id: ID пользователя.

        Returns:
            Article или None.
        """
        is_premium = self._check_if_premium(
            url, paywall_info.domain,
        )

        if not is_premium:
            return await self._try_free_article(
                url,
            )

        # Premium: ?reduced=true для SZ
        if 'sueddeutsche.de' in paywall_info.domain:
            modified = self._add_reduced_param(url)
            article = await fetch_via_js_disable(
                modified, extractor=self.extractor,
            )
            if self._is_full_article(article):
                return article

        # 1. js_disable — иногда premium
        #    контент всё равно в DOM
        article = await fetch_via_js_disable(
            url, extractor=self.extractor,
        )
        if self._is_full_article(article):
            return article

        # 2. googlebot_spoof — немецкие сайты
        #    отдают полный контент Googlebot
        logger.info(
            'js_disable: %d символов для %s'
            ' — пробуем googlebot',
            len(article.content) if article else 0,
            url,
        )
        article = await fetch_via_googlebot_spoof(
            url, extractor=self.extractor,
        )
        if self._is_full_article(article):
            return article

        # 3. Headless с аккаунтом
        if user_id and self.account_manager:
            try:
                article = (
                    await fetch_via_headless_auth(
                        url,
                        user_id=user_id,
                        account_manager=(
                            self.account_manager
                        ),
                        extractor=self.extractor,
                    )
                )
                if self._is_full_article(article):
                    return article
            except RuntimeError:
                logger.warning(
                    'Headless не удался для %s',
                    url,
                )

        # 4. archive.ph — последний шанс
        logger.info(
            'Все методы не удались для %s'
            ' — пробуем archive.ph',
            url,
        )
        return await fetch_via_archive(
            url, extractor=self.extractor,
        )

    async def _try_free_article(
        self,
        url: str,
    ) -> Article | None:
        """Попробовать извлечь бесплатную статью.

        js_disable → googlebot → archive fallback.

        Args:
            url: URL статьи.

        Returns:
            Article или None.
        """
        article = await fetch_via_js_disable(
            url, extractor=self.extractor,
        )
        if self._is_full_article(article):
            return article

        # Мало текста — пробуем googlebot
        logger.info(
            'js_disable: %d символов для %s'
            ' — пробуем googlebot',
            len(article.content) if article else 0,
            url,
        )
        article = await fetch_via_googlebot_spoof(
            url, extractor=self.extractor,
        )
        if self._is_full_article(article):
            return article

        logger.info(
            'googlebot не помог для %s'
            ' — пробуем archive.ph',
            url,
        )
        return await fetch_via_archive(
            url, extractor=self.extractor,
        )

    @staticmethod
    def _is_full_article(
        article: Article | None,
    ) -> bool:
        """Проверить что статья не лид.

        Args:
            article: Извлечённая статья.

        Returns:
            True если текст достаточно длинный.
        """
        if not article or article.is_empty:
            return False
        return len(article.content) >= (
            _MIN_ARTICLE_LENGTH
        )

    def _check_if_premium(
        self,
        url: str,
        domain: str,
    ) -> bool:
        """Проверить, премиум ли статья."""
        for pat_domain, pattern in (
            self.PREMIUM_URL_PATTERNS.items()
        ):
            if pat_domain in domain:
                return bool(
                    re.search(
                        pattern,
                        url,
                        re.IGNORECASE,
                    ),
                )
        return False

    @staticmethod
    def _add_reduced_param(url: str) -> str:
        """Добавить ?reduced=true для SZ."""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        query['reduced'] = ['true']
        new_query = urlencode(query, doseq=True)
        return parsed._replace(
            query=new_query,
        ).geturl()
