"""Платформа для немецких freemium-изданий.

Spiegel S+, Zeit Z+, FAZ F+, Süddeutsche,
Tagesspiegel, Welt, Berliner Zeitung.
"""

import logging
import re
from urllib.parse import (
    parse_qs,
    urlencode,
    urlparse,
)

import httpx

from bot.auth.account_manager import AccountManager
from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.services.content_extractor import (
    ContentExtractor,
)
from bot.services.methods.archive_relay import (
    fetch_via_archive,
)
from bot.services.methods.headless_auth import (
    fetch_via_headless_auth,
)
from bot.services.methods.js_disable import (
    fetch_via_js_disable,
)

__all__ = ['GermanFreemiumPlatform']

logger = logging.getLogger(__name__)


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
        1. Не-premium → js_disable
        2. Premium + есть аккаунт → headless_auth
        3. Premium + нет аккаунта → js_disable
           (иногда отдаёт) → archive.ph

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

        # Premium-статья: ?reduced=true для SZ
        if 'sueddeutsche.de' in paywall_info.domain:
            modified = self._add_reduced_param(url)
            try:
                article = (
                    await fetch_via_js_disable(
                        modified,
                        extractor=self.extractor,
                    )
                )
                if article and not article.is_empty:
                    return article
            except (
                httpx.HTTPError,
                OSError,
            ):
                logger.debug(
                    'SZ reduced: сетевая ошибка'
                    ' для %s',
                    url,
                )

        # Headless с аккаунтом (если есть)
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
                if article and not article.is_empty:
                    return article
            except RuntimeError:
                logger.warning(
                    'Headless не удался для %s',
                    url,
                )

        # Fallback: js_disable (иногда premium
        # контент всё равно в DOM)
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
                'js_disable premium fallback:'
                ' сетевая ошибка для %s',
                url,
            )

        # Последний шанс: archive.ph
        logger.info(
            'Все методы не удались для %s,'
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
            )
            return None

    async def _try_free_article(
        self,
        url: str,
    ) -> Article | None:
        """Попробовать извлечь бесплатную статью.

        js_disable → archive.ph fallback.

        Args:
            url: URL статьи.

        Returns:
            Article или None.
        """
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
            )

        logger.info(
            'js_disable вернул None для %s'
            ' — пробуем archive.ph',
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
            )
            return None

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
