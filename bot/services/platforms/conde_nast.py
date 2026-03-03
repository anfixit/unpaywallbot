"""Платформа для изданий Condé Nast.

New Yorker, Vanity Fair и другие. Metered paywall
с лимитом статей — googlebot_spoof работает хорошо.
"""

from bot.models.article import Article
from bot.models.paywall_info import PaywallInfo
from bot.services.content_extractor import (
    ContentExtractor,
)
from bot.services.methods.googlebot_spoof import (
    fetch_via_googlebot_spoof,
)
from bot.services.methods.js_disable import (
    fetch_via_js_disable,
)

__all__ = ['CondeNastPlatform']


class CondeNastPlatform:
    """Обработчик изданий Condé Nast."""

    def __init__(
        self,
        extractor: ContentExtractor | None = None,
    ) -> None:
        """Инициализировать платформу."""
        self.extractor = (
            extractor or ContentExtractor()
        )

    async def handle(
        self,
        url: str,
        paywall_info: PaywallInfo,
        *,
        user_id: int | None = None,
    ) -> Article | None:
        """Обработать URL Condé Nast.

        Сначала googlebot_spoof, затем js_disable.

        Args:
            url: URL статьи.
            paywall_info: Информация о paywall.
            user_id: Не используется.

        Returns:
            Article или None.
        """
        article = await fetch_via_googlebot_spoof(
            url, extractor=self.extractor,
        )

        if article and not article.is_empty:
            return article

        return await fetch_via_js_disable(
            url, extractor=self.extractor,
        )
