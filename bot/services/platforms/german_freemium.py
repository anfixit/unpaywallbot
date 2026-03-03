"""Платформа для немецких freemium-изданий.

Spiegel S+, Zeit Z+, FAZ F+, Süddeutsche,
Tagesspiegel, Welt.
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
        'spiegel.de': r'/plus/|spiegel-plus|s\+',
        'zeit.de': r'/plus/|zeit-plus|z\+',
        'faz.net': r'/faz-plus|f\+',
        'sueddeutsche.de': r'plus|reduced=true',
        'tagesspiegel.de': r'/plus/',
        'welt.de': r'/plus/',
    }

    def __init__(
        self,
        extractor: ContentExtractor | None = None,
        account_manager: AccountManager | None = (
            None
        ),
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
            article = await fetch_via_js_disable(
                url, extractor=self.extractor,
            )
            # Если экстрактор вернул None —
            # возможно S+ статья без маркера в URL.
            # Не падаем молча, а логируем.
            if article is None:
                logger.info(
                    'js_disable вернул None для %s'
                    ' — возможно скрытый premium',
                    url,
                )
            return article

        # Премиум — пробуем headless
        if user_id and self.account_manager:
            try:
                return await fetch_via_headless_auth(
                    url,
                    user_id=user_id,
                    account_manager=(
                        self.account_manager
                    ),
                    extractor=self.extractor,
                )
            except RuntimeError:
                logger.warning(
                    'Headless не удался для %s, '
                    'пробуем archive',
                    url,
                )
                return await fetch_via_archive(
                    url, extractor=self.extractor,
                )

        # ?reduced=true для Süddeutsche
        if 'sueddeutsche.de' in paywall_info.domain:
            modified = self._add_reduced_param(url)
            return await fetch_via_js_disable(
                modified, extractor=self.extractor,
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
        """Добавить ?reduced=true для Süddeutsche."""
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        query['reduced'] = ['true']
        new_query = urlencode(query, doseq=True)
        return parsed._replace(
            query=new_query,
        ).geturl()
